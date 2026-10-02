# Integrated terminal and Workspace — implementation spec

## Read this for Workspace work

Think of the Workspace as two parts: **saved files** and a **running Linux environment** (the Player container). Stopping the container must not erase saved files.

The controller already exists in `server/api/runtime.py`; its script bridge is in `server/api/script_bridge.py`. The browser terminal, file saving and editor are still application work.

| Part | Builds on |
| --- | --- |
| Terminal WebSocket on the server | The controller's existing shell connection (`RuntimeController.terminal`) |
| Terminal panel in the browser | xterm.js and the terminal WebSocket |
| File read and save on the server | The authored Workspace folder the controller already creates |
| Editor panel in the browser | CodeMirror 6, the shared controls and the file read/save routes |
| File browser, notes and downloads (after the three Challenges work) | The same file routes |

Start with the [session lifecycle](#session-lifecycle), then the interface section for your part. The [glossary](../glossary.md) explains PTY, runtime and other terms. Robustness we chose to leave out of the MVP is in [later hardening](later-hardening.md#terminal-and-workspace).

Status: agreed requirements. The runtime controller and bridge are implemented; the terminal, file and editor integrations remain feature work.

Start with the [project plan](project-plan.md). This file owns terminal execution, shared files and Player containers for the operations MVP. The [operations curriculum](ground-station-training.md#mvp-operations-curriculum) owns the three MVP learning activities.

## Problem Statement

The Player needs to read a Challenge, edit and run a script, and understand the Satellite Sim's response without leaving the Platform or installing local tools.

## Solution

Provide a real Linux terminal and file editor inside the website, with Python, the public helper, and useful file-inspection tools prepared in advance. The terminal and editor share saved files. The Player still performs the scripting task; the Platform supplies the environment with connection boilerplate and a supplied decoder for Catch and Log.

Use a replaceable Docker execution container with retained Workspace storage and a terminal WebSocket. Keep the Web Backend and Sim Service together in their existing Python process. Explicit Save writes a file; saving is never automatic.

The first deployment is internal-team-only and must be available at a shared hosted URL, with Player execution on the host. Local Docker development remains supported. Hosting and access follow the [Backend deployment section](backend-and-simulation.md#ownership-and-deployment).

The general shell can reach only the Platform's script routes. Hello uses a supplied terminal command to send PING and inspect its reply, without requiring the Player to write Python. Catch and Log uses a short Python starter to receive, record and interpret the practice pass.

## Implementation Decisions

### Application and responsibility boundaries

- Use the [three-pane desktop layout](frontend.md#layout-and-screen-support): Challenge navigation, a central Workspace pane containing the terminal/editor and active tools, and the Challenge guide on the right. Preserve readable labels and keyboard focus, and keep the distinction between sending a packet, receiving a reply, verified task evidence and saved completion.
- Integrate xterm.js into the React interface. The terminal WebSocket connects the browser to the container's existing shell. Reconnecting is not executing a new command. Terminal output is untrusted display data.
- FastAPI owns the session lifecycle, completion checks and SQLite progress. The Sim Service owns packets, Ground Sim, the Software Link, Satellite Sim state and goal detection in the same Python process. Terminal and filesystem work does not move into the Satellite Sim.
- The runtime controller creates and destroys the Docker execution container and manages Workspace storage and the per-session connection files. Player code receives no infrastructure-control interface.

### Execution, storage, and endpoint isolation

These container protections are already built and remain required.

- Player scripting runs inside the website's Workspace only. Scripts on a Player's own computer are deferred. Keep the raw and receive routes behind the restricted internal bridge.
- One Player container runs at a time: a prepared non-root Linux image with shell, Python, the public helper, and selected file-inspection tools. Use a read-only base image, dropped capabilities, no privilege escalation, and bounded writable storage. Player package installation and internet access remain outside the MVP.
- Keep authored Workspace storage separate from the container so stopping it does not discard files. Storage is in memory (tmpfs) and may be lost when the host restarts.
- Keep per-session resources (connection details, pass brief, log template) in a separate read-only folder from authored Challenge folders. Providing them never overwrites the Player's scripts, recordings, logs or notes.
- Expose only the permitted raw and receive routes through the existing Unix-socket bridge. The bridge still requires the per-session bearer credential.
- Never mount server source, private configuration, progress storage, or Docker control access into Player execution.
- The server reads and writes authored files on the Player's behalf, so it must not follow a link the Player created to a location outside the Challenge folder (see [Files](#implementation-defaults-runtime-and-files)).
- Resource limits are configurable. Start from the prototype's values below, then adjust from measured workload; these are initial engineering values, not performance guarantees.

| Resource | Initial value to validate |
| --- | --- |
| Player CPU and memory | 0.5 CPU; 128 MiB memory, no additional swap |
| Processes and file descriptors | 64 processes; 256 file descriptors |
| Authored Workspace storage | 64 MiB |
| Disposable temporary/home storage | 16 MiB / 4 MiB |
| Managed per-session resources | 1 MiB |
| Browser terminal scrollback | 1,000 lines |

### Editor, notes, and saves

- Use CodeMirror 6 for the editor. Include Python syntax highlighting, line numbers and indentation. Notes use plain-text editing. Autocomplete, diagnostics, and debugging are deferred. Run saved scripts in the existing terminal; the editor does not add a separate execution environment. Shared controls and styling follow the [Frontend spec](frontend.md).
- Use explicit Save for scripts, session logs and notes, with Saved, Unsaved, Saving and Failed feedback. Mark a file saved only after the server confirms the save. Running a file uses saved contents; unsaved editor text is never silently executed.
- Save replaces the file on disk with the editor's text. If the file changed in the terminal since it was opened, the save still overwrites it (last write wins). Detecting that conflict is [later hardening](later-hardening.md#stale-save-conflict-detection).
- On a failed save, keep the unsaved draft in the editor and say so.
- Warn with the browser's standard leave-page prompt when there are unsaved edits.
- Keep authored work in per-Challenge folders. Downloads of saved scripts, recordings, logs and notes come with the file browser, after the three Challenges work.

### Operations integration and readiness

Hello receives a prepared PING example. Ready needs no container. Catch receives a connection starter, a decoder and a session-log template; the Player writes their own recording. The [operations defaults](ground-station-training.md#implementation-defaults-practice-pass-and-evidence) own scenario data, file formats and checks. Do not provide a completed recording or an automatic solve script.

Write connection details into managed resources, separate from authored code, fresh for each session. A script that cached an old credential receives a clear access error. Hello's helper waits for an actual correlated reply; Catch's receiver readiness comes from an authenticated stream connection, not an open terminal or a printed message.

Keep environment preparation, receiver readiness, pass progress and saved completion separate. A working shell or fixture echo cannot set a real goal. The Backend verifies Sim/Link evidence and saved files before saving completion.

### Session lifecycle

Viewing another Challenge's page or using Back/Forward does not change the running session; see [Frontend navigation](frontend.md#navigation-and-active-session).

| Event or action | Container and access | Authored files | Session and completion |
| --- | --- | --- | --- |
| Start | Create the container with starter files and a fresh connection file; bind the bridge. | Add missing starter files; never overwrite existing ones. | New session ID, Sim state and history. |
| Refresh or temporary disconnect | Programs keep running; the terminal reconnects to the same shell without rerunning anything. | Kept. | Same session; the browser reads state again. |
| Stop (also used to restart or switch) | Revoke the credential, stop the bridge, destroy the whole container including background processes. | Kept. | Session ends; completion kept. |
| Python server failure | Old access ends; startup removes any leftover container before admitting a new session. | May be lost if the host restarted. | Unfinished session ends; SQLite completion survives. |

If Stop's cleanup fails, keep the session slot unavailable and show the failure; Stop can be retried. Destroy only resources owned by this Platform deployment. Never automatically retry packet submission when completion is uncertain.

### Interface responsibilities

| Interface | Required contract |
| --- | --- |
| Terminal WebSocket | Same-origin check; attaches to the running session's existing shell; never creates a shell or replays input. |
| File read/save | Only inside the current Challenge's authored folder; no links out of it; size limits; explicit save. |
| Lifecycle | Start/Stop under one lock; cleanup verified before the slot is free; old credentials rejected. |
| Script packet access | Existing bearer authentication, exact binary bytes, current-session check at delivery, real Sim replies and pass telemetry. |

## Implementation defaults: runtime and files

**Controller and storage.** Put the controller and terminal WebSocket inside the single FastAPI process. Use the Python Docker SDK from a worker thread for blocking operations. Only the trusted server mounts Docker's control socket. Give every managed container/volume a deployment label and every execution a fresh `runtime_id`; cleanup uses those labels and recorded IDs, never broad Docker prune commands.

Use Docker named volumes backed by bounded Linux tmpfs: authored files 64 MiB, managed resources 1 MiB, raw bridge 1 MiB. Keep them mounted in the trusted server so replacing Player execution does not discard files. Mount authored storage read/write at `/workspace`, resources read-only at `/attempt`, bridge read-only at `/bridge` in Player execution. Use UID/GID 1000 for Player files. Host restart may lose these volatile volumes. Persistent SQLite lives separately. [Docker volume options](https://docs.docker.com/reference/cli/docker/volume/create/) document the tmpfs-backed named-volume mechanism.

Run Player execution with network `none`, read-only root, all capabilities dropped, no-new-privileges, and the limits above. Prepare Bash, Python, `ls`, `cat`, `cp`, `mv`, `rm`, `mkdir`, `head`, `tail`, `xxd`, `od`, `sha256sum`, the helper, and `socat` in the image. Use a fixed loopback listener at `127.0.0.1:8766` forwarding only to `/bridge/raw.sock`.

A second, script-only ASGI listener in the existing Python process serves that Unix socket; expose only `/raw/attempts/{attempt_id}` and `/receive/attempts/{attempt_id}` there, with bearer authentication on every connection. It shares the actual Sim instance. Public API, progress, filesystem and Docker operations never appear on this listener. The Player can reach the socket directly, so security belongs in its handler rather than the forwarding command.

The controller creates one Bash PTY (pseudo-terminal) per container, starting in `/workspace/{challenge_id}`; Ctrl-C uses the PTY. Closing the terminal tab only disconnects. If the shell exits or the container fails, show that the session failed and offer Stop; nothing restarts automatically.

**Files.** Use one fixed `workspace_id` for the shared team Workspace, so authored files survive Stop and Start. Provide only missing authored starters: Hello gets `ping_example.py` and `notes.txt`; Catch gets `main.py` (connection boilerplate with task comments) and `notes.txt`. Files stay in `/workspace/{challenge_id}`. User-created scripts, recordings and logs are never overwritten.

Managed, read-only resources: `/attempt/connection.json` holds `{attempt_id, url, credential, protocol: raw|receive}` for Hello and Catch; `attempt_id` is the session ID. The URL uses the loopback listener and the current route. Catch also receives `/attempt/pass-brief.json` and `/attempt/log-template.json` with the scenario, pass and setup values and blank result fields. The Player copies the template to a log file of their own before filling it in. The template and brief formats are owned by the operations spec.

The helper reads the current connection file each time it runs, so starters contain no live credentials. Explain that credentials expire when the session stops.

File routes work on the running session's Challenge folder:

| Method and path | Request → response |
| --- | --- |
| `GET /api/session/file?path=main.py` | `{path, text}`. UTF-8 text up to 1 MiB; otherwise 413 `TOO_LARGE`. |
| `PUT /api/session/file` | `{path, text}` → `{path, size_bytes}`. UTF-8 up to 1 MiB. Creates or replaces the file. |

Path rules (keep these; they protect the server): accept only a relative path inside the current Challenge folder. Reject absolute paths, `..`, and NUL. Resolve the real path with `os.path.realpath` and refuse it unless it is still inside the Challenge folder, so a symlink the Player made cannot point the server elsewhere. Read and write regular files only. Writing a temporary file and renaming it, and walking directories by file descriptor to close the remaining race, are [later hardening](later-hardening.md#descriptor-safe-and-atomic-file-writes).

After the three Challenges work, add listing (`GET /api/session/files`) and download (`GET /api/session/download?path=…`, sent as an attachment, never shown inline as HTML) with the same path rules.

### Controller integration handoff

`api.runtime.RuntimeController` is an in-process infrastructure boundary. Construct
one controller per deployment with the Docker client, `RuntimeStorage`, the prepared
Player image and `RuntimeLimits`. The trusted Linux server must already mount the
three named tmpfs volumes at `/runtime/authored`, `/runtime/managed` and
`/runtime/bridge`; their deployment labels and actual quotas are checked. Configure
volume names through `RUNTIME_AUTHORED_VOLUME`, `RUNTIME_MANAGED_VOLUME` and
`RUNTIME_BRIDGE_VOLUME`, and the label value through `RUNTIME_DEPLOYMENT`.
Empty volumes are deployment infrastructure; packaging/teardown owns their removal.

Under the session lock, call
`await create(workspace_id=..., attempt_id=..., challenge_id=..., starters=...,
resources=...)`, passing the session ID as `attempt_id`. File maps contain plain
filenames and bytes supplied by the Challenge implementation. The return value
identifies the runtime and its recorded Docker container name. `terminal` is the
single existing nonblocking PTY socket; `terminal_exec_id` supports Docker resize
and exit inspection. The terminal WebSocket reads and writes that socket; attaching
never creates a shell.

`api.script_bridge.ScriptBridge` runs its script-only ASGI listener on the same
server event loop. Bind the session ID, secret, protocol and actual Sim
WebSocket handler, then start it on `/runtime/bridge/raw.sock`. Ready has no session.
Authentication and revocation checks also apply to direct Unix-socket clients.
The infrastructure fixtures are not Sim handlers.

On Stop, revoke the credential and await `bridge.stop()` before
`await controller.destroy(clear_workspace=False)`. `RuntimeFailure.code` is
`RUNTIME_UNAVAILABLE` or `CLEANUP_FAILED`; `current` and `failed` retain the cleanup
obligation. A cancelled Docker worker continues to completion; cleanup refuses to
overtake it and must be retried explicitly. Free the session slot only after
successful cleanup.

Labels `org.knightsat.deployment`, `org.knightsat.runtime` and
`org.knightsat.workspace` identify execution; storage volumes carry the deployment
label. At startup, remove containers labelled for this deployment and clear the
managed and bridge storage before reporting healthy. The controller refuses new
execution while another labelled container remains.

## Implementation defaults: terminal and helper contracts

**Terminal WebSocket:** `/api/session/terminal`, same-origin only. It attaches to the running session's shell.

| Direction | Message |
| --- | --- |
| Server → browser | Binary frames containing raw terminal output bytes; pass them to `terminal.write()`. |
| Browser → server | Text frame `{type: "input", data}` with the typed characters; the server writes them to the PTY as UTF-8. Ctrl-C is the ordinary character `\u0003`. |
| Browser → server | Text frame `{type: "resize", cols, rows}`; the server clamps to 20–300 columns and 5–120 rows and resizes the shell. |
| Server → browser | Close with a reason when there is no running session or the shell ended. |

Only one terminal connection is attached at a time; a new connection replaces the old one. Output produced while no browser is attached is not replayed; press Enter for a fresh prompt. Never send a shell command to recreate output, and never resend input after a reconnect. Read the PTY only as fast as the browser accepts output, so nothing piles up in server memory. Use xterm's fit addon for rows and columns. Disable automatic terminal hyperlinks and clipboard access. Replaying missed output after reconnect is [later hardening](later-hardening.md#terminal-reconnect-offsets-and-history).

Use a small synchronous Python module named `kss_client` backed by pinned `websockets`. Pin compatible helper/packet versions into the Player image. Document imports, methods, formats and the exact terminal command beside each starter; assume basic Python knowledge.

- `load_connection()` reads `/attempt/connection.json` and returns its documented fields. `connect(url, credential)` is a context manager for the raw endpoint, using the bearer header. `send(packet: bytes)` preserves bytes. `receive(timeout_s=5)` returns either Packet (`data: bytes`) or Feedback (`code`, `message`), and raises TimeoutError if no message arrives. Raw text feedback is `{type: "feedback", code, message}`. No implicit reconnect or retransmission.
- `build_ping(sequence, role)` constructs the documented packet; the Hello example uses guest role and sequence 0 per invocation. Repeated invocations are deliberate transmissions and may reuse sequence 0 with Defenses off. `decode_packet(packet)` verifies supported downlink header/length/CRC and returns `{kind, sequence, state, reply}`: kind is `telemetry` or `reply`; `state` uses the Backend model fields, and `reply` is null or `{command_code, command_sequence, status}`. Invalid packets raise a readable `ValueError`; decoding never repairs or sends bytes.
- `python ping_example.py` sends exactly one PING and waits up to five seconds total for the matching successful PING reply, displaying actual fields and ignoring periodic telemetry as completion evidence. On timeout/connection failure it says no reply was observed; it never resends. Server goal correlation uses the actual submission, not just the reusable wire sequence.
- `receive_pass(url, credential)` is a context manager for the receive endpoint. The starter opens it and prints “Receiver ready; use Start pass in the website.” Connecting consumes the server's initial ready message. `stream.records()` yields dictionaries in the [recording format](ground-station-training.md#implementation-defaults-practice-pass-and-evidence), blocking until the Player starts the pass and then until each packet arrives. The Player adds the loop, file writing and decoding with `decode_packet(bytes.fromhex(record["packet_hex"]))`. End of the pass finishes iteration. Interruption/connection loss raises a readable error and leaves a partial file for inspection.

**Receive wire contract.** An authenticated connection to a `not_started` Catch pass receives `{type: "ready", pass_run_id}` once the receiver is registered. Subsequent JSON messages are `{type: "packet", record: {pass_run_id, index, scenario_time, packet_hex}}`, then `{type: "end", pass_run_id, count: 12}` and normal close; errors use `{type: "error", code, message}` and close. No client data messages are allowed. Connections during a running or finished pass are rejected with `PASS_ALREADY_STARTED`; Stop and Start for another reception. A receiver disconnect before Start merely clears readiness; after Start it interrupts the pass unless it already finished. Connection-only starter code is fully supplied; recording and extracting readings remain the task.

The Catch terminal runs the saved script with `python main.py`. Explicitly explain that saving a file, running a program, receiving all packets and passing Check work are different steps. Editor and terminal use the same authored files.

## Acceptance checks

The main acceptance check is the Player journey in Chrome against the real Backend, Sim and container. Test what the Player sees rather than counting internal calls.

1. Run the Hello terminal command and receive its real reply; saved completion unlocks Ready. Check Ready's setup. Start Catch, edit/save/run Python, start the pass, save the recording and the log, Check work and see saved completion.
2. Reject false success from Hello submission alone, a wrong setup, incomplete or old recordings, or incorrect log facts. Locked Challenges cannot be started.
3. Refresh while a program runs: it keeps running, the terminal reconnects to the same shell, and nothing is sent twice.
4. Stop with saved files and a background process: files remain, the process is gone, and the old credential no longer works. Start again: starter files did not overwrite saved work.
5. Save from the editor and read the same bytes with `cat` in the terminal. A failed save keeps the draft. Unsaved text is not run.
6. File paths with `..`, absolute paths or a symlink pointing outside the Challenge folder are refused.
7. Player containers have no network, no Docker socket, no server source or progress database; resource limits apply. Use real containers for these claims.
8. A server restart ends the unfinished session, removes the leftover container and keeps saved completion.
9. Keyboard access, readable labels and distinguishable errors.

## Out of Scope

Unrestricted public access (hosting remains team-only); individual Platform accounts or simultaneous Players; collaborative editing or automatic merging; durable personal-work recovery after server failure; Player package installation and outbound networking; a general hosted IDE; goal-free Sandbox; real orbital contact windows or radio operation; working Defense comparisons; research logging/export; the robustness items in [later hardening](later-hardening.md); and importing the entire throwaway prototype as production architecture.

## Further Notes

### Primary references and prototype evidence

- [Project plan](project-plan.md) and [glossary](../glossary.md).
- [Backend and simulation](backend-and-simulation.md) owns sessions, script access, and completion. The [operations curriculum](ground-station-training.md#mvp-operations-curriculum) owns the learning tasks, and [Packet format](packet-format-v1.md) owns the packet bytes.
- [Frontend workstation requirements](frontend.md#workstation-implementation-handoff-ksat-36) define the shared layout.
- Historical prototype evidence was retained locally under `PSB GS/mockups/HANDOFF.md` and `PSB GS/prototypes/kss-terminal-feasibility-2026-09-18/server/terminal-prototype/{FINDINGS,README}.md`, outside this repository. Contributors do not need those unpublished files; use the current specifications and [repository checks](../development.md#tests-and-lint).
- Prototype branch: `prototype/terminal-feasibility-2026-09-18`. Source/evidence commit: `9bd1f30872774ea09fa657b27665bb67e5183cbc`; cleanup-documentation HEAD: `d4407d9f8925b031e8d49da41550caaabed6022d`; base: `7ed045a736ee4d4679df7fae7f76a3af0790fd2f`. Retained locally; not published.

The prototype demonstrated execution, shared files, authenticated byte preservation, reconnect, container replacement, cleanup, and the specific isolation/limit probes in its findings. It used a raw echo fixture, plain HTML, a separate throwaway gateway, interleaved multi-tab terminal input, and last-writer-wins file saves. Actual Sim Service acceptance, operations task verification, completion persistence, and React integration were not demonstrated. Its warm local timings are observations, not guarantees.
