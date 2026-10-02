# Later hardening

This file keeps the robustness requirements we deliberately left out of the MVP. The MVP is a one-session, team-only demo behind an access gate; these items matter for a public, multi-user or production service. **Nothing here is an MVP requirement.** Build it only after the three Challenges work and the team agrees to take it on.

The text below was moved from the owning specs on 1 October 2026, lightly shortened, so the original reasoning is not lost. Former Jira tickets are named for history only. If an item comes back into scope, move it back into the spec that owns that behavior.

What the MVP still keeps: the container isolation that is already built, the Cloudflare Access gate, server-enforced unlocks, saving completion before showing success, the per-session script credential, the same-origin check on changes, and a simple check that file paths stay inside the Challenge folder.

## Backend and sessions

Moved from [Backend and simulation](backend-and-simulation.md).

### Browser ownership and Platform busy

The Web Backend recognizes the owning browser through an opaque, server-issued ownership cookie, shared across tabs and refreshes. It is HttpOnly, SameSite=Lax, and Secure when hosted over HTTPS. Browser control requests and browser WebSocket connections validate ownership and Origin. Shared demo progress does not grant ownership.

A different browser receives “Platform busy” (`GET /api/session` returns `status: busy` with no personal data). Losing the ownership cookie does not let a browser take over the current session; it waits for that session to stop or expire. Passing the access gate does not grant control of another browser's session. Account-based recovery is deferred. Every owner-only route checks the cookie; HTTP reads reject a different Origin when present. Errors: 403 `NOT_OWNER`, 409 `PLATFORM_BUSY`.

Former tickets: KSAT-12 (server), KSAT-31 (browser).

### Tab-control generations

Within the owning browser, one tab controls terminal input and editing; other tabs observe and can explicitly Take control (`POST /api/attempts/{id}/control` with `{tab_id}` → `{tab_id, generation}`). Use server-enforced tab identity and a changing control generation, not merely disabled buttons. Every mutation except Take control and the activity heartbeat carries `X-Tab-Id` and `X-Control-Generation`; reject a mutation whose grant is stale at the time of application (409 `STALE_CONTROL`, 403 `NOT_CONTROLLER`).

Transfer control atomically. Old terminal input and editor saves queued under the revoked generation must not be applied afterward. Leave the shell, running programs, Workspace and session intact. Preserve an old tab's unsaved draft visibly as unsaved, but do not let it save until it reacquires control. Start establishes generation 1; restart, switch and reset preserve the controlling tab but increment its generation. Store tab ID and grant in sessionStorage; a new tab, including one opened from another tab, generates its own ID. A refresh may restore the same tab's control only if its grant is still current; concurrent Take control requests result in one current grant. Taking control does not invalidate the script credential or interrupt running programs.

Former tickets: KSAT-12, KSAT-31, KSAT-13, KSAT-38.

### Live updates and resynchronization

Replace polling with an Attempt WebSocket (`/api/attempts/{id}/events`) that starts with an authoritative snapshot, then delivers numbered updates:

