"""Mermaid executor — converts .mmd/.mermaid diagrams to PDF.

Renders Mermaid to SVG headlessly (jsdom + @napi-rs/canvas, no browser),
then converts SVG to PDF with cairosvg.
"""

import os
import re
import subprocess
import tempfile

import cairosvg

from openworks.fs import JobFS

RENDER_SCRIPT = "/opt/mermaid/mermaid-render.mjs"


def _clean_svg_for_cairo(svg: bytes) -> bytes:
    """Remove foreignObject elements that contain HTML (cairosvg can't parse them)."""
    text = svg.decode("utf-8", errors="replace")
    # Replace foreignObject blocks with simple text fallback
    text = re.sub(
        r"<foreignObject[^>]*>.*?</foreignObject>",
        "",
        text,
        flags=re.DOTALL,
    )
    return text.encode("utf-8")


def execute(fs: JobFS, dest_fs: JobFS | None, params: dict, job_id: str, on_stage=None) -> dict:
    """Convert a Mermaid diagram to PDF via SVG."""
    out_fs = dest_fs or fs

    filename = params.get("origin_filename", "")
    if filename:
        content = fs.read(filename)
    else:
        source_info = fs.ls("/")
        if not source_info:
            raise FileNotFoundError("no files in origin share")
        filename = source_info[0].name
        content = fs.read(filename)

    mermaid_text = content.decode("utf-8", errors="replace").strip()
    if not mermaid_text:
        raise ValueError(f"Empty mermaid file: {filename}")

    with tempfile.TemporaryDirectory(prefix=f"openworks-{job_id}-") as tmpdir:
        local_in = os.path.join(tmpdir, filename)
        base_name = os.path.splitext(filename)[0]
        pdf_path = os.path.join(tmpdir, f"{base_name}.pdf")

        with open(local_in, "wb") as f:
            f.write(content)

        # Mermaid → SVG (headless, no browser)
        result = subprocess.run(
            ["node", RENDER_SCRIPT, local_in],
            capture_output=True, timeout=60
        )
        if result.returncode != 0:
            raise RuntimeError(f"Mermaid render failed: {result.stderr.decode()[-500:]}")

        svg_data = _clean_svg_for_cairo(result.stdout)

        # SVG → PDF
        cairosvg.svg2pdf(bytestring=svg_data, write_to=pdf_path)

        with open(pdf_path, "rb") as f:
            out_fs.write(f"{base_name}.pdf", f.read())

    return {"target": f"{base_name}.pdf"}
