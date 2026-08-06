"""dir-to-pdfa executor — converts an entire folder to a single PDF/A file.

Walks the directory recursively, converts each file based on its extension
(using conversion.json), creates a cover page with table of contents,
placeholder pages for unconvertible files, and merges everything into
<foldername>.pdf.
"""

import json
import os
import shutil
import subprocess
import tempfile
import logging

import requests
from pypdf import PdfMerger

from openworks.fs import JobFS

logger = logging.getLogger("openworks.dir2pdfa")

# Load conversion map (extension → converter type)
_CONV_MAP_PATH = os.path.join(os.path.dirname(__file__), "conversion.json")
with open(_CONV_MAP_PATH) as _f:
    CONVERSION_MAP: dict[str, str] = json.load(_f)


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _md_to_pdf(md_text: str, out_path: str, tmpdir: str):
    """Convert markdown text to PDF using pandoc + xelatex."""
    md_path = os.path.join(tmpdir, "_toc.md")
    with open(md_path, "w") as f:
        f.write(md_text)
    subprocess.run(
        ["pandoc", md_path, "-o", out_path, "--pdf-engine=xelatex"],
        check=True, capture_output=True, timeout=120,
    )


def _convert_collabora(content: bytes, filename: str, out_path: str, collabora_url: str):
    """Convert office document to PDF via Collabora."""
    resp = requests.post(
        f"{collabora_url.rstrip('/')}/cool/convert-to/pdf",
        files={"data": (filename, content)},
        timeout=300,
    )
    resp.raise_for_status()
    if len(resp.content) < 100:
        raise RuntimeError(f"Collabora returned too small response ({len(resp.content)} bytes)")
    with open(out_path, "wb") as f:
        f.write(resp.content)


def _convert_chrome(content: bytes, filename: str, out_path: str, tmpdir: str):
    """Convert HTML to PDF via chrome-headless-shell."""
    html_path = os.path.join(tmpdir, filename)
    with open(html_path, "wb") as f:
        f.write(content)
    subprocess.run(
        ["chrome-headless-shell", "--headless", "--disable-gpu", "--no-sandbox",
         f"--print-to-pdf={out_path}", f"file://{html_path}"],
        check=True, capture_output=True, timeout=120,
    )


def _convert_pandoc(content: bytes, filename: str, out_path: str, tmpdir: str):
    """Convert Markdown to PDF via pandoc + xelatex."""
    src_path = os.path.join(tmpdir, filename)
    with open(src_path, "wb") as f:
        f.write(content)
    subprocess.run(
        ["pandoc", src_path, "-o", out_path, "--pdf-engine=xelatex"],
        check=True, capture_output=True, timeout=300,
    )


def _convert_mermaid(content: bytes, filename: str, out_path: str, tmpdir: str):
    """Convert Mermaid diagram to PDF via mmdc."""
    src_path = os.path.join(tmpdir, filename)
    with open(src_path, "wb") as f:
        f.write(content)
    result = subprocess.run(
        ["mmdc", "-i", src_path, "-o", out_path, "-b", "white",
         "--pdfFit", "-p", "/opt/puppeteer.json"],
        capture_output=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"mmdc failed: {result.stderr.decode()[-500:]}")


def _make_placeholder(filepath: str, size: int, ext: str, out_path: str, tmpdir: str):
    """Create a one-page placeholder PDF for an unconvertible file."""
    md = (
        f"# Nicht konvertierbar\n\n"
        f"**Datei:** `{filepath}`\n\n"
        f"**Typ:** `{ext}`\n\n"
        f"**Größe:** {_human_size(size)}\n\n"
        f"Diese Datei konnte nicht in PDF/A konvertiert werden.\n"
    )
    _md_to_pdf(md, out_path, tmpdir)


