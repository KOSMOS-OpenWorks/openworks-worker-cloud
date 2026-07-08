"""ZIP executor — creates ZIP archives from folder contents."""

import os
import logging
import zipfile
import tempfile

from ..fs import JobFS

logger = logging.getLogger("openworks.zip")


def _download_dir(fs, remote_path, local_dir):
    """Recursively download a directory from WebDAV to local disk.
    Creates local directories even if empty."""
    entries = fs.ls(remote_path)
    for entry in entries:
        child_path = remote_path.rstrip("/") + "/" + entry.name
        if entry.is_dir:
            local_subdir = os.path.join(local_dir, entry.name)
            os.makedirs(local_subdir, exist_ok=True)
            _download_dir(fs, child_path, local_subdir)
        else:
            content = fs.read(child_path)
            local_path = os.path.join(local_dir, entry.name)
            with open(local_path, "wb") as f:
                f.write(content)


def execute(fs: JobFS, dest_fs: JobFS | None, params: dict, job_id: str, on_stage=None) -> dict:
    """Create a ZIP archive from origin share contents."""
    out_fs = dest_fs or fs

    origin_filename = params.get("origin_filename", "")

    with tempfile.TemporaryDirectory(prefix=f"openworks-{job_id}-") as tmpdir:
        source_dir = os.path.join(tmpdir, "source")
        os.makedirs(source_dir, exist_ok=True)

        if origin_filename:
            # Check if it's a directory (has children) or a file
            is_dir = False
            try:
                entries = fs.ls(origin_filename)
                if entries:
                    is_dir = True
                    logger.info("ls(%s) returned %d entries — treating as directory", origin_filename, len(entries))
                    _download_dir(fs, origin_filename, source_dir)
            except Exception as exc:
                logger.info("ls(%s) failed: %s — treating as file", origin_filename, exc)

            if not is_dir:
                content = fs.read(origin_filename)
                local_path = os.path.join(source_dir, os.path.basename(origin_filename))
                with open(local_path, "wb") as f:
                    f.write(content)
                logger.info("read %s: %d bytes", origin_filename, len(content))
            zip_name = params.get("archive_name", os.path.splitext(os.path.basename(origin_filename))[0] + ".zip")
        else:
            # Download everything from share root
            _download_dir(fs, "/", source_dir)
            zip_name = params.get("archive_name", "archive.zip")

        # Create ZIP (including empty directories)
        zip_path = os.path.join(tmpdir, zip_name)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_dir):
                for dir_name in dirs:
                    dir_full = os.path.join(root, dir_name)
                    arcname = os.path.relpath(dir_full, source_dir) + "/"
                    zf.mkdir(arcname)
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, source_dir)
                    zf.write(full_path, arcname)

        # Log ZIP contents before upload
        with zipfile.ZipFile(zip_path, "r") as zf:
            logger.info("ZIP contents of %s:", zip_name)
            for info in zf.infolist():
                logger.info("  %s  %d bytes", info.filename, info.file_size)
            if not zf.infolist():
                logger.warning("ZIP is EMPTY!")

        # Upload result
        with open(zip_path, "rb") as f:
            out_fs.write(zip_name, f.read())

    return {"target": zip_name}
