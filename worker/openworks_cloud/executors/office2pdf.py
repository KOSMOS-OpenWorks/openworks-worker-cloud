"""Office-to-PDF executor — converts office documents via Collabora."""

import os

import requests

from openworks.fs import JobFS


SUPPORTED_EXTENSIONS = {
    ".docx", ".doc", ".odt", ".xlsx", ".xls", ".ods",
    ".pptx", ".ppt", ".odp", ".rtf", ".csv", ".txt",
}


def execute(fs: JobFS, dest_fs: JobFS | None, params: dict, job_id: str, on_stage=None) -> dict:
    """Convert an office document to PDF via Collabora convert-to API."""
    out_fs = dest_fs or fs

    collabora_url = params.get("collabora_url", os.environ.get("COLLABORA_URL", ""))
    if not collabora_url:
        raise ValueError("collabora_url not configured (param or COLLABORA_URL env)")

    filename = params.get("origin_filename", "")
    if filename:
        content = fs.read(filename)
    else:
        source_info = fs.ls("/")
        if not source_info:
            raise FileNotFoundError("no files in origin share")
        filename = source_info[0].name
        content = fs.read(filename)

    base_name = os.path.splitext(filename)[0]
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"unsupported format: {ext} (supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))})")

    convert_url = f"{collabora_url.rstrip('/')}/cool/convert-to/pdf"
    resp = requests.post(
        convert_url,
        files={"data": (filename, content)},
        timeout=300,
    )
    resp.raise_for_status()

    if len(resp.content) < 100:
        raise RuntimeError(f"Collabora returned too small response ({len(resp.content)} bytes)")

    out_fs.write(f"{base_name}.pdf", resp.content)

    return {"target": f"{base_name}.pdf", "size": len(resp.content)}
