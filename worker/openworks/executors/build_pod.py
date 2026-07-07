"""Generic build executor — clones a git repo and runs its build script.

The build logic lives in the repo (build.sh, build_app.sh, build_web.sh).
This executor just clones, runs, and reports.

job.params:
  repo: "opencloud"                       # repo name
  branch: "kosmos"                        # branch to build
  git_base: "https://codeberg.org/kosmos-opencloud"
  git_token: ""                           # optional auth token
  build_script: "build.sh"               # script to run (auto-detected if empty)
  env: {}                                 # extra env vars for the build
  push_token: ""                          # registry token (passed as env)
"""

import os
import subprocess
import logging
from datetime import datetime

logger = logging.getLogger("openworks.build")

WORK_DIR = "/build"

# Auto-detect build script in priority order
BUILD_SCRIPTS = ["build.sh", "build_kosmos.sh", "build_app.sh", "build_web.sh", "build_build_worker.sh"]


def execute(fs=None, dest_fs=None, params: dict = None, job_id: str = "", on_stage=None) -> dict:
    """Clone repo and run its build script."""
    params = params or {}
    if on_stage is None:
        on_stage = lambda stage, progress=0: None
    repo = params.get("repo", "opencloud")
    branch = params.get("branch", "kosmos")
    git_base = params.get("git_base", "https://codeberg.org/kosmos-opencloud")
    git_token = params.get("git_token", "")
    build_script = params.get("build_script", "")
    extra_env = params.get("env", {})
    push_token = params.get("push_token", "")
    tag = datetime.now().strftime("%Y%m%d-%H%M")

    results = {"steps": [], "tag": tag, "repo": repo, "branch": branch}

    def run(cmd, cwd=None, label="", timeout=600, env=None):
        logger.info("[%s] %s", label, cmd[:200])
        results["current_stage"] = label
        on_stage(label, 0)

        proc = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, env=env)
        output_lines = []
        try:
            for line in proc.stdout:
                line = line.rstrip()
                output_lines.append(line)
                if line:
                    logger.info("  %s", line[:200])
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError(f"{label} timed out after {timeout}s")

        step = {"label": label, "exit_code": proc.returncode,
                "output": "\n".join(output_lines[-20:])}
        if proc.returncode != 0:
            results["steps"].append(step)
            raise RuntimeError(f"{label} failed (exit {proc.returncode}): {output_lines[-3:] if output_lines else 'no output'}")
        results["steps"].append(step)
        return "\n".join(output_lines)

    auth_base = git_base
    if git_token:
        auth_base = git_base.replace("https://", f"https://{git_token}@")

    try:
        # 1. Clone/pull
        on_stage("clone", 10)
        logger.info("=== build: %s branch=%s ===", repo, branch)
        os.makedirs(WORK_DIR, exist_ok=True)
        repo_dir = f"{WORK_DIR}/{repo}"

        if os.path.isdir(repo_dir):
            run(f"git checkout -f {branch} 2>/dev/null || git checkout -f kosmos && git fetch origin && git reset --hard origin/{branch}",
                cwd=repo_dir, label="pull")
        else:
            run(f"git clone --depth 1 -b {branch} {auth_base}/{repo}.git {repo_dir} 2>/dev/null || "
                f"git clone --depth 1 -b kosmos {auth_base}/{repo}.git {repo_dir}",
                label="clone", timeout=120)

        # 2. Find build script
        if not build_script:
            for candidate in BUILD_SCRIPTS:
                if os.path.isfile(os.path.join(repo_dir, candidate)):
                    build_script = candidate
                    break

        if not build_script:
            raise FileNotFoundError(f"No build script found in {repo}. Tried: {BUILD_SCRIPTS}")

        on_stage("build", 30)
        logger.info("=== running %s ===", build_script)

        # 3. Build environment
        build_env = os.environ.copy()
        build_env["BRANCH"] = branch
        build_env["TAG"] = tag
        if push_token:
            build_env["PUSH_TOKEN"] = push_token
        # Pass all params as uppercase env vars (web_zip → WEB_ZIP)
        for k, v in params.items():
            env_key = k.upper()
            if env_key not in ("REPO", "BRANCH", "GIT_BASE", "GIT_TOKEN", "BUILD_SCRIPT", "PUSH_TOKEN", "ENV"):
                build_env[env_key] = str(v)
        for k, v in extra_env.items():
            build_env[k] = str(v)

        # 4. Run build script
        run(f"bash {build_script}", cwd=repo_dir, label="build", timeout=1800, env=build_env)

        results["build_script"] = build_script

        # 5. Run push script if exists and push_token provided
        push_script = params.get("push_script", "")
        if not push_script:
            for candidate in ["push.sh", "publish_app.sh"]:
                if os.path.isfile(os.path.join(repo_dir, candidate)):
                    push_script = candidate
                    break

        if push_script and push_token:
            on_stage("push", 80)
            logger.info("=== running %s ===", push_script)
            run(f"bash {push_script}", cwd=repo_dir, label="push", timeout=300, env=build_env)
            results["pushed"] = True
            results["push_script"] = push_script
        else:
            results["pushed"] = False

        results["status"] = "success"

    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
    finally:
        # Clean up container build artifacts (images, layers) to avoid state pollution
        try:
            subprocess.run("podman system prune -af 2>/dev/null || buildah prune -af 2>/dev/null",
                           shell=True, capture_output=True, timeout=30)
        except Exception:
            pass
        raise

    return results
