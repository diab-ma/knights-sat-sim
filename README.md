# Knight Sat Sim

A UCF Senior Design project for practicing satellite communication in a browser. The satellite is simulated: this demo does not connect to a real spacecraft or radio.

The first version has three planned activities: **Hello, Satellite!** (send PING and inspect the reply), **Ready for the Pass** (configure a receiving station), and **Catch and Log** (use Python to receive and save simulated telemetry).

## Start here

You do not need AI, an agent, radio equipment, or server access to contribute. You need a code editor, Git, Docker, and access to the team's GitHub repository and Jira board.

1. Follow **Run locally** below and check the expected result.
2. Read the short [project plan](docs/specs/project-plan.md) to understand the parts and team responsibilities.
3. Follow [Contributing](CONTRIBUTING.md) to take one Jira ticket through a branch, tests, pull request, and deployment.
4. Read only the specification sections linked by your ticket. The [documentation map](docs/README.md) explains where to find details.

## What works today

As of 2026-09-29:

| Available | Still being built |
| --- | --- |
| Local UI placeholder and server health check | Challenge pages, saved progress, and browser session controls |
| Isolated Player runtime controller, with real Docker tests | Browser terminal, editor, files, and their application integration |
| Automatic deployment after successful checks on `main` | The three complete learning activities and final hosted acceptance |

A placeholder page is the expected result of setup. Specifications describe the product to build; they are not claims that all features work. Jira is the source for current ticket status.

## Run locally

Install Git and Docker Desktop for your operating system. Start Docker Desktop and wait until its engine is running. On Linux, Docker Engine with the Compose plugin also works.

Open a terminal in the folder where you keep projects, then run:

```bash
git clone https://github.com/senior-design-organization/knights-sat-sim.git
cd knights-sat-sim
docker compose up --build
```

If you already cloned the project, open a terminal in that folder and run only the last command. The first build downloads dependencies and may take several minutes. Leave this terminal running.

Open these addresses on **your computer**:

- [UI: localhost:5173](http://localhost:5173) — a page headed “Satellite Security Challenge Platform.”
- [Server check: localhost:8000/health](http://localhost:8000/health) — `{"status":"ok"}`. This confirms the server responds; it does not test the planned Challenges.

Use current stable desktop Google Chrome for required browser checks. The planned workstation targets windows at least 1280 pixels wide.

To stop, press **Ctrl+C** in the running terminal, then run `docker compose down`. Do **not** add `-v` to this normal development command: that would delete its stored volumes, including future local progress.

UI source edits reload automatically. After server or dependency changes, stop and run `docker compose up --build` again. Keep one Python server worker; session state will live in that process.

### If setup fails

| Symptom | Next step |
| --- | --- |
| `git` or `docker` not found | Install the missing tool, then reopen the terminal. |
| Cannot connect to the Docker daemon | Start Docker Desktop and wait for the engine. |
| No configuration file found | Run `pwd` (PowerShell: `Get-Location`). Change into the cloned folder containing `docker-compose.yml`. |
| Port 5173 or 8000 is already in use | Stop the other development copy or application using that port, then retry. |
| Page unavailable | Keep Compose running; inspect `docker compose ps` and `docker compose logs --tail=100`. |
| Docker build fails | Read the first error above the final failure. Share that error and your OS with a teammate; remove secrets before sharing logs. |

For an editor with local dependencies, or to work without Docker for UI/API changes, see [native development](docs/development.md#run-without-compose).

## Tests and lint

Run the [test commands](docs/development.md#tests-and-lint) for the area you changed before opening a pull request. That guide includes Python/Node setup, expected results, and the separate real-container runtime tests. A successful website startup alone is not a test pass.

## Repository layout

| Path | What belongs here |
| --- | --- |
| `ui/src/` | React/TypeScript browser interface; currently a small placeholder |
| `server/api/` | Python HTTP API and existing runtime/bridge infrastructure |
| `server/sim/` | Planned simulation and packet code; currently a placeholder |
| `server/tests/` | Server tests, including the real Docker runtime harness |
| `player/` | Image and helper library for the Player's isolated Python environment |
| `deploy/`, `.github/workflows/` | Hosting checks and automatic build/deployment |
| `docs/specs/` | Agreed behavior, shared interfaces, and acceptance checks |
| `docs/research/` | Background sources; not extra work for the first demo |

The [glossary](docs/glossary.md) explains project and development terms. The [documentation map](docs/README.md) separates everyday contributor instructions from detailed specifications and server administration.

## How we work

Use [Jira](https://seniordesign-g20.atlassian.net/jira/software/projects/KSAT/boards/1), not GitHub Issues, for build tickets. Keep each ticket small, use a short-lived branch, and agree on shared API shapes before implementing both sides. Follow the [complete contributor workflow](CONTRIBUTING.md).

A merge to `main` runs automated checks, publishes tested images, and triggers **Update website**. The [shared website](https://knightsat.radio-ranger.com) is for internal development and requires an approved email address. Updates may interrupt sessions or unsaved work. The GitHub environment is named `production` for historical configuration reasons; this is still a development site.

## Local Player runtime checks (KSAT-11)

The [runtime test guide](docs/development.md#local-player-runtime-checks-ksat-11) runs disposable local containers. It does not change the shared website.

Diab handles hosting privately. Contributors only need the PR/deployment workflow above; private server administration does not belong in this repository.
