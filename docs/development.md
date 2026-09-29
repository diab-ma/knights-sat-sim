# Local development and tests

Use [README setup](../README.md#run-locally) first. Run commands from the cloned repository unless a step tells you to enter a subfolder. Commands here work in macOS/Linux terminals and PowerShell; do not copy the surrounding Markdown fences.

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

The current scaffold permits the UI's localhost origin through CORS (the browser's cross-origin access rules). KSAT-9 will add the same-origin Vite API/WebSocket proxy needed by the session features. Do not assume that proxy exists yet.

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

This is for changes to the controller, bridge, or Player image. It runs **real local Docker containers**. Browser Start/Stop and real Sim integration belong to KSAT-12 and are not provided by this harness.

From the repository root with Docker running:

```bash
docker build -t knightsat-player:ksat11 player
docker compose -p ksat11-test -f compose.runtime-test.yml build
docker compose -p ksat11-test -f compose.runtime-test.yml run --rm runtime-tests
docker compose -p ksat11-test -f compose.runtime-test.yml down -v
```

The final command deletes **only this disposable harness's** volumes and network. Its `-p ksat11-test -f compose.runtime-test.yml` options matter. Never replace it with a broad Docker prune or use `down -v` on your ordinary development stack.

Run the harness serially: its three named volumes are shared by the test deployment. To select a test, append `pytest tests/runtime/test_controller.py -k NAME -v` to the `run --rm runtime-tests` command, replacing `NAME` with part of a test name.

The trusted test server mounts the local Docker socket; the Player container never receives it. The authored, managed, and bridge storage volumes are bounded in-memory filesystems. Runtime replacement preserves authored contents; ending a session removes personal data and all execution, including detached processes.

If a test is interrupted, inspect only containers labelled `org.knightsat.deployment=ksat11-test`. Record their runtime IDs and deliberately remove those test containers before deleting the harness volumes. Ask Diab for help if cleanup fails. Never treat failed cleanup as a free Player slot.

The [controller integration handoff](specs/terminal-workspace.md#controller-integration-handoff) defines how application code uses this infrastructure. The harness verifies infrastructure; it does not prove complete browser or Challenge behavior.
