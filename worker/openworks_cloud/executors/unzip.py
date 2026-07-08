"""Unzip executor — extracts ZIP archives into the same folder."""

import os
import zipfile
import tempfile

from openworks.fs import JobFS


def execute(fs: JobFS, dest_fs: JobFS | None, params: dict, job_id: str, on_stage=None) -> dict:
    """Extract a ZIP archive into the same folder."""
    out_fs = dest_fs or fs

    filename = params.get("origin_filename", "")
    if not filename:
        entries = fs.ls("/")
        zips = [e for e in entries if e.name.endswith(".zip")]
        if not zips:
            raise FileNotFoundError("no ZIP file found in origin share")
        filename = zips[0].name

    content = fs.read(filename)

    with tempfile.TemporaryDirectory(prefix=f"openworks-{job_id}-") as tmpdir:
        zip_path = os.path.join(tmpdir, filename)
        with open(zip_path, "wb") as f:
            f.write(content)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(os.path.join(tmpdir, "out"))

        # Upload extracted entries
        out_dir = os.path.join(tmpdir, "out")
        created_dirs: set[str] = set()
        count = 0

        # Create all directories first (including empty ones)
        for root, dirs, _ in os.walk(out_dir):
            for d in dirs:
                rel_dir = os.path.relpath(os.path.join(root, d), out_dir)
                rel_dir = rel_dir.replace("\\", "/")
                if rel_dir not in created_dirs:
                    # Ensure parent chain exists
                    parts = rel_dir.split("/")
                    for i in range(1, len(parts)):
                        parent = "/".join(parts[:i])
                        if parent not in created_dirs:
                            out_fs.mkdir(parent)
                            created_dirs.add(parent)
                    out_fs.mkdir(rel_dir)
                    created_dirs.add(rel_dir)

        # Upload files
        for root, _, files in os.walk(out_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, out_dir).replace("\\", "/")
                with open(full_path, "rb") as f:
                    out_fs.write(rel_path, f.read())
                count += 1

    return {"extracted": count, "source": filename}
