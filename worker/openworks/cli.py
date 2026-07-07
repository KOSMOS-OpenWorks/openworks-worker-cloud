"""CLI entry point for the OpenWorks cloud worker daemon."""

import glob
import logging
import os
import sys

import yaml

from openworks.client import ControlClient
from openworks.worker import Worker
from .executors import pandoc, zip as zip_exec, unzip as unzip_exec, test_echo


def load_pipelines(dirs: list[str]) -> dict:
    """Load pipeline definitions from YAML files in the given directories."""
    pipelines = {}
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.yaml")) + glob.glob(os.path.join(d, "*.yml"))):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                if data and "pipelines" in data:
                    pipelines.update(data["pipelines"])
            except Exception as e:
                logging.warning("failed to load %s: %s", path, e)
    return pipelines


def main():
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper()),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    url = os.environ.get("OPENWORKS_URL", "")
    user = os.environ.get("OPENWORKS_USER", "")
    token = os.environ.get("OPENWORKS_TOKEN", "")
    pick = os.environ.get("OPENWORKS_PICK", "md-to-pdf,zip-create,test-echo")
    capacity = int(os.environ.get("OPENWORKS_CAPACITY", "2"))
    insecure = os.environ.get("OPENWORKS_INSECURE", "").lower() in ("1", "true", "yes")
    pipeline_dirs = os.environ.get("OPENWORKS_PIPELINES", "").split(":") if os.environ.get("OPENWORKS_PIPELINES") else []

    if not url:
        logging.error("OPENWORKS_URL required")
        sys.exit(1)

    if not url.startswith("https://") and not insecure:
        logging.error("OPENWORKS_URL must use https://. Set OPENWORKS_INSECURE=1 for dev.")
        sys.exit(1)

    if not user or not token:
        logging.error("OPENWORKS_USER and OPENWORKS_TOKEN required")
        sys.exit(1)

    pick_list = [t.strip() for t in pick.split(",")]

    client = ControlClient(
        base_url=url,
        user=user,
        token=token,
        pick=pick_list,
        capacity=capacity,
        verify_tls=not insecure,
    )

    executors = {
        "md-to-pdf": pandoc.execute,
        "zip-create": zip_exec.execute,
        "unzip": unzip_exec.execute,
        "test-echo": test_echo.execute,
    }

    # Load pipeline definitions from YAML dirs
    pipelines = load_pipelines(pipeline_dirs) if pipeline_dirs else None
    if pipelines:
        logging.info("loaded %d pipeline definition(s) from %s", len(pipelines), pipeline_dirs)

    worker = Worker(client=client, executors=executors, pipelines=pipelines)
    worker.run()


if __name__ == "__main__":
    main()