def execute(fs: JobFS, dest_fs: JobFS | None, params: dict, job_id: str, on_stage=None) -> dict:
    """Walk directory, convert all files, merge into single PDF."""
    stage = on_stage or (lambda s, p=0: None)
    out_fs = dest_fs or fs

    collabora_url = params.get("collabora_url", os.environ.get("COLLABORA_URL", ""))
    folder_name = params.get("origin_filename", "Dokumente")

    # Output filename — this file is excluded from the walk
    output_name = f"{folder_name}.pdf"

    # --- 1. Scan ---
    stage("scanning", 5)
    all_entries = fs.ls("/", recursive=True)
    files = [e for e in all_entries if not e.is_dir and e.name != output_name]
    files.sort(key=lambda e: e.path)

    convertible = []
    unconvertible = []
    for entry in files:
        ext = os.path.splitext(entry.name)[1].lower()
        converter = CONVERSION_MAP.get(ext)
        if converter:
            convertible.append((entry, ext, converter))
        else:
            unconvertible.append((entry, ext))

    logger.info("dir-to-pdfa: %d files (%d convertible, %d unconvertible)",
                len(files), len(convertible), len(unconvertible))

    with tempfile.TemporaryDirectory(prefix=f"openworks-dir2pdfa-{job_id[:8]}-") as tmpdir:
        pdf_parts = []  # list of (order_key, pdf_path)

        # --- 2. Cover page + TOC ---
        stage("toc", 10)
        toc_lines = [f"# {folder_name}\n", "## Inhaltsverzeichnis\n"]

        if convertible:
            toc_lines.append("### Konvertierte Dateien\n")
            for entry, ext, converter in convertible:
                toc_lines.append(f"- `{entry.path}` ({ext}, {_human_size(entry.size)})")

        if unconvertible:
            toc_lines.append("\n### Nicht konvertierbare Dateien\n")
            for entry, ext in unconvertible:
                toc_lines.append(f"- `{entry.path}` ({ext}, {_human_size(entry.size)})")

        toc_lines.append(f"\n---\n*{len(convertible)} konvertiert, {len(unconvertible)} Platzhalter*\n")

        cover_path = os.path.join(tmpdir, "_000_cover.pdf")
        _md_to_pdf("\n".join(toc_lines), cover_path, tmpdir)
        pdf_parts.append(("", cover_path))

        # --- 3. Convert files ---
        total = len(files)
        for idx, (entry, ext, converter) in enumerate(convertible):
            progress = 15 + int(70 * idx / max(total, 1))
            stage("converting", progress)
            logger.info("  [%d/%d] %s (%s)", idx + 1, total, entry.path, converter)

            safe_name = entry.path.replace("/", "__")
            out_pdf = os.path.join(tmpdir, f"{safe_name}.pdf")

            try:
                if converter == "copy":
                    content = fs.read(entry.path)
                    with open(out_pdf, "wb") as f:
                        f.write(content)
                elif converter == "collabora":
                    if not collabora_url:
                        raise ValueError("COLLABORA_URL not configured")
                    content = fs.read(entry.path)
                    _convert_collabora(content, entry.name, out_pdf, collabora_url)
                elif converter == "chrome":
                    content = fs.read(entry.path)
                    _convert_chrome(content, entry.name, out_pdf, tmpdir)
                elif converter == "pandoc":
                    content = fs.read(entry.path)
                    _convert_pandoc(content, entry.name, out_pdf, tmpdir)
                elif converter == "mermaid":
                    content = fs.read(entry.path)
                    _convert_mermaid(content, entry.name, out_pdf, tmpdir)
                else:
                    raise ValueError(f"unknown converter: {converter}")

                pdf_parts.append((entry.path, out_pdf))
            except Exception as e:
                logger.warning("  conversion failed for %s: %s — creating placeholder", entry.path, e)
                _make_placeholder(entry.path, entry.size, ext, out_pdf, tmpdir)
                pdf_parts.append((entry.path, out_pdf))

        # --- 4. Placeholders for unconvertible ---
        for idx, (entry, ext) in enumerate(unconvertible):
            progress = 15 + int(70 * (len(convertible) + idx) / max(total, 1))
            stage("converting", progress)
            logger.info("  [placeholder] %s (%s)", entry.path, ext)

            safe_name = entry.path.replace("/", "__")
            out_pdf = os.path.join(tmpdir, f"{safe_name}.pdf")
            _make_placeholder(entry.path, entry.size, ext, out_pdf, tmpdir)
            pdf_parts.append((entry.path, out_pdf))

        # --- 5. Merge ---
        stage("merging", 88)
        pdf_parts.sort(key=lambda x: x[0])  # cover first (empty key), then alphabetical
        merged_path = os.path.join(tmpdir, output_name)

        merger = PdfMerger()
        for _, pdf_path in pdf_parts:
            if os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0:
                merger.append(pdf_path)
        merger.write(merged_path)
        merger.close()

        # --- 6. Upload ---
        stage("uploading", 95)
        with open(merged_path, "rb") as f:
            out_fs.write(output_name, f.read())

        merged_size = os.path.getsize(merged_path)
        logger.info("dir-to-pdfa: done — %s (%s)", output_name, _human_size(merged_size))

    return {
        "target": output_name,
        "size": merged_size,
        "files_total": len(files),
        "files_converted": len(convertible),
        "files_placeholder": len(unconvertible),
    }
