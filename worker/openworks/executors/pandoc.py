"""Pandoc executor — converts Markdown to PDF."""

import os
import subprocess
import tempfile

from ..fs import JobFS


def execute(fs: JobFS, dest_fs: JobFS | None, params: dict, job_id: str, on_stage=None) -> dict:
    """Convert a Markdown file to PDF using pandoc."""
    out_fs = dest_fs or fs

    # Read source — use origin_filename if provided (folder share),
    # otherwise list and take the first file (file share)
    filename = params.get("origin_filename", "")
    if filename:
        content = fs.read(filename)
    else:
        source_info = fs.ls("/")
        if not source_info:
            raise FileNotFoundError("no files in origin share")
        filename = source_info[0].name
        content = fs.read(filename)

    with tempfile.TemporaryDirectory(prefix=f"openworks-{job_id}-") as tmpdir:
        local_in = os.path.join(tmpdir, filename)
        base_name = os.path.splitext(filename)[0]
        local_out = os.path.join(tmpdir, f"{base_name}.pdf")

        with open(local_in, "wb") as f:
            f.write(content)

        cmd = [
            params.get("command", "pandoc"),
            local_in, "-o", local_out,
        ]

        engine = params.get("engine", "xelatex")
        cmd.append(f"--pdf-engine={engine}")

        user_name = params.get("user_name", "")
        if user_name:
            cmd.append(f"--variable=author:{user_name}")

        date = params.get("date", "")
        if date:
            cmd.append(f"--variable=date:{date}")

        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        with open(local_out, "rb") as f:
            out_fs.write(f"{base_name}.pdf", f.read())

    return {"target": f"{base_name}.pdf"}
