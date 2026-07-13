"""Mermaid executor — converts .mmd/.mermaid diagrams to PDF.

Uses the mermaid.ink online renderer to get SVG, then cairosvg to convert to PDF.
No Chromium/Puppeteer needed.
"""

import os
import tempfile
import urllib.parse
import urllib.request
import base64

import cairosvg

from openworks.fs import JobFS

MERMAID_INK_URL = "https://mermaid.ink/svg/"


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
    base_name = os.path.splitext(filename)[0]

    # Encode diagram for mermaid.ink API
    encoded = base64.urlsafe_b64encode(mermaid_text.encode()).decode()
    svg_url = f"{MERMAID_INK_URL}{encoded}"

    # Fetch SVG
    req = urllib.request.Request(svg_url, headers={"User-Agent": "OpenWorks/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        svg_data = resp.read()

    # Convert SVG to PDF
    with tempfile.TemporaryDirectory(prefix=f"openworks-{job_id}-") as tmpdir:
        pdf_path = os.path.join(tmpdir, f"{base_name}.pdf")
        cairosvg.svg2pdf(bytestring=svg_data, write_to=pdf_path)

        with open(pdf_path, "rb") as f:
            out_fs.write(f"{base_name}.pdf", f.read())

    return {"target": f"{base_name}.pdf"}
