"""Test executor — processes .tst files for end-to-end testing.

No external dependencies. Reads the source file, writes a result
with metadata. Use this to verify the full pipeline:
Poll → Pick → Share → Read → Write → Complete.
"""

import json
from datetime import datetime

from openworks.fs import JobFS


def execute(fs: JobFS, dest_fs: JobFS | None, params: dict, job_id: str, on_stage=None) -> dict:
    """Process a .tst file — read content, write result."""
    out_fs = dest_fs or fs

    # List source files
    entries = fs.ls("/")
    if not entries:
        raise FileNotFoundError("no files in origin share")

    source = entries[0]
    content = fs.read(source.name)

    # Build result
    result_data = {
        "job_id": job_id,
        "source": source.name,
        "source_size": len(content),
        "source_content": content.decode("utf-8", errors="replace")[:500],
        "processed_at": datetime.now().isoformat(),
        "params": params,
        "status": "ok",
    }

    # Write result as JSON
    result_name = source.name.rsplit(".", 1)[0] + ".result.json"
    out_fs.write(result_name, json.dumps(result_data, indent=2).encode())

    return {"target": result_name, "source_size": len(content)}
