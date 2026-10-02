# Backend and simulation

## Read this for server work

The **Backend** receives browser requests. The **Sim Service** runs the fictional satellite. They share one Python process but have different jobs. The Backend must not directly change the Sim's internal objects.

Start in `server/api/main.py` (currently health only). Reuse `server/api/runtime.py` and `server/api/script_bridge.py`; those infrastructure pieces exist. Add simulation work under `server/sim/`, which is currently a placeholder.

| You are building | Read first |
| --- | --- |
| Saved completion and the Challenge list | [Progress storage](#progress-storage), [storage defaults](#implementation-defaults-simulation-and-storage) |
| Ready's setup check | [Task completion](#task-completion), [browser contract](#implementation-defaults-browser-contract), [Ready interaction](ground-station-training.md#ready-for-the-pass-agreed-interaction) |
| Packet simulation | [State and commands](#state-and-commands), [operations](#operations-and-data), Packet format spec |
| Start, read and stop a session | [Browser contract](#implementation-defaults-browser-contract), [session lifecycle](#session-lifecycle) |
| Catch's pass and Check work | [Receive-only pass stream](#implementation-defaults-receive-only-pass-stream), [operations evidence](ground-station-training.md#implementation-defaults-practice-pass-and-evidence) |
| Hosting and cleanup | [Hosting defaults](#implementation-defaults-hosting) |

An API contract below lists a request and its result. For example, a client sends JSON to `POST /api/session`; the server returns the new session's state. The [glossary](../glossary.md) explains the terms.

This specification owns simulation state and commands, the Backend/Sim interface, the session lifecycle, script access and task completion. These are build requirements, not implemented code. Robustness we chose to leave out of the MVP is in [later hardening](later-hardening.md#backend-and-sessions).

This contract covers all three Basic operations Challenges. The [operations curriculum](ground-station-training.md#mvp-operations-curriculum) owns their tasks and evidence. No Flag generation, packet or submission route is part of this MVP.

## Ownership and deployment

The first demo requires a shared, team-only hosted URL as well as local Docker development. Hosted Players need only a browser; execution runs on the host. Use one dedicated Linux server running Docker Compose for the hosted demo, with one session at a time. Keep the built React interface, FastAPI/Sim, SQLite storage, and runtime controller on that server; the controller manages isolated Player execution containers.

Diab maintains the hosting environment privately. Contributors use the approved-email development site and the repository's local setup. VM configuration, private network details, and home-server procedures do not belong in this repository.

Keep the application portable to a Linux Docker host. Validate real Player workloads before claiming hosted capacity. Use only approved free hosting features; do not enable paid services without Diab's approval. Backups remain deferred; retaining a volume through an update is not off-server recovery.

This is the architecture to build, not evidence of a completed shared demo. The Compose setup described below is the local development scaffold; `compose.hosting.yml` separately validates private hosting of the existing placeholder UI and health API.

One Python server process contains FastAPI and the Sim Service, with at most one active session. The Sim Service owns Satellite Sim state, packet handling, Ground Sim, Link, the Catch pass and packet-goal evidence. FastAPI owns the session lifecycle, setup and file checks, unlocks and saved progress. FastAPI calls a Python interface on the Sim; it never edits Satellite Sim state directly. These calls return copies of data, not references to mutable simulation objects.

Browser actions use HTTP to FastAPI. The browser learns about changes by reading the session again (see [Reading session state](#reading-session-state)); the terminal uses its own WebSocket. Generate frontend HTTP request and response types from the FastAPI OpenAPI schema using `openapi-typescript`; the [Frontend HTTP client rules](frontend.md#http-api-types-and-client) define their use.

Player scripts reach the Sim Service through the restricted script bridge. The terminal PING tool uses that packet path through Ground Sim/Link, preserving supplied bytes. Ready's station form sends settings to FastAPI, not packets; the Catch pass is delivered to the Player's receiver through the Software Link.

Docker Compose starts `ui` (React development server) and `server` (FastAPI plus Sim Service). Run one server worker. SQLite in a persistent volume stores the shared demo progress.

Satellite Sim state and session packet history are in memory. No separate database server is required. The integrated terminal adds a replaceable Docker execution container, retained Workspace storage, and a terminal WebSocket.

The runtime controller and its local harness exist, but the normal two-service scaffold does not yet connect sessions to that infrastructure. The [Workspace contract](terminal-workspace.md#application-and-responsibility-boundaries) defines how it connects to the combined Backend/Sim process. Packaging the runtime-enabled application for local use and the hosted site must supply copyable launch and cleanup commands in `docs/development.md`.

## Updating the hosted demo

The shared URL is an internal development environment. After a successful `main` push CI run publishes immutable images, automatically dispatch **Update website** with that exact commit SHA. PR checks never deploy. Keep the manual workflow for retrying a tested revision. KSAT-25 implemented image publishing and automatic delivery. The existing GitHub Environment is named `production` for credential compatibility; the name does not make this a production service.

Development updates may interrupt teammate sessions, running programs and unsaved work. Session-safe deployment is [later hardening](later-hardening.md#deployment-and-sessions). Teammates should save or download work before merging changes they are testing. Access control, runtime isolation, startup cleanup and persistent database storage remain required.

Serialize replacements with cancellation disabled and an exclusive host lock. An older queued revision must not replace a newer deployed revision. GitHub may replace a pending workflow with a newer one; every intermediate commit need not reach the website.

During replacement, show temporary unavailability and retain the SQLite progress volume. A failed preflight leaves the running version intact; a replacement or readiness failure retains maintenance for attended recovery. Do not blindly roll back an incompatible database schema.

Existing startup migrations must succeed before application health reports ready.

### Development deployment boundary

Replace the historical placeholder-only application fingerprint with a fingerprint of `compose.hosting.yml`, which is installed independently on the host. Tested application, UI, dependency and image changes can deploy without individually requalifying their source. Host Compose changes still require an attended installation of the reviewed configuration; a CI build using different ports, mounts or services must not silently deploy against the old host configuration.

Deployment scripts remain root-owned and are upgraded separately. The host refuses unexpected running images and validates the selected main commit, required CI jobs, release artifact, image digests, revision and health before recording success.

The exclusive host lock and persistent maintenance marker remain. Nginx returns 503 for UI and API requests during replacement; `/health` and `/revision` are diagnostic routes behind Access. Image pulls and all release checks precede maintenance. Failure during replacement leaves the marker and pending release record for attended recovery. The progress volume is never removed. These checks prove development delivery and volume retention, not session continuity.

Use ephemeral GitHub-hosted runners over Tailscale. The automatic dispatcher has only Actions write permission and calls the existing main-only manual workflow after successful main push CI. Its token receives no host credentials.

Preserve the existing OIDC trust for the exact repository, **Update website** workflow on main, `workflow_dispatch` event and `production` environment, with only tagged-device authentication and deployment-target SSH connectivity. A production-environment SSH key invokes a root-owned forced deployment command with no shell, forwarding, Docker socket or arbitrary sudo access. Pin the verified SSH host key.

Keep the short-lived workflow token only in process input and a temporary private registry config. No paid service, self-hosted runner, public management endpoint, Access policy expansion or backup service is introduced. Diab handles private host setup and recovery.

## Hosted team access

Use Cloudflare Access with emailed one-time codes for the MVP. Allow only explicitly approved email addresses; possession of any email address does not grant entry. The access gate covers the hosted browser interface, HTTP API, and browser WebSocket connections. The hosted origin must not provide an alternate path that bypasses the gate.

This gate controls entry to the demo, not individual Platform accounts. Every approved teammate shares one progress record and the single session slot: any of them can see, use or stop the running session. Per-browser session ownership is [later hardening](later-hardening.md#browser-ownership-and-platform-busy).

Player execution uses the restricted internal script bridge with its existing per-session credential. Do not place Cloudflare administration credentials or an access-gate bypass credential in Player containers or distributed starters. Connecting scripts from a Player's own computer is deferred, so do not publish an external Player script route.

Individual Platform accounts and per-account progress belong to later work. Cloudflare Access supplies the login experience; the MVP does not implement signup, passwords, or account recovery. Use the [hosting defaults](#implementation-defaults-hosting) for routing, access sessions and deployment mechanics.

## Progress storage

Use Python's built-in `sqlite3` through one shared progress module. Use parameterized SQL and explicit transactions; no ORM or additional database-access package is required. API handlers call named operations to read completed Challenges, save completion, and reset demo progress rather than implementing database handling independently.

- Store shared demo progress in the SQLite database configured by `SQLITE_PATH`, using the persistent volume described above. Live session state and packet history remain in memory. All three MVP activities use the same Challenge completion table.
- Enforce completion uniqueness in the database so repeating a completed task cannot create duplicate records. Commit completion before reporting success. A database failure must not produce a successful completion response.
- Open, use and close a connection within one operation. Run database calls with `asyncio.to_thread` (or a plain `def` FastAPI route, which FastAPI runs in a worker) so they do not block the server.
- Track database structure changes as numbered migrations in the repository. Apply pending migrations in order at startup, recording each applied version in the database, each in one transaction. Repeated startup must not reapply completed migrations. Add a new migration when the schema changes instead of editing an applied one.

Automated backups are deferred beyond the MVP. Normal restarts and website updates must retain the SQLite progress volume. If the server's storage is lost, shared demo completion may need to be recreated.

## State and commands

State fields are `mode` (SAFE or NOMINAL), `antenna_deployed`, `deploy_count`, `heater_on`, `battery_pct`, `uptime_s`, `commands_received`, and `last_seq_seen`. Hello publishes full-state telemetry once per second; Ready has no simulator, and Catch publishes only its finite pass. Encoding, counter limits, and command replies are defined in [Packet format v1](packet-format-v1.md).

The six commands are `PING`, `GET_TELEMETRY`, `SET_MODE`, `DEPLOY_ANTENNA`, `SET_HEATER`, and `REBOOT`. Keep this existing packet vocabulary; only PING is required in the learner route. Ready/Catch are receive-only station practice, not additional command exercises. Individual Challenge specs define starting state and exact goals.

`DEPLOY_ANTENNA` marks the simulated antenna deployed and increments `deploy_count` each time it is accepted. An unchanged replay can execute again while replay detection is off. The antenna remains deployed; it does not physically unfold twice.

Message numbering and accepted-command history survive `REBOOT` within a session. A new session resets them. The [model defaults](#implementation-defaults-simulation-and-storage) define the remaining reboot effects.

## Defenses and model limits

The planned optional Defenses are format validation, replay detection, and authorization. They are off in the operations MVP; the general Defense framework is a stretch goal. Minimum safe parsing and the exact Challenge goal checks are still required.

Receiver rules for wrapped or out-of-order message numbers, authorization, and the full rejection order belong to later Defense work. A claimed Mission role does not prove identity.

Hello success does not depend on battery or uptime. The MVP requires no realistic orbital or radio physics. Use the Hello model below and the [Catch fixture](ground-station-training.md#implementation-defaults-practice-pass-and-evidence), whose recorded values determine log answers. Ground-station tracking/settings are separate from Satellite Sim spacecraft state.

## Operations and data

The Sim Service exposes these Python operations to FastAPI:

| Operation | Input | Output / meaning |
| --- | --- | --- |
| `start` | `session_id`, `challenge_id` | Create fresh Hello or Catch simulation state. FastAPI checks unlocks first. |
| `stop` | `session_id` | End timers and streams. Repeated stop is harmless. |
| `send_packet` | original `packet_bytes` from the raw script route | Record and deliver the bytes through the Link; return a receipt, not proof of acceptance. Preserve malformed bytes. Hello only; Catch refuses uplinks. Never retry automatically. |
| `start_pass` | — | Start the 12-packet Catch pass once; return the current pass if already started. Requires a connected receiver. |
| `read` | — | A copy of current spacecraft state, packet history, pass status and goal evidence. |

Return copies, not mutable service objects. Station setup and file checks are FastAPI's job; they are not part of spacecraft state.

## Task completion

The [Hello goal](challenges/01-hello-satellite.md#setup-defenses-and-exact-goal) and [operations evidence](ground-station-training.md#implementation-defaults-practice-pass-and-evidence) define success. Hello needs an accepted conforming Player PING and its correlated reply actually received through the Link. Ready needs a check of submitted settings in which every field passes. Catch needs a finished pass, a matching saved recording and a factual saved log. An HTTP receipt, browser checkbox or terminal success text is never enough.

After verifying evidence, FastAPI writes the Challenge completion to SQLite. Only committed progress unlocks the next Challenge and shows the Debrief. If the write fails, report that the task succeeded but progress was not saved, and ask the Player to repeat the check (or rerun the PING tool). An automatic Retry saving action is [later hardening](later-hardening.md#retry-saving-without-repeating-the-task).

Keep `goal_reached` (verified evidence) separate from `completion` (`not_yet`, `saved` or `save_failed`). Use one `asyncio.Lock` around session start/stop and completion saving so a Stop cannot interleave with a save. The unique database key makes repeated successful completion harmless. Starting a completed Challenge again creates fresh task state without relocking later Challenges.

## Browser API errors

Browser HTTP endpoints use one JSON error envelope with an appropriate non-success HTTP status:

```json
{
  "error": {
    "code": "CHALLENGE_LOCKED",
    "message": "Finish Hello, Satellite! first."
  }
}
```

`code` is a stable machine-readable identifier; frontend logic uses it rather than matching message text. `message` explains the failure in plain language. An optional `field_errors` array inside `error` contains `{ "field": "field_name", "message": "What to correct" }` entries for invalid input. Define this envelope in the Backend schema used to generate frontend HTTP types. Unexpected server failures use a safe generic message; diagnostic details stay in server logs.

Show failures beside the affected control or panel. Preserve entered values and unsaved drafts after a rejected operation. A missing response does not establish whether a change was applied: say the outcome is unknown and never automatically retry. These are Platform errors; Satellite Sim command replies and Defense results keep their existing packet semantics.

## Reading session state

The browser asks `GET /api/session` about once per second while a session is running, and after each of its own actions. Each response is the complete current state, including packet history and goal/completion status, so a missed response loses nothing. Reading never reruns a program, resends a packet or repeats an action.

Pushing updates over a WebSocket with numbered revisions and gap recovery is [later hardening](later-hardening.md#live-updates-and-resynchronization).

## Session lifecycle

A **session** is one run of one Challenge: a fresh Sim state, a Player container (for Hello and Catch) and its packet history. Only one session runs at a time, shared by all approved teammates.

- **Start** (`POST /api/session`) checks that the Challenge is unlocked and no session is running, then creates the Sim state, the Player container with its starter files and connection file, and binds the script bridge. Ready needs no session.
- **Read** (`GET /api/session`) returns the current state, or `null` when nothing is running.
- **Stop** (`DELETE /api/session`) revokes the script credential, stops the bridge and Sim, and destroys the container including background processes. Authored files are kept for the next session. If cleanup fails, keep the slot unavailable and report it; Stop can be repeated.

Restarting or switching Challenges is Stop followed by Start. A new session gets a new ID, credential, packet history and (for Catch) pass. Viewing another Challenge's page does not change the running session.

If the server process crashes or restarts, the unfinished session ends; saved completion remains. At startup, before reporting healthy, remove any leftover Player container and bridge belonging to this deployment ([controller handoff](terminal-workspace.md#controller-integration-handoff)). Connection loss never triggers an automatic packet resend, because retransmission can change the Challenge outcome.

Idle expiry, reopening only the terminal, and resetting the Workspace are [later hardening](later-hardening.md#lifecycle-extras).

## Script access

### Connecting a script to the session

- The Player's scripts connect through the restricted internal bridge to `/raw/attempts/{session_id}` for Hello or `/receive/attempts/{session_id}` for Catch. The existing bridge names this path segment "attempts"; the session ID fills it. These routes are only for scripts in the Workspace, not a public endpoint for a Player's own computer. The raw handler belongs to the Sim Service in the existing Python server.
- The script credential is an unpredictable secret generated for one session. Scripts read it from `/attempt/connection.json` and send it as `Authorization: Bearer <credential>` when opening the WebSocket, never in the URL or inside a Space Packet. It is distinct from the packet's claimed Mission role.
- Stop or a server failure invalidates the credential. Close old sockets and check that the session is still active before delivering queued packets, so old traffic cannot affect a new session.
- Hello permits multiple raw connections with commands processed one at a time. Catch permits one receiver; a second gets `RECEIVER_BUSY`. Ready has no script connection. A reconnect never automatically resends a command.

### Packet delivery and helper

The binary-message rules below apply to Hello’s raw connection. Catch uses the receive-only JSON stream defined in the next section.

- After authentication, one binary WebSocket message contains exactly one complete Space Packet, including header and CRC. Use message boundaries, not the packet's declared length, to delimit submissions.
- Preserve supplied bytes through Ground Sim and the Link, including intentionally incorrect headers or CRCs. Enforce the existing 256-byte maximum. Oversize submissions are rejected before Link delivery; other malformed bytes follow the minimum parsing rules in Packet format v1. Never silently fix, renumber, or retry a packet.
- Each received Satellite Sim packet is a binary WebSocket message. Text messages are reserved for Platform feedback, such as a local parsing error, and must not be presented as Satellite Sim replies. Packet history retains original bytes, direction, and time. Delivery to the Link is not proof that the command was accepted.
- Ship a small Python helper in `player/python/` and examples in `player/examples/`, preinstalled in the Player image so Players need neither the repository nor local installation.
- The helper connects, sends exact bytes, receives packets and Platform feedback, and provides the PING builder and packet decoder. Its raw-send function never rewrites bytes. Catch’s starter handles connection setup but leaves receiving, saving and selecting log readings to the Player. Byte construction utilities may be shared with the server, but no server-private configuration is included.

### Implementation defaults: receive-only pass stream

The [Workspace receive helper](terminal-workspace.md#implementation-defaults-terminal-and-helper-contracts) defines the JSON messages for Catch. Use the same bearer credential and revocation checks as raw access. The internal listener exposes only the two script routes; neither is mounted on the public browser app. Reject Player uplink data on the receive stream.

The Sim Service forwards Link-delivered telemetry, retaining original bytes and pass metadata. Browser history, helper output and the grading manifest describe the same deliveries. Report the receiver as ready only after its authenticated connection is registered. If the receiver disconnects while the pass is running, mark the pass interrupted; never silently drop records or replay the stream.

## Challenge goals

Use [Challenge progression](project-plan.md#challenge-progression) for the three server-enforced IDs and prerequisites. Exact goals belong to the Hello and operations specs.

**Correlation:** the raw handler assigns a fresh server `submission_id` and origin `raw_player` to every binary message it receives. Generated downlinks use origin `satellite`; pass packets also carry `pass_run_id` and index metadata. Never trust origin or correlation IDs supplied by a Player; these are internal history metadata, not extra packet bytes. Correlate each reply to its actual submission, not merely the reusable 14-bit wire sequence. A command can execute without meeting Hello's conformance goal; never fabricate a rejection Verdict. Repeated transmissions are deliberate new commands, with no automatic deduplication or retry.

## Implementation defaults: browser contract

Browser routes use `/api`; the script routes are never mounted on that public application. JSON field names are snake_case. Session and pass IDs are UUID strings; Challenge IDs are `hello-satellite`, `ready-for-the-pass` and `catch-and-log`. Times are UTC RFC 3339 strings, and packet bytes are lowercase hexadecimal without spaces.

**Shared records.** `Progress` is `{completed_challenge_ids: string[]}`. A `Challenge` is `{challenge_id, title, availability: available|locked, prerequisite_ids: string[], completed: boolean}`; include exactly the three MVP IDs and compute availability on the server. `Check` is `{field, passed: boolean, message}`. `StationSetup` is defined in the [Ready preparation defaults](ground-station-training.md#implementation-defaults-practice-pass-and-evidence). `PassView` is `{pass_run_id, status: not_started|running|finished|interrupted, receiver_ready: boolean, received_count: integer}`.

`HistoryEntry` is `{time, direction: uplink|downlink, packet_hex, origin: raw_player|satellite, pass_index: integer|null, feedback: {code, message}|null}`. Retain original packets including unreadable submissions. Feedback is Platform explanation, never a fabricated reply or Verdict.

`Session` is `{session_id, challenge_id, status: starting|running|failed, state, history: HistoryEntry[], pass: PassView|null, goal_reached: boolean, completion: not_yet|saved|save_failed, checks: Check[]}`. `state` uses the model fields, string mode, booleans and integer counters; `last_seq_seen` is null before any accepted command. Hello has a null pass. No bearer credential belongs in these records.

| Method and path | Request → successful response |
| --- | --- |
| `GET /api/challenges` | `{challenges: Challenge[], progress: Progress}` |
| `GET /api/challenges/ready-for-the-pass/brief` | `{scenario_id, brief: StationSetup, starting_setup: StationSetup}` |
| `POST /api/challenges/ready-for-the-pass/check` | `StationSetup` → `{checks: Check[], completion: not_yet\|saved\|save_failed}`; every field passing saves completion. Locked if Hello is not complete. |
| `POST /api/session` | `{challenge_id}` → 201 `Session` for Hello or Catch. |
| `GET /api/session` | `{session: Session\|null}` |
| `DELETE /api/session` | Stop → 204. |
| `POST /api/session/pass/start` | Catch only, `{}` → `Session`; requires a connected receiver. Never restarts an existing pass. |
| `POST /api/session/work/check` | Catch only, `{recording_path, log_path}` → `Session` with evidence checks and completion. Paths are relative to the Catch folder. |
| `POST /api/progress/reset` | `{confirm: "RESET DEMO PROGRESS"}` → `Progress`; refused while a session is running. |

Mutations and the terminal WebSocket require the request's `Origin` header, when present, to match the site's own origin. Do not enable cross-origin credentialed access.

A wrong setup or answer is a successful evaluation with failed checks, not a transport error. A verified task whose database write failed returns 503 `STORAGE_UNAVAILABLE`.

Errors use the common envelope: 403 `INVALID_ORIGIN`; 409 `SESSION_ACTIVE`, `NO_SESSION`, `CHALLENGE_LOCKED`, `WRONG_CHALLENGE`, `RECEIVER_REQUIRED`, `RECEIVER_BUSY`, `PASS_ALREADY_STARTED` or `EVIDENCE_REQUIRED`; 413 `TOO_LARGE`; 422 `INVALID_INPUT`; 503 `RUNTIME_UNAVAILABLE`, `CLEANUP_FAILED` or `STORAGE_UNAVAILABLE`. Unknown resources use 404. Disable controls that cannot work in the current state, and enforce the same rules on the server. No browser packet builder, packet-submission or Flag route is required.

Define these records once with Pydantic and generate the TypeScript types from OpenAPI. Regenerate and check in the types whenever the schema changes; a CI check for stale types is [later hardening](later-hardening.md#generated-types-ci-check).

## Implementation defaults: simulation and storage

- Use a deterministic Software Link with ordered delivery, no artificial latency, drops or contact windows. Process one command at a time. Use real reply delivery for Hello evidence. Ground Sim and downlink sender counts follow the packet spec; helper-generated raw input retains its supplied sequence; Catch uses its finite pass instead of the live timer.
- For Hello, keep battery at its initial 100%. Uptime is whole elapsed seconds since session start or the latest REBOOT. REBOOT sets SAFE, heater off and uptime zero; preserves battery, physical antenna state, deployment/accepted-command counts, goal evidence and all sequence history. It is itself an accepted command. No battery-related command gating or reboot downtime.
- The first migration creates `schema_migrations(version INTEGER PRIMARY KEY)` and `challenge_completion(challenge_id TEXT PRIMARY KEY, completed_at TEXT NOT NULL)`. There is one shared profile, so no user/account table. Completion insert ignores conflicts and keeps the first UTC completion timestamp. Reset deletes completion rows only. Each connection uses a 5-second busy timeout.
- `DEV_UNLOCK_ALL=1` makes all three Challenges available without writing completion, so Ready and Catch can be built and shown before Hello works. Use it locally and on the development site only until Hello works; turn it off before the newcomer walkthrough. Unlock rules and their tests stay in the code.
- No future lesson tables, account migrations, background job system or general Defense framework are prerequisites for the operations MVP.

## Implementation defaults: hosting

- Validate the actual application's runtime limits on the selected Linux host before the demo. Diab owns host operation; host maintenance and private network configuration are outside contributor documentation.
- Serve the built UI, `/api` and the terminal WebSocket on one origin through an Nginx Compose service. Proxy API/WebSocket traffic to the single server worker; use SPA fallback only for UI routes. Local Vite proxies `/api` (including WebSocket) to the server. Backend readiness is `/health`; return 503 until migrations and leftover-container cleanup finish.
- Use a Cloudflare Tunnel from that origin with no public application ports; keep SSH as a separate key-authenticated management path. Cloudflare Access gates the whole hostname with the approved-email list and a 6-hour session. Enable HttpOnly and binding cookies for this browser-only Access application; keep SSH on its separate Tailscale path. Restrict origin ingress to the tunnel service and validate the Access JWT at the origin against the configured audience/issuer, signature and expiry, following [Cloudflare’s validation contract](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/). Tunnel/Access configuration is operational setup, not a Player secret. If access expires, preserve drafts and explain reauthentication; never resubmit work from an access-gate redirect.
- Build revision-tagged images in GitHub Actions and pull them from GHCR. Successful main CI automatically dispatches the deployment workflow with its immutable commit; the workflow checks that exact SHA's required checks. Serialize deployments with cancellation disabled; connect over SSH using GitHub Environment secrets. No self-hosted Actions runner or Docker administration endpoint is reachable from Player code.
- A host deployment command takes an exclusive deployment lock and places a persistent maintenance marker outside the containers before replacement. Keep the database volume; verify startup readiness and the deployed revision, then clear maintenance. Development updates may interrupt sessions. Failure leaves maintenance visible for attended recovery. Access-gated Nginx serves the maintenance page even if the API is restarting.
- Before the shared demo, verify Access denial, origin bypass prevention, the terminal WebSocket, resource limits, an automatic update, and progress surviving a restart. KSAT-24 validated the host and access gate; KSAT-25 established the deployment path.

## Acceptance checks

- A successful main push CI run automatically deploys that tested revision. Failed or PR CI never deploys. The update keeps persistent progress and clears maintenance only when healthy. Concurrent updates cannot overlap or downgrade a newer deployed revision.
- Fresh database initialization and repeated startup work; a failed migration stops startup. Repeated valid completion creates one record; failed persistence never reports success or unlocks the next Challenge. Reset progress keeps the schema and migration history and is refused while a session runs.
- Locked Challenges cannot be checked or started; `DEV_UNLOCK_ALL` unlocks without saving completion.
- Start creates one session; a second Start returns `SESSION_ACTIVE`. Stop removes the container and background processes, rejects the old script credential, and keeps authored files. A failed cleanup keeps the slot unavailable.
- Browser actions and scripts use the same session; Hello replies and Catch packets in history match actual Link deliveries. Reading state never resends packets.
- Reject false completion from submission alone, incorrect settings, missing/old recordings or wrong log facts.
- A server restart ends the unfinished session, removes leftover containers and retains saved completion.
- Check every operation and raw delivery rule above, plus [Hello](challenges/01-hello-satellite.md#acceptance-examples), [operations activities](ground-station-training.md#mvp-acceptance-checks), and [Workspace checks](terminal-workspace.md#acceptance-checks).
