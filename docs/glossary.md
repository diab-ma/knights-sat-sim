# Project glossary

Knight Sat Sim teaches satellite cybersecurity and ground-station operation, including the PSB station at UCF. Use these names consistently in specs. Explain them in plain language in Player-facing material.

| Term | Meaning |
| --- | --- |
| Platform | The whole product: browser interface, backend, simulation, cybersecurity Challenges, station lessons, and saved progress. |
| Player | A person practicing activities in any of the three tracks. |
| Track | A learning path grouping related Challenges: Basic operations, Offensive, or Defensive. Only Basic operations is in the MVP. |
| Satellite Sim | Software that receives commands, holds simulated spacecraft state, sends telemetry and replies, and supplies packet evidence for Challenge completion. |
| Ground Sim | The software that handles the ground side of messages sent to and received from the Satellite Sim. It is not the real PSB station or a complete station operations trainer. |
| Ground station | The real equipment and software used to track satellites and receive or send signals. Our training focuses on UCF's Physical Sciences Building (PSB) station. |
| Station lesson | Ground-station instruction and practice within Basic operations. A lesson may support a Challenge. The three MVP activities use the shared task-based completion model. |
| Link | The message path between Ground Sim and Satellite Sim. The Software Link is used for the first demo. The later RF Link would carry messages through station radios on a cabled bench. |
| Packet | A structured message with a header, body, and checksum. The [packet spec](specs/packet-format-v1.md) defines the bytes. |
| Telemetry | A status report from the Satellite Sim, such as battery level or antenna state. |
| Packet decoder | A tool that interprets packet bytes as named fields. The MVP supplies this tool; interpreting packets is distinct from recovering them from a radio signal. |
| Challenge | A practical learning activity within a track, with a Briefing, an observable goal and a Debrief. Basic operations Challenges use task-based completion, without Flag submission; exact success criteria belong to each spec. |
| Briefing | The story and goal shown before a Challenge. |
| Session | One run of one Challenge: simulation state, the Player container, task evidence and packet history. Only one runs at a time, shared by the team. Stop then Start creates a new session. Older documents and the existing script bridge call this an **Attempt**. |
| Practice pass | A simulated reception scenario described by Ready for the Pass and received in Catch and Log, started on demand. Scenario time is fictional, not the current real-world clock. |
| Recording | A Player-saved file of the practice pass’s received packets. It is packet data, not radio audio or IQ data. |
| Session log | Saved context, recording filename, readings and an outcome note for a practice pass. |
| Workspace | The Player's scripts, recordings, logs, notes, and supplied Challenge resources. Saved authored files survive refresh, Stop and Start, and Challenge switching. A host restart may erase them. |
| Completion | Saved confirmation that the Player met a Challenge’s required goal. For Basic operations, the Platform verifies the task result and records completion without a Flag. |
| Debrief | The explanation shown after Challenge completion: what happened, what it teaches, and any relevant Defense. The three MVP activities teach operational foundations. |
| Defense | An optional command check for format, repetition, or authorization. The first demo leaves these off. Minimum parsing and Challenge goal checks still apply. |
| Verdict | A Defense's accept or reject decision for a message. |
| Mission | The fictional KnightSat story used for the Challenges, separate from real KSC spacecraft and the PSB station. |
| Mission role | The authority claimed inside a command, such as guest or operator. The claim alone does not authenticate the sender or grant Platform access. |
| Sandbox | Planned goal-free play with switchable Defenses. It is separate from the required Challenge Workspace. |
| MVP | The version we promise to finish: Hello, Satellite!, Ready for the Pass, and Catch and Log in Basic operations, all with task-based completion. The [project plan](specs/project-plan.md#mvp-what-done-means) lists what is required and what is a stretch goal. |
| Stretch goal | Work we would like to do but do not promise, such as the Offensive and Defensive tracks and PSB station lessons. |
| Later hardening | Robustness deliberately left out of the MVP, listed in [later hardening](specs/later-hardening.md). |

See the [project plan](specs/project-plan.md) for scope and the [station training plan](specs/ground-station-training.md) for PSB lessons. Definitions of future features do not make those features part of the first demo.

## Development terms

| Term | Plain-language meaning |
| --- | --- |
| API / endpoint | A defined way for programs to talk. An endpoint is one address and operation, such as `GET /health`. |
| HTTP / WebSocket | HTTP sends a request and receives a response. WebSocket keeps a connection open for live messages. |
| Frontend / Backend | Browser code the user interacts with / server code that checks requests and performs work. |
| Contract / schema | Agreement about data and behavior / the definition of the data's fields and types. |
| OpenAPI / generated types | A description exported by FastAPI / TypeScript definitions made from it so both sides agree. Do not hand-edit generated files. |
| JSON / JSON Lines | Text containing named data fields / a file with one JSON object on each line. |
| Fixture / test double | Known example input / a substitute for another component during a focused test. Neither proves real integration. |
| Integration / acceptance check | Testing connected parts / demonstrating the ticket's required observable result. |
| Image / container / runtime | A packaged program and dependencies / a running instance of that image / the Player's current running environment. |
| Docker Compose / volume | A configuration that starts related containers / storage mounted into containers. Some volumes are persistent; our Player tmpfs volumes are temporary. |
| tmpfs / quota | A filesystem held in memory / its maximum permitted size. Restarting the host may erase tmpfs. |
| PTY / terminal gateway | A pseudo-terminal that lets a program act like an interactive shell / the server code connecting that shell to the browser. |
| Polling | The browser asking the server for the current state again every second or so, instead of the server pushing changes. |
| Authoritative state | The server's checked state, rather than an assumption made by the browser. |
| Origin | The browser page's scheme, hostname, and port. The server refuses changes from a different Origin. |
| Lock | Coordination allowing only one conflicting operation at a time, such as Start and Stop. |
| Async event loop / worker | The server schedules many waiting operations on an event loop. Slow blocking Docker, file, and database calls run in workers so the loop can keep responding. |
| Migration / transaction | A numbered database structure change / a group of changes that commits together or is rolled back. |
| Path traversal / symlink | Escaping an allowed folder with a path such as `../` / a filesystem link to another location. The file routes must refuse both. |
| CI / SHA / immutable digest | Automated checks / a Git commit identifier / an exact image identifier that does not change when a tag is reused. |
| Deploy / readiness | Install a tested version on the host / confirm it is safe for the application to accept work. A running process alone is not readiness. |
| Idempotent / fail closed | Repeating an operation has no extra effect / deny new work when required checks or cleanup cannot be confirmed. |
| UUID / UTC / RFC 3339 | A standard unique ID / a shared time standard / a timestamp format such as `2026-09-21T18:00:00Z`. |
| CRC / APID / CCSDS | Packet checksum / packet application identifier / the space-data standards body whose header structure we use. See Packet format v1 for our exact convention. |

Terms used only in [later hardening](specs/later-hardening.md), such as ownership cookie, tab generation, revision, file version and descriptor-relative access, are explained there.

For Git branches, commits, and PRs, use the [contributor walkthrough](../CONTRIBUTING.md#the-whole-process). An unfamiliar term is a reason to ask for an example, not a reason to guess at an authorization or data-loss rule.
