# Local development and tests

Use [README setup](../README.md#run-locally) first. Run commands from the cloned repository unless a step tells you to enter a subfolder. Commands here work in macOS/Linux terminals and PowerShell; do not copy the surrounding Markdown fences.

## Compose development

`docker-compose.yml` is the portable development configuration, not the hosted deployment. It contains both source mounts, hot reload, localhost-only published ports, and readiness checks; no machine-specific override is needed. Python's locked development dependencies live outside the source mount. The UI's named dependency volume is refreshed when `package-lock.json` changes.

```bash
docker compose up --build --detach --wait --wait-timeout 120
docker compose logs -f
```

Stop with `docker compose down`, **without `-v`**, to preserve the SQLite development database. Rebuild after Python dependency or Dockerfile changes. Keep [compose.hosting.yml](../compose.hosting.yml) separate; it does not use source mounts or development tools.

## Remote Docker (optional)

You can keep editing on a laptop while a separate Linux development machine runs Docker. SSH access, source synchronization, and localhost port forwarding are machine configuration, not repository secrets or checked-in IP addresses. Never point development or runtime checks at the shared hosted backend.

On Diab's configured Mac, from this checkout:

```bash
prodesk up
prodesk check
```

`prodesk up` syncs source, builds on the development VM, waits for readiness, and forwards the UI/API back to the usual localhost addresses. `prodesk check` syncs first, then runs the check command below on that VM. Select an area with `prodesk check server`, `prodesk check ui`, or `prodesk check runtime`; `prodesk check runtime --match bridge` selects matching runtime tests.

`prodesk dev` starts a foreground source watcher for another checkout. The configured primary checkout is already watched automatically. Use `prodesk logs -f` for logs and `prodesk down` to stop the development app without deleting its database. Other contributors can run the same checked-in Compose configuration locally or use their own SSH/sync runner; the helper is not a project dependency. Only one checkout can publish the default UI/API ports on a Docker host at a time.

A remote Docker context alone does **not** share laptop folders. Run Compose and checks beside the synchronized checkout on the development VM, or use a runner that handles synchronization. Runtime checks require the Docker host's socket and bind paths.

## Containerized checks

With Docker running, one command runs Python lint/type checks and unit tests, UI lint/tests/build, then the real Player-runtime harness:

```bash
python3 scripts/check.py
```

Use `python` in PowerShell. Choose `server`, `ui`, or `runtime` as an argument for focused work. These checks use locked dependencies in disposable containers; Python/Node test dependencies and build outputs need not be installed on the laptop. The ordinary check containers have no application-data volumes, source mounts, or Docker socket. Runtime tests use only their dedicated harness described below.

The runner removes its check containers/networks after success or failure. Only the disposable runtime harness uses volume-deleting cleanup; it never prunes Docker or deletes the ordinary development database. A host-wide runtime lock prevents concurrent harness runs across checkouts. After a hard interruption, inspect the labelled runtime containers before removing a stale `knightsat-ksat11-test.lock` directory from that Docker host's temporary directory.

## Run without Compose

This option is useful when your editor needs local dependencies. Install **Python 3.12**, **uv** (the Python dependency tool), and **Node.js 22** (includes npm). These match our container/CI versions. Docker is still required for real Player runtime tests.

If Compose is already running, stop it first so ports 8000 and 5173 are free. Open two terminals in the repository.

In the first terminal:

```bash
cd server
uv sync --extra dev
uv run uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

In the second terminal:

```bash
cd ui
npm ci
npm run dev
```

Open the same UI and health addresses from the README. Ctrl+C stops each process. `uv sync` and `npm ci` install the versions in the checked-in lockfiles. Keep lockfile changes intentional; do not upgrade packages just to get started.

The current scaffold permits the UI's localhost origin through CORS (the browser's cross-origin access rules). The Challenge-list work will add the same-origin Vite proxy for `/api` (including the terminal WebSocket). Do not assume that proxy exists yet.

## Tests and lint

**Tests** run examples and check their results. **Lint/type checks** catch likely code mistakes. Run the commands for the area changed; read and fix failures before pushing. Documentation-only changes need link/command review and normal PR CI, not artificial feature tests.

From a fresh terminal in the repository, check the server:

```bash
cd server
uv sync --extra dev
uv run ruff check .
uv run mypy --ignore-missing-imports api
uv run pytest
```

From another fresh terminal in the repository, check the UI:

```bash
cd ui
npm ci
npm run lint
npm test
npm run build
```

Each command should exit successfully. Pytest reports passed/skipped tests; Vitest reports passed tests; the UI build produces `ui/dist/`. Ordinary pytest skips tests that need the dedicated Docker harness below. A skipped runtime test is not proof of isolation or cleanup.

Deployment-tool changes also need, from the repository root:

```bash
python3 deploy/test_release.py
python3 deploy/test_check_hosting.py
```

Use `python` instead of `python3` if that is your Python 3 command. CI additionally checks real hosted-container routing/protections and the pinned Cloudflare validator; the commands are in [ci.yml](../.github/workflows/ci.yml).

### Test one behavior while editing

Run a focused test first, then the relevant full checks above before the PR:

```bash
# From server/:
uv run pytest tests/test_health.py -v
```

For new behavior, write a small test of the expected result, including the failure case that could lose data or grant the wrong access. Get expected values from the owning specification. Do not change a test's expected result just to make it pass.

If a check fails only on your computer, include the command, error, OS, and tool versions in the ticket. Ask the relevant teammate before working around an isolation or cleanup failure.

## Local Player runtime checks (KSAT-11)

This is for changes to the controller, bridge, or Player image. It runs **real local Docker containers**. Browser Start/Stop and real Sim integration belong to the session work and are not provided by this harness.

From the repository root with Docker running (or `prodesk check runtime` on the configured remote development machine):

```bash
python3 scripts/check.py runtime
```

The runner builds the Player image and locked test image, runs the tests, then uses `docker compose -p ksat11-test -f compose.runtime-test.yml down -v` to delete **only this disposable harness's** volumes and network. Those project/file selectors matter. Never replace them with a broad Docker prune or use `down -v` on your ordinary development stack.

Run the harness serially: its three named volumes are shared by the test deployment. To select tests, use `python3 scripts/check.py runtime --match NAME`, replacing `NAME` with part of a test name. An expression matching no tests returns a nonzero result, not a passing check.

The trusted test server mounts the local Docker socket; the Player container never receives it. The authored, managed, and bridge storage volumes are bounded in-memory filesystems. Runtime replacement preserves authored contents; ending a session removes personal data and all execution, including detached processes.

If a test is interrupted, inspect only containers labelled `org.knightsat.deployment=ksat11-test`. Record their runtime IDs and deliberately remove those test containers before deleting the harness volumes. Ask Diab for help if cleanup fails. Never treat failed cleanup as a free Player slot.

The [controller integration handoff](specs/terminal-workspace.md#controller-integration-handoff) defines how application code uses this infrastructure. The harness verifies infrastructure; it does not prove complete browser or Challenge behavior.
