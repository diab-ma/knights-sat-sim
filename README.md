# Knight Sat Sim

A UCF Senior Design project for practicing satellite communication in a browser. The satellite and ground station are simulated; no real equipment is connected.

## Stack

- React, TypeScript, and Vite for the browser UI
- Python 3.12 and FastAPI for the server
- SQLite for shared progress
- Docker Compose for local development

## Run locally

### Dependencies

- Git and a code editor
- Docker Desktop, or Docker Engine with the Compose plugin on Linux
- Google Chrome for browser checks
- [KSAT Jira board](https://seniordesign-g20.atlassian.net/jira/software/projects/KSAT/boards/1) access and GitHub write access to contribute; cloning the public repository needs neither

### Quick start

```bash
git clone https://github.com/senior-design-organization/knights-sat-sim.git
cd knights-sat-sim
docker compose up --build
```

- UI: [http://localhost:5173](http://localhost:5173) — opens the workstation with Briefing previews and empty Workspace panels.
- Server: [http://localhost:8000/health](http://localhost:8000/health) — returns `{"status":"ok"}`.

Docker installs the application dependencies; local setup needs no `.env` file or private server keys. Stop with **Ctrl+C**, then run `docker compose down` (without `-v`, which deletes local data). For native setup and test commands, see [Development](docs/development.md).

Playable Challenges, terminal execution, saved files and progress are not connected yet. UI contributors can use `/dev/components` in development; see the [workstation handoff](docs/specs/frontend.md#workstation-implementation-handoff-ksat-36).

## Work on a ticket

1. On the [Jira board](https://seniordesign-g20.atlassian.net/jira/software/projects/KSAT/boards/1), take a **Ready** ticket assigned to you in the current sprint. Its prerequisites, starting point, and acceptance checks determine what to build. Ticket numbers are not an implementation order. If none is assigned, ask Diab which ticket to take next.
2. Start with the [project plan](docs/specs/project-plan.md) and its MVP statement, then read the specification sections linked by your ticket. Use the [glossary](docs/glossary.md) for project terms.
3. Follow [Contributing](CONTRIBUTING.md) for the branch, local checks, pull request, review, merge, and website check. Work on one ticket at a time; do not code directly on `main`.
