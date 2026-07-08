"""Base executor interface for OpenWorks workers."""

from openworks.fs import JobFS


def execute(fs: JobFS, dest_fs: JobFS | None, params: dict, job_id: str) -> dict:
    """
    Execute a job. All executors follow this signature.

    Args:
        fs: JobFS for origin share (read source files)
        dest_fs: JobFS for destination share (write results), or None if same as origin
        params: job.params from pipeline YAML (opaque, executor-specific)
        job_id: unique job identifier

    Returns:
        dict with result metadata (e.g. {"target": "output.pdf"})
    """
    raise NotImplementedError("subclass must implement execute()")
