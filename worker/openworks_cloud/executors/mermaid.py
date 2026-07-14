"""Mermaid executor — converts .mmd/.mermaid diagrams to PDF.

Uses mmdc (mermaid-cli) with chrome-headless-shell for correct rendering.
"""

import os
import subprocess
import tempfile

from openworks.fs import JobFS


def execute(fs: JobFS, dest_fs: JobFS | None, params: dict, job_id: str, on_stage=None) -> dict:
    """Convert a Mermaid diagram to PDF using mmdc."""
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
        local_out = os.path.join(tmpdir, f"{base_name}.pdf")

        with open(local_in, "wb") as f:
            f.write(content)

        cmd = [
            "mmdc",
            "-i", local_in,
            "-o", local_out,
            "-b", "white",
            "--pdfFit",
            "-p", "/opt/puppeteer.json",
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"mmdc failed: {result.stderr.decode()[-500:]}")

        with open(local_out, "rb") as f:
            out_fs.write(f"{base_name}.pdf", f.read())

    return {"target": f"{base_name}.pdf"}
