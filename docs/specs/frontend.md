# Frontend

## Read this for browser work

This is the agreement for the UI we are building. Start in `ui/src/App.tsx` and `ui/src/Workstation.tsx` for the reusable shell and routes. Shared controls are installed; catalogue, session and execution integration remain separate work.

| Part | Builds on |
| --- | --- |
| Workstation layout and shared controls (done, KSAT-36) | Every other UI part uses these. |
| Challenge list, API client and generated types | `GET /api/challenges`; the Backend owns the API schemas. |
| Ready station form and its check | The [Ready routes](backend-and-simulation.md#implementation-defaults-browser-contract); needs no session. |
| Session hook with Start/Stop | `GET/POST/DELETE /api/session`. |
| Terminal / editor / file browser | The terminal WebSocket and file routes in the [Workspace spec](terminal-workspace.md). |

Read the relevant section, then its acceptance checks. **Provider** means shared React state available to child components. See the [glossary](../glossary.md) for other terms.

This spec owns the shared UI foundation and browser conventions for the operations MVP. Start with the [project plan](project-plan.md). The foundation, behavior and implementation defaults below are agreed requirements. The current UI provides the KSAT-36 workstation skeleton; catalogue, session and execution integration remain separate work. Robustness we chose to leave out of the MVP is in [later hardening](later-hardening.md#frontend).

## Shared UI foundation

| Area | Use |
| --- | --- |
| Application | React, TypeScript, and Vite |
| Components | shadcn/ui with Base UI primitives |
| Styling | Tailwind with centrally defined colors, typography, and spacing |
| Icons | Lucide |
| Navigation | React Router, with shareable main-page URLs and a persistent workstation shell |
| Shared session state | One React Context provider and a `useSession()` hook |
| HTTP API | Types generated from FastAPI OpenAPI with `openapi-typescript`; one shared client using browser `fetch` |
| Editor and terminal | CodeMirror 6 and xterm.js, following the [Workspace spec](terminal-workspace.md#editor-notes-and-saves) |

Configure the shared components once to match the approved dark workstation design. Keep reusable controls in `ui/src/components/ui/`; feature components import them rather than creating separate button, dialog, tab, form, or menu implementations. Use one shared set of style tokens for colors, typography, spacing, and control states.

Provide a small developer component example page showing the supported controls and their intended usage. It is a reference for teammates, not part of the Player's Challenge workflow. Package versions belong in the package manifest and lockfile.

## Layout and screen support

The supported MVP browser is current stable desktop Google Chrome. Run the required browser acceptance checks in Chrome and record the tested version with the results. Other browsers are outside the MVP support commitment; do not deliberately block them solely by browser name.

Use three full-height panes, following the Slack/Codex reference: left navigation, a substantial Workspace pane in the center, and the Challenge guide on the right. Keep the guide and working tools side by side. Use the existing dark visual direction, readable labels, visible keyboard focus, and text alongside status colors. The [Workspace spec](terminal-workspace.md#application-and-responsibility-boundaries) owns workspace interaction requirements.

The first demo supports desktop use, targeting widths of 1280px and above. Below the supported width, show a clear message explaining that the demo requires a wider desktop window. Phone/tablet layouts and collapsing the workstation into a mobile interface are deferred. Keep keyboard access and readable text at browser zoom; do not shrink text to force the layout to fit.

## Operations interaction choices

Hello, Satellite! introduces a supplied terminal command. Ready for the Pass is a graphical form and needs no session or terminal. The Catch pass begins when the Player clicks Start pass, with scenario time clearly distinguished from wall-clock time.

The Ready form includes satellite, pass time, receiving frequency, receiving mode, an automatic-tracking control and Check setup feedback. Use the [agreed setup behavior](ground-station-training.md#ready-for-the-pass-agreed-interaction). Catch and Log uses the editor and terminal to adapt and run a Python starter, then an editor-based log with prefilled session details and Player-entered results. Use the [scenario/file defaults](ground-station-training.md#implementation-defaults-practice-pass-and-evidence) for exact context, readings and evidence.

Catch shows Receiver ready, Start pass, pass progress, fields for the saved recording and log filenames, and Check work; completion feedback distinguishes verified work from successfully saved progress. Do not add a PING button, packet-building form or Flag entry box.

## Navigation and active session

Hosted entry uses [Cloudflare Access email codes](backend-and-simulation.md#hosted-team-access) for approved addresses. Do not add custom signup, password, or profile screens for the MVP. Individual Platform accounts are later work; completion remains shared.

Give Challenge pages shareable URLs and working browser Back/Forward navigation. Keep the workstation shell mounted during in-app navigation; individual workspace panels remain ordinary tabs.

The viewed Challenge and the Challenge running in the session are separate. Opening Hello's page while Catch and Log runs shows Hello's instructions without stopping the Catch session. Label the terminal and live tools (telemetry, history, Start pass, Check work) with the running session's Challenge, so browsing another page cannot mislabel live data.

Starting a session requires an explicit Start button; switching is Stop then Start. A URL change alone never starts or stops a session. Before Stop, warn if the editor has unsaved changes. The server still enforces Challenge availability. In-app browsing must preserve unsaved drafts.

## Shared state and connections

Mount one session provider in the persistent workstation shell so in-app navigation does not recreate it. It reads `GET /api/session` about once per second while a session is running and after every Start, Stop or check, and exposes the latest result, plus `start()` and `stop()`, through a `useSession()` hook. Panels use that hook rather than fetching the session themselves. No additional state-management library is required. The [Backend](backend-and-simulation.md#reading-session-state) explains why reading the whole state again is enough.

If a read fails, keep showing the last result labelled "connection lost" and keep trying. Never resend a command or repeat an action because a read failed. The terminal WebSocket is separate and follows the Workspace contract.

Keep ordinary form input and temporary panel state local. CodeMirror owns editor documents and unsaved drafts; xterm.js owns terminal output. Do not route keystrokes or terminal bytes through shared session state. Preserve drafts during in-app navigation.

## HTTP API types and client

Generate the frontend's HTTP request and response types from the FastAPI OpenAPI schema using `openapi-typescript` as a development dependency. Backend API definitions own these shapes; frontend features import generated types instead of maintaining separate copies. Do not hand-edit generated types. Regenerate them when API definitions change.

Use one shared HTTP client built on the browser's `fetch`. Feature code uses that client so response handling and errors follow one convention. Follow the no-automatic-retry rule in the [Backend spec](backend-and-simulation.md).

Use the [shared Backend error envelope](backend-and-simulation.md#browser-api-errors): a stable code, readable message, and optional field errors. Show errors beside the affected control or panel and preserve entered values and drafts. Failures requiring action stay visible until resolved or dismissed; a disappearing notification is not sufficient.

The shared client normalizes network failures into the same presentation without pretending they are server responses. If an operation's outcome is unknown, say so and reconcile with authoritative state where possible; do not claim rejection, completion, or save success without evidence. Never automatically repeat an uncertain command or mutation.

Generated TypeScript types provide development-time checks; they do not validate incoming data at runtime. The terminal WebSocket messages are documented in the [Workspace spec](terminal-workspace.md#implementation-defaults-terminal-and-helper-contracts), not in OpenAPI.

## Acceptance checks

- Feature screens reuse the shared controls and styling; the developer example page demonstrates their intended usage.
- The workstation follows the selected layout at supported desktop widths, with readable labels, visible focus, and keyboard-operable controls.
- Narrower viewports show an understandable desktop-width requirement.
- Python editing and notes meet the [editor requirements](terminal-workspace.md#editor-notes-and-saves).
- Opening another Challenge page or using Back/Forward leaves the running session intact. Live tools stay labelled with the session's Challenge; only explicit Start and Stop change it.
- Panels share one session provider; navigation does not create a second one.
- HTTP types regenerate from the Backend OpenAPI schema and the UI type-checks against them; features use the shared `fetch` client.
- Field errors appear beside the relevant inputs; actionable failures remain visible. A rejected save preserves the draft, and a lost response is reported as an uncertain outcome without automatically repeating the operation.

## Implementation defaults: screens and styling

These defaults carry the approved visual direction into a self-contained build reference; teammates do not need the local mockup to implement the shell.

- Routes: `/` redirects to `/challenges/hello-satellite`; `/challenges/:challenge_id` displays a Briefing without starting a session. MVP IDs are `hello-satellite`, `ready-for-the-pass` and `catch-and-log`. Unlock them in that order using server-owned shared demo progress; completed activities remain repeatable. Offensive and Defensive tracks are labelled Coming later with no playable routes. Unknown IDs show Not found. `/dev/components` is available only in development.
- Use a full-height CSS grid: left rail 240px, central Workspace with minimum width 480px, and right guide with minimum width 440px. Divide remaining width between Workspace and guide in a 1.15:1 ratio. Give each pane an aligned header and independently scrolling content. The Workspace fills its pane vertically. Resizable splitters and saved layout preferences are deferred.
- Left: Challenge navigation and files. Center: persistent Terminal / Editor / Notes tabs, Challenge tools (including the Ready station form), and Satellite Sim state. Right: the viewed Challenge’s Briefing, instructions, task-completion feedback, Debrief and contextual map. Bottom: connection and command-delivery status. Display the session's Challenge beside every live tool when it differs from the viewed page.
- Narrow windows and browser zoom show a nonblocking width notice above the workstation; preserve the session, drafts, keyboard access and horizontal scrolling. Never stop execution or hide the only Stop control because the viewport shrank.
- Start with the tokens below, system sans-serif for prose and system monospace for bytes/code. Body text is 14–16px; secondary labels at least 12px. Use 4px spacing increments and 6px control corners. Verify contrast and focus in the rendered UI; the mockup's tiny labels are not requirements.

| Token | Initial value |
| --- | --- |
| Background / panel / input | `#10161c` / `#141c24` / `#141e27` |
| Text / secondary text / border | `#e0e7ed` / `#a0afbc` / `#2a3540` |
| Accent / text on accent | `#bce387` / `#15200c` |

Use shared Button, Input, Label, Tabs, Dialog, AlertDialog, Select, Tooltip and Alert controls. Native tables render packet fields/history; CodeMirror and xterm own their specialist surfaces. Stop and Reset demo progress use explicit confirmation dialogs. Prefer inline status to toasts, CSS grid to a layout package, and native form state to an additional form library. Dark appearance only for MVP.

Implementation references: [shadcn/ui for Vite](https://ui.shadcn.com/docs/installation/vite) and [CodeMirror](https://codemirror.net/docs/guide/).


## Workstation implementation handoff (KSAT-36)

- `ui/src/App.tsx` owns routes and the development-only, lazy-loaded `/dev/components` reference. The production build excludes its route, link and example code. Unknown routes and Challenge IDs show Not found.
- `ui/src/Workstation.tsx` owns the persistent shell and Workspace pane. Its small Briefing list is display-only: it supplies no unlock, session or completion state. The server catalogue replaces it; browsing remains separate from starting a session.
- The session provider mounts inside `Workstation`, around both routed content and persistent panels. Terminal and editor work belongs in the persistent Workspace pane; keep draft-bearing panels mounted. Label live tools from the running session, never from the viewed route.
- Shared controls live in `ui/src/components/ui/`. `ui/components.json`, `ui/vite.config.ts` and `ui/src/styles.css` centralize the Base UI registry, build integration and dark tokens. System fonts, 4px spacing units, 6px corners and the specified desktop columns are used.
- Run `npm run dev` from `ui/` and visit `/dev/components` for labelled form controls, persistent errors, tabs, dialogs, confirmation and tooltips. Base UI tabs use arrows for focus and Enter/Space for selection. Import these controls in feature screens rather than implementing replacements.

Verification on 2026-09-29: Google Chrome 154.0.8037.92 on macOS, using Playwright. Checked 1280px and 1600px layouts, 1000px width notice/horizontal scrolling, persistent Workspace pane and selected tab through route changes and Back/Forward, keyboard tabs/select, and dialog Escape/focus return. Empty panels report unavailable session, telemetry, command-delivery and progress services. Vitest covers route/Workspace persistence, unknown Challenges and example form/confirmation behavior. Production preview rejects `/dev/components`, and its bundle contains no example page. These are skeleton checks, not evidence for real session or Sim behavior.

Layout revision: the three-pane Slack/Codex reference replaces the original center dock and narrow inspector. Guide browsing remains separate from the active Workspace; route changes preserve the mounted Workspace and selected tab.
