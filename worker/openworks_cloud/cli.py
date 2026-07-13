"""CLI entry point for the OpenWorks cloud worker daemon."""

import glob
import logging
import os

import yaml

from openworks.config import clients_from_env
from openworks.worker import Worker
from .executors import pandoc, zip as zip_exec, unzip as unzip_exec, test_echo, office2pdf, mermaid


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

    clients, capacity = clients_from_env()

    pipeline_dirs = os.environ.get("OPENWORKS_PIPELINES", "").split(":") if os.environ.get("OPENWORKS_PIPELINES") else []

    executors = {
        "md-to-pdf": pandoc.execute,
        "zip-create": zip_exec.execute,
        "unzip": unzip_exec.execute,
        "test-echo": test_echo.execute,
        "office-to-pdf": office2pdf.execute,
        "mmd-to-pdf": mermaid.execute,
    }

    pipelines = load_pipelines(pipeline_dirs) if pipeline_dirs else None
    if pipelines:
        logging.info("loaded %d pipeline definition(s)", len(pipelines))

    worker = Worker(clients=clients, executors=executors, pipelines=pipelines, capacity=capacity)
    worker.run()


if __name__ == "__main__":
    main()
