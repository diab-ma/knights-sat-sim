# Knight Sat Sim

A **Platform** for practicing satellite cybersecurity and learning ground-station operation, including the station at UCF’s Physical Sciences Building (PSB). **Players** practice with simulated systems and learn the equipment and workflow used at PSB.

This repository is **Knight Sat Sim (KSS)**, the UCF CS Senior Design implementation of that Platform. The product has three tracks: **Basic operations**, **Offensive**, and **Defensive**. The first version to build (MVP) focuses on **three Basic operations Challenges**, **Hello, Satellite!**, **Ready for the Pass**, and **Catch and Log**. Completion is based on performing the tasks, without submitting Flags. The specs define the agreed learning flow and implementation defaults. Offensive and Defensive Challenges come later. Practice remains browser-based, without live station-hardware integration. See the [ground-station training plan](docs/specs/ground-station-training.md).

Start with the [project plan](docs/specs/project-plan.md) for scope, responsibilities, progression, and completion checks. Its [build specifications](docs/specs/project-plan.md#build-specifications) table links to the implementation and learning documents. Each spec owns its decisions; research provides supporting sources, not additional MVP requirements.

## Repository layout

| Path | Contents |
| --- | --- |
| `server/sim/` | Sim Service, packet handling, Ground Sim, and Software Link |
| `server/api/` | FastAPI Web Backend |
| `ui/` | React and TypeScript frontend |
| `docs/specs/` | Current scope, architecture, behavior, and acceptance checks |
| `docs/research/` | Supporting sources and technical findings |

The repository currently contains a scaffold. Running it starts the frontend and backend health endpoint; it does not provide the planned Challenges, terminal, database behavior, or station lessons yet.

## Run locally

You need Docker. From the repository root:

```bash
docker compose up --build
```

- Browser UI: http://localhost:5173
- Web Backend health check: http://localhost:8000/health

Compose starts the React development server and **one** Python process that will contain FastAPI and the Sim Service. The `sqlite-data` volume is reserved for the planned SQLite progress database. Do not run extra server workers: the MVP Attempt lives in memory in that single process.

Without Docker:

- Server: Python 3.12+, from `server/`: `uv sync` then `uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000` (still one worker).
- UI: Node 22+, from `ui/`: `npm install` then `npm run dev`.

## Tests and lint

```bash
# server
cd server && uv sync --extra dev && uv run ruff check . && uv run pytest

# ui
cd ui && npm ci && npm run lint && npm test
```

Pull requests run the same checks in GitHub Actions.

## How we work

Jira holds build tickets. Open a branch named with the Jira key, open a pull request whose title starts with that key, wait for CI, and get one teammate review before merge. Details: [`CONTRIBUTING.md`](CONTRIBUTING.md).


## Local Player runtime checks (KSAT-11)

The isolated runtime controller is available to server code; browser Start/Stop and
production Sim wiring remain KSAT-12. The default development and hosted services
still serve the scaffold. This harness uses **local Docker only** and does not
change the hosted demo or its deployment fingerprint.

```bash
docker build -t knightsat-player:ksat11 player
docker compose -p ksat11-test -f compose.runtime-test.yml build
docker compose -p ksat11-test -f compose.runtime-test.yml run --rm runtime-tests
# Remove only the disposable harness volumes/network after the tests finish:
docker compose -p ksat11-test -f compose.runtime-test.yml down -v
```

Run one behavior by appending `pytest tests/runtime/test_controller.py -k <name> -v`
to the `run --rm runtime-tests` command. Run the harness serially: its three named
volumes belong to one test deployment. The trusted test server has the local Docker
socket; the Player never receives it. The test image uses the server lockfile.
Ordinary `uv run --extra dev pytest` skips real-container checks without the harness
environment; CI runs them in a dedicated required-for-publishing job. Typecheck with
`uv run --extra dev mypy --ignore-missing-imports api` from `server/`.

The harness's three deployment-labelled named volumes are bounded tmpfs and remain
mounted in the trusted server throughout each test. Runtime replacement preserves
authored contents. Session cleanup empties personal data and removes execution,
including detached processes, temporary/home files and the PTY. Empty infrastructure
volumes remain attached until `down -v`; they contain no retained personal data.
Do not use a broad Docker prune command. If a test process is killed, inspect only
containers with `org.knightsat.deployment=ksat11-test`, record their runtime labels,
and deliberately remove those identified test containers before removing the
harness volumes. A failed cleanup must not be treated as successful admission.

Local evidence, 2026-09-29 UTC: Docker Desktop 4.93.0, Engine 29.8.1,
Linux ARM64, 10 CPUs / approximately 7.75 GiB Docker VM memory. Real Player probes
verified UID/GID 1000, network none, read-only root/resources, dropped capabilities,
no-new-privileges and 0.5 CPU / 128 MiB / no extra swap / 64 processes / 256 descriptors.
Observed exhaustion: authored/tmp/home writes stopped at 67,108,864 / 16,777,216 /
4,194,304 bytes; managed and bridge storage rejected writes beyond 1 MiB; process
creation and descriptor opens hit kernel limits; CPU throttling occurred; an
unbounded allocator was killed with status 137. Exact available child/descriptor
counts include the shell and bridge overhead, so they may vary.

The checks also cover retained authored files, fresh read-only managed context,
non-overwriting/symlink-safe provisioning, quota-failure recovery, detached-child
removal, failed/lost Docker responses, cancellation during creation, abandoned
runtime refusal, foreign-resource preservation, denied IPv4/IPv6 egress/private
paths, direct-socket and loopback authentication, denied non-script routes, revoked
queued traffic, receive routing and the 256-byte input bound. Bridge fixtures
prove infrastructure transport only; they do not claim Sim/Link completion or
receiver readiness. No browser journey or HP x86-64 hosted capacity was tested here.

Final local verification: all 20 server tests passed with real Docker, plus the UI
test/build, Python/TypeScript type checks, lint and five deployment-tool regression
checks. Standards and spec reviews found no remaining issues after the close-race
and cleanup-fault regressions were added.

KSAT-12 supplies real Sim handlers, browser ownership and the shared lifecycle lock;
KSAT-37 supplies startup reconciliation, maintenance and readiness. KSAT-13 drains
the existing PTY into its bounded terminal buffers. KSAT-17/20 extend
`player/python/kss_client.py` and provide the authored starter/managed scenario bytes;
this image currently supplies `load_connection()` and pinned `websockets`, not a
PING solver or completed recording. See the controller handoff in the
[Workspace spec](docs/specs/terminal-workspace.md#controller-integration-handoff).
