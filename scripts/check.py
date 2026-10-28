#!/usr/bin/env python3
"""Run the repository's checks in disposable containers on this Docker host."""

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PROJECT = "ksat11-test"


def run(*args):
    print("+ " + shlex.join(str(arg) for arg in args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def output(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def require_local_engine():
    # Runtime bind mounts must refer to files on the daemon host. A remote
    # context alone does not sync source; the SSH runner executes this script
    # beside its synced checkout instead.
    endpoint = os.environ.get("DOCKER_HOST") or output(
        "docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"
    )
    if not endpoint.startswith(("unix://", "npipe://")):
        raise RuntimeError(
            "Run checks on the Docker host (for example: prodesk check)."
        )


@contextmanager
def runtime_lock():
    # All checkouts share the harness's fixed volume names and Player image.
    # Atomically exclude concurrent harness runs on this Docker host.
    path = Path(tempfile.gettempdir()) / "knightsat-ksat11-test.lock"
    try:
        path.mkdir(mode=0o700)
    except FileExistsError as error:
        raise RuntimeError(
            f"Runtime checks are already locked at {path}. If interrupted, inspect "
            "the ksat11-test containers before deliberately removing the stale lock."
        ) from error
    try:
        (path / "owner.json").write_text(
            json.dumps({"pid": os.getpid(), "checkout": str(ROOT)})
        )
        yield
    finally:
        (path / "owner.json").unlink(missing_ok=True)
        path.rmdir()


def ordinary_checks(areas):
    suffix = hashlib.sha256(str(ROOT).encode()).hexdigest()[:10]
    compose = [
        "docker", "compose", "-p", f"knightsat-check-{suffix}",
        "-f", str(ROOT / "docker-compose.yml"), "--profile", "checks",
    ]
    try:
        for area in areas:
            run(*compose, "run", "--rm", "--build", "--no-deps", f"{area}-check")
    finally:
        # No -v: never remove application data as a side effect of lint/tests.
        run(*compose, "down")


def runtime_checks(match):
    compose = [
        "docker", "compose", "-p", RUNTIME_PROJECT,
        "-f", str(ROOT / "compose.runtime-test.yml"),
    ]
    with runtime_lock():
        for label in (f"org.knightsat.deployment={RUNTIME_PROJECT}",
                      f"com.docker.compose.project={RUNTIME_PROJECT}"):
            if output("docker", "ps", "-aq", "--filter", f"label={label}"):
                raise RuntimeError(
                    "Existing ksat11-test containers need inspection before a new run."
                )
        try:
            run(
                "docker", "build", "-t", "knightsat-player:ksat11", str(ROOT / "player")
            )
            run(*compose, "build")
            pytest = ["pytest", "tests/runtime", "-v"]
            if match:
                pytest.extend(["-k", match])
            run(*compose, "run", "--rm", "runtime-tests", *pytest)
        finally:
            # These three bounded tmpfs volumes belong only to the disposable
            # harness. Keep its explicit project/file selectors on cleanup.
            run(*compose, "down", "-v")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "area", nargs="?", choices=["all", "server", "ui", "runtime"], default="all"
    )
    parser.add_argument("--match", help="Only run matching runtime tests (pytest -k)")
    args = parser.parse_args()
    if args.match and args.area != "runtime":
        parser.error("--match requires the runtime area")
    require_local_engine()
    if args.area in ("all", "server", "ui"):
        ordinary_checks(["server", "ui"] if args.area == "all" else [args.area])
    if args.area in ("all", "runtime"):
        runtime_checks(args.match)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Checks failed: {error}", file=sys.stderr)
        sys.exit(getattr(error, "returncode", 1))
