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
| Attempt | One Player's run of a Challenge, including simulation state, task evidence and packet history. Restart creates a new Attempt. |
| Practice pass | An on-demand simulated reception scenario shared by Ready for the Pass and Catch and Log. Scenario time is fictional, not the current real-world clock. |
| Recording | A Player-saved file of the practice pass’s received packets. It is packet data, not radio audio or IQ data. |
| Session log | Saved context, recording filename, readings and an outcome note for a practice pass. |
| Workspace | The Player's scripts, recordings, logs, notes, and supplied Challenge resources. Saved authored files survive refresh, Attempt Restart, and Challenge switching during the current session. Stop and expiry clear personal work. |
| Completion | Saved confirmation that the Player met a Challenge’s required goal. For Basic operations, the Platform verifies the task result and records completion without a Flag. |
| Debrief | The explanation shown after Challenge completion: what happened, what it teaches, and any relevant Defense. The three MVP activities teach operational foundations. |
| Defense | An optional command check for format, repetition, or authorization. The first demo leaves these off. Minimum parsing and Challenge goal checks still apply. |
| Verdict | A Defense's accept or reject decision for a message. |
| Mission | The fictional KnightSat story used for the Challenges, separate from real KSC spacecraft and the PSB station. |
| Mission role | The authority claimed inside a command, such as guest or operator. The claim alone does not authenticate the sender or grant Platform access. |
| Sandbox | Planned goal-free play with switchable Defenses. It is separate from the required Challenge Workspace. |
| MVP | The first software demo: Hello, Satellite!, Ready for the Pass, and Catch and Log in Basic operations, all with task-based completion. Offensive and Defensive Challenges are deferred. |

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
| Snapshot / revision | A complete current view / its increasing update number. Reconnect uses a snapshot to recover what was missed. |
| Authoritative state | The server's checked state, rather than an assumption made by the browser. |
| Ownership cookie / Origin | A browser token identifying the session owner / the browser page's scheme, hostname, and port. Check both where the contract requires them. |
| Tab grant / generation / revocation | Permission for one browser tab to make changes / its increasing version / cancellation of that permission. Old queued actions must fail after revocation. |
| Lock / serialize | Coordination allowing only one conflicting operation at a time / putting those operations in a definite order. |
| Atomic | Other operations see the change as one unit, not a partially applied result. |
| Async event loop / worker | The server schedules many waiting operations on an event loop. Slow blocking Docker, file, and database calls run in workers so the loop can keep responding. |
| Migration / transaction | A numbered database structure change / a group of changes that commits together or is rolled back. |
| File version / SHA-256 | A fingerprint of saved bytes / the hash algorithm used to produce it. A mismatched version prevents overwriting newer content. |
| Path traversal / symlink | Escaping an allowed folder with a path / a filesystem link to another location. Safe file APIs must prevent both from reaching unauthorized files. |
| Descriptor-relative access | Open a checked directory, then operate through its handle instead of trusting a path string that could change. Follow the Workspace rules exactly. |
| Backpressure / bounded queue | Slowing or disconnecting a producer/reader when needed / limiting buffered data so output cannot exhaust memory. |
| CI / SHA / immutable digest | Automated checks / a Git commit identifier / an exact image identifier that does not change when a tag is reused. |
| Deploy / readiness | Install a tested version on the host / confirm it is safe for the application to accept work. A running process alone is not readiness. |
| Idempotent / fail closed | Repeating an operation has no extra effect / deny new work when required checks or cleanup cannot be confirmed. |
| UUID / UTC / RFC 3339 | A standard unique ID / a shared time standard / a timestamp format such as `2026-09-21T18:00:00Z`. |
| CRC / APID / CCSDS | Packet checksum / packet application identifier / the space-data standards body whose header structure we use. See Packet format v1 for our exact convention. |

For Git branches, commits, and PRs, use the [contributor walkthrough](../CONTRIBUTING.md#the-whole-process). An unfamiliar term is a reason to ask for an example, not a reason to guess at an authorization or data-loss rule.