- The server first sends `{type: "snapshot", attempt_id, revision, data: Snapshot}`; each later `{type: "update", attempt_id, revision, data: {view, history_append, progress}}` replaces the small public view and appends only new packets. On termination send `{type: "ended", attempt_id, revision, reason}` and close.
- Capture the snapshot and subscribe under the same serialization boundary, so a change during connection setup is neither missed nor duplicated.
- After installing a snapshot, ignore duplicate or older updates and apply only the next expected revision. A revision gap or invalid frame triggers a fresh snapshot. Ignore messages from superseded connections or Attempts.
- During disconnection, label retained readings as stale. Reconnect while visible after 1, 2, 4, 8, then at most 15 seconds. Reconnecting restores observation only; it never reruns a program, resends a packet or repeats an HTTP mutation.
- Define event records once with Pydantic, including a discriminated union for `type`, and explicitly include them in OpenAPI `components.schemas` for TypeScript generation. The browser connection module checks event type, IDs, integer revision and required fields before dispatch. See [OpenAPI TypeScript schema guidance](https://openapi-ts.dev/advanced).
- The browser keeps this state in a React Context with a pure `useReducer` and named, typed actions, exposed through separate state and dispatch contexts.

Former tickets: KSAT-12, KSAT-31.

### Retry saving without repeating the task

Keep `completion_state = in_progress|save_failed|saved`. A failed write retains evidence; an explicit Retry saving action (`POST /api/attempts/{id}/completion/retry`) performs persistence again without resending a packet, rerunning Python or replaying the pass. On a Ready/Catch retry, recheck session identity and the current setup/file evidence; changed or missing evidence clears the unsaved goal and requires a new check. Retain validated file hashes and context for the retry. Hold a per-session operation lock through validation and the database commit so no lifecycle change can overtake persistence.

Former tickets: KSAT-17, KSAT-22, KSAT-40.

### Ready to Catch handoff of live settings

Explicitly switching from Ready for the Pass to Catch and Log copies the verified setup and scenario version into the new session before ending Ready. If that setup changed, refuse the switch with field feedback and leave Ready running. Every setup edit (`PUT /api/attempts/{id}/station-setup`) is stored on the server and clears `setup_verified`; Start pass requires the current setup to be verified. The MVP instead always starts Catch from the correct prepared setup, which gives the same result for the learner.

Former ticket: KSAT-19.

### Lifecycle extras

- **Idle expiry.** End a session after 30 minutes without Player activity, terminate execution and clear personal Workspace data before releasing the slot. A visible owning page (heartbeat `POST /api/attempts/{id}/activity`, at most once every 30 seconds), accepted terminal input, file saves, explicit setup/pass/check actions and raw packet submissions count as activity; autonomous telemetry, receive-only stream traffic, terminal output and idle sockets do not. Test with a controlled clock, not a 30-minute sleep. Former ticket: KSAT-16.
- **Reopen runtime.** If only the container fails, an explicit Reopen terminal replaces the whole container (including descendants and temporary/home data) while keeping the same session, Satellite Sim state, packet history and authored files. Never reopen automatically or rerun commands. A pass already interrupted stays interrupted. Former ticket: KSAT-33.
- **Reset workspace.** After a distinct confirmation, revoke access, remove execution and all authored and managed files, restore starters, and start a fresh session for the current Challenge while keeping saved completion. Separate from Reset demo progress. Former ticket: KSAT-34.
- **Restart and switch as one atomic action.** Validate the requested Challenge, unlocks and handoff before revoking the old session; keep exclusive ownership while revoking, terminating, verifying cleanup and provisioning the replacement. An invalid switch leaves the current session running. Former ticket: KSAT-15.
- **Clearing personal files on Stop.** When sessions belong to different people, Stop clears authored files, managed resources, temporary/home data, terminal buffers, shell history and stored credentials, after explaining the deletion and offering downloads. Startup reconciliation also clears all personal storage before admitting a new Player. Former ticket: KSAT-16.
- **Rich internal operations.** `watch_attempt` as an ordered event feed; serialized Sim packet ingestion together with snapshot/subscription; a per-Attempt operation lock across setup changes, verification, persistence and lifecycle revocation.

### Generated-types CI check

Check in generated TypeScript, and make CI export the OpenAPI schema, regenerate the types and fail on any difference. Former ticket: KSAT-9.

### Receive stream bounds

Bound the receive subscriber to 64 messages of at most 4 KiB; overflow while running interrupts the pass rather than silently dropping records. Serialize subscription/disconnection with Start pass so it cannot begin against a stale readiness flag. Former ticket: KSAT-20.

### Deployment and sessions

Session-safe deployment, atomic idle/admission checks, busy refusal during deployment and uninterrupted user sessions are deferred until a production deployment is in scope. They do not block automatic development updates.

## Terminal and workspace

Moved from [Terminal Workspace](terminal-workspace.md).

### Terminal reconnect offsets and history

The gateway drains the PTY into a 128 KiB history ring. The first browser message is `{type: "attach", runtime_id, tab_id, generation, after_offset}`; the server replies `{type: "attached", runtime_id, start_offset, end_offset, history_lost}` and then `{type: "output", runtime_id, offset, data_base64}` messages, where the offset counts raw bytes from runtime start. Input and resize messages carry `runtime_id, tab_id, generation` and base64 data. A retained xterm instance resumes at an available offset and receives exactly the missing bytes, even across split escape sequences. If history is gone or a gap appears, reset the parser, show “Earlier terminal output is unavailable,” and attach at the current tail without replaying a ring that starts mid-sequence. Limit input to 8 KiB per message, output chunks to 8 KiB and each subscriber queue to 128 KiB; disconnect slow subscribers on overflow while continuing to drain the PTY. Bound client rendering queues with the same overflow behavior. Observers in other tabs may attach and read. Former tickets: KSAT-38, KSAT-13.

### Stale-save conflict detection

Reads return a version that is the SHA-256 of the actual bytes on disk. A save supplies the version it was based on (`base_version`; null means create only if absent, including Save as). Under a per-file lock, read the file again, compare, and reject a mismatch with 409 `FILE_CONFLICT`, keeping both the draft and the stored file unchanged. Offer reload/compare or Save as; never force-overwrite or merge automatically. This catches terminal-side edits already present when the save is validated; a program continuously rewriting a file is outside the lock and the limit must be documented. Check work also sends `recording_version` and `log_version`, reads both files into immutable buffers, matches their hashes, and returns `FILE_CONFLICT` if they moved. Before Stop or switching, require pending edits to be saved or explicitly discarded. Re-read an open file on editor focus to detect shell edits without replacing a dirty draft. Former tickets: KSAT-14, KSAT-39, KSAT-45, KSAT-22.

### Descriptor-safe and atomic file writes

Resolve relative paths by walking directory descriptors beneath the selected volume (`dir_fd`, `O_DIRECTORY`, `O_NOFOLLOW`) with no symlink following, so a Player cannot swap a path component between the check and the open. Reject special devices and FIFOs. Write a temporary file in the same checked directory and atomically rename it over the target; no success response before the rename succeeds. A quota failure keeps the existing file and removes the temporary file. A short shared apply gate serializes the final grant check and replace with control revocation, so an already-revoked save cannot commit later. Former tickets: KSAT-46, KSAT-39.

### Fault and load testing

Verify controller failure during each transition, interrupted provisioning and cleanup retry with real containers; sustained output, slow readers and disconnect during output; and a broader security assessment of the tested internal deployment conditions.

## Frontend

Moved from [Frontend](frontend.md).

- One shared connection module owns the Attempt WebSocket, feeds a pure reducer, and marks disconnected readings stale; panels never open their own event connections (see [Live updates](#live-updates-and-resynchronization)).
- Take control, observer read-only mode and per-tab grants (see [Tab-control generations](#tab-control-generations)).
- Editor Conflict state, reload/compare and Save as (see [Stale-save conflict detection](#stale-save-conflict-detection)).
- Stop, Reset workspace and Reset demo progress each with their own destructive-action dialog and save/discard/download decision.
