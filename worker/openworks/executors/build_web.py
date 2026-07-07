"""Build-web executor — builds any web project and pushes as ZIP.

Clones a git repo, runs the build command, packages output as ZIP,
pushes to Codeberg Generic Packages registry.

Works for any web project — opencloud_web, openworks web-extension, etc.

job.params:
  repo: "opencloud_web"                  # repo name to clone
  branch: "openworks"                     # branch
  git_base: "https://codeberg.org/kosmos-opencloud"
  git_token: ""                           # optional for private repos
  build_cmd: "pnpm install && pnpm build" # build command
  dist_dir: "dist"                        # output directory (relative to repo root)
  push_registry: "codeberg.org"
  push_owner: "kosmos-opencloud"
  push_token: ""
  package_name: "web-dist"                # package name on registry
"""

import os
import subprocess
import logging
import zipfile
from datetime import datetime

logger = logging.getLogger("openworks.build-web")

WORK_DIR = "/build"


def execute(fs=None, dest_fs=None, params: dict = None, job_id: str = "", on_stage=None) -> dict:
    """Build web project and push as ZIP."""
    params = params or {}
    repo = params.get("repo", "opencloud_web")
    branch = params.get("branch", "kosmos")
    git_base = params.get("git_base", "https://codeberg.org/kosmos-opencloud")
    git_token = params.get("git_token", "")
    build_cmd = params.get("build_cmd", "pnpm install && pnpm build")
    dist_dir = params.get("dist_dir", "dist")
    push_registry = params.get("push_registry", "codeberg.org")
    push_owner = params.get("push_owner", "kosmos-opencloud")
    push_token = params.get("push_token", "")
    package_name = params.get("package_name", repo)
    tag = datetime.now().strftime("%Y%m%d-%H%M")

    results = {"steps": [], "tag": tag, "repo": repo}

    def run(cmd, cwd=None, label="", timeout=300):
        logger.info("[%s] %s", label, cmd[:120])
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        step = {"label": label, "exit_code": r.returncode}
        if r.returncode != 0:
            step["stderr"] = r.stderr[-500:] if r.stderr else ""
            results["steps"].append(step)
            raise RuntimeError(f"{label} failed (exit {r.returncode}): {r.stderr[-200:]}")
        results["steps"].append(step)
        return r.stdout

    auth_base = git_base
    if git_token:
        auth_base = git_base.replace("https://", f"https://{git_token}@")

    try:
        # 1. Clone/pull
        logger.info("=== build-web: %s branch=%s ===", repo, branch)
        os.makedirs(WORK_DIR, exist_ok=True)
        repo_dir = f"{WORK_DIR}/{repo}"

        if os.path.isdir(repo_dir):
            run(f"git fetch origin && git checkout {branch} 2>/dev/null || git checkout kosmos && git pull --ff-only",
                cwd=repo_dir, label="pull")
        else:
            run(f"git clone --depth 1 -b {branch} {auth_base}/{repo}.git {repo_dir} 2>/dev/null || "
                f"git clone --depth 1 -b kosmos {auth_base}/{repo}.git {repo_dir}",
                label="clone", timeout=120)

        # 2. Build
        logger.info("=== build ===")
        run(build_cmd, cwd=repo_dir, label="build", timeout=300)

        # 3. Package as ZIP
        full_dist = os.path.join(repo_dir, dist_dir)
        if not os.path.isdir(full_dist):
            raise FileNotFoundError(f"dist directory not found: {full_dist}")

        zip_path = f"{WORK_DIR}/{package_name}-{tag}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(full_dist):
                for f in files:
                    full = os.path.join(root, f)
                    arcname = os.path.relpath(full, full_dist)
                    zf.write(full, arcname)

        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        results["zip"] = zip_path
        results["size_mb"] = round(size_mb, 1)
        logger.info("ZIP: %s (%.1f MB)", zip_path, size_mb)

        # 4. Push to Codeberg Generic Packages
        if push_token:
            logger.info("=== push to registry ===")
            url = f"https://{push_registry}/api/packages/{push_owner}/generic/{package_name}/{tag}/{package_name}.zip"
            run(f"curl --fail -T {zip_path} -H 'Authorization: token {push_token}' '{url}'",
                label="push", timeout=120)
            results["pushed"] = True
            results["package_url"] = url
        else:
            results["pushed"] = False
            logger.info("No push_token — skipping push")

        results["status"] = "success"

    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        raise

    return results
