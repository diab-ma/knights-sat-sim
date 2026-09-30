# Knight Sat Sim

Knight Sat Sim is a UCF Senior Design project for practicing satellite communication in a browser. The satellite and ground station are simulated; this software does not connect to real equipment.

## Run locally

Install Git, a code editor, and Docker Desktop (or Docker Engine with the Compose plugin on Linux). Start Docker and wait for it to be ready. Use current desktop Google Chrome when you check browser behavior. Local setup needs no `.env` file or server keys.

The repository is public, so you can clone it without signing in. In a terminal, run:

```bash
git clone https://github.com/senior-design-organization/knights-sat-sim.git
cd knights-sat-sim
docker compose up --build
```

The first build can take several minutes. Leave the terminal open. If you use GitHub Desktop, clone by URL, then open a terminal in that folder and run the Compose command.

On your computer, check:

- [The browser page](http://localhost:5173) shows “Satellite Security Challenge Platform.” A placeholder page is expected.
- [The server health check](http://localhost:8000/health) shows `{"status":"ok"}`.

Press **Ctrl+C** to stop, then run `docker compose down` from the repository folder. Do not add `-v`: it deletes local stored data. UI edits reload automatically; after server or dependency changes, run `docker compose up --build` again.

If setup fails, check that Docker is running and that you are in the folder with `docker-compose.yml`. For more detail, run `docker compose ps` and `docker compose logs --tail=100`. If ports 5173 or 8000 are busy, stop the other app using them. The [development guide](docs/development.md) has native setup and test commands.

## Start an assigned ticket

1. Get access to the [KSAT Jira board](https://seniordesign-g20.atlassian.net/jira/software/projects/KSAT/boards/1) and ask Diab for GitHub write access before you need to push. Sign in with GitHub Desktop or your Git credential manager. You do not need private server access or AI tools.
2. Choose a ticket **assigned to you** in **Ready**. Read its goal, starting point, and acceptance checks. If it is blocked, tell the owner and link the blocking ticket. Do not guess from ticket numbers; the board and its dependency links show what can start.
3. Read the [project plan](docs/specs/project-plan.md) and the specification sections linked in your ticket. Use the [glossary](docs/glossary.md) for unfamiliar project terms. The [documentation map](docs/README.md) points to other details only when you need them.
4. Follow [Contributing](CONTRIBUTING.md) to make a branch with the Jira key, implement and test your change, open a pull request, get review, merge, check the shared development website, and move the ticket to Done. Do not implement directly on `main`.

Start with one implementation ticket at a time. Ask the owner of a shared interface before changing it. Jira holds current work status; specifications describe the behavior to build.
