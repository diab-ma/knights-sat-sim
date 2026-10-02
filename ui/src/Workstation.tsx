import { Link, NavLink, Outlet, useParams } from "react-router";
import {
  BookOpen,
  FileCode,
  Folder,
  Info,
  Orbit,
  Satellite,
  Terminal,
  WifiOff,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Briefing previews only. KSAT-9 replaces these with the server catalogue;
// availability and completion must never be inferred from this list.
const challenges = [
  {
    id: "hello-satellite",
    title: "Hello, Satellite!",
    goal: "Send PING and recognize the Satellite Sim’s reply.",
    description:
      "Practice your first exchange over the Software Link using a supplied terminal command. No script writing is required.",
  },
  {
    id: "ready-for-the-pass",
    title: "Ready for the Pass",
    goal: "Prepare the station for a simulated satellite pass.",
    description:
      "Check the satellite, pass time, receiving frequency and mode, then enable automatic tracking. Scenario time is fictional; the pass starts on demand.",
  },
  {
    id: "catch-and-log",
    title: "Catch and Log",
    goal: "Receive telemetry, save a recording and complete a session log.",
    description:
      "Adapt a short Python starter, use the supplied packet decoder and record what happened during the practice pass.",
  },
];

export function ChallengePage() {
  const { challenge_id } = useParams();
  const challenge = challenges.find(({ id }) => id === challenge_id);
  if (!challenge) return <NotFound />;
  return (
    <article className="challenge-page">
      <p className="eyebrow">Basic operations · Briefing preview</p>
      <h1>{challenge.title}</h1>
      <p className="challenge-goal">{challenge.goal}</p>
      <Alert>
        <Info aria-hidden="true" />
        <AlertTitle>Practice is not available yet</AlertTitle>
        <AlertDescription>
          You can browse the Briefings. Sessions and Challenge availability are
          not connected.
        </AlertDescription>
      </Alert>
      <section className="guide-section" aria-labelledby="briefing-title">
        <h2 id="briefing-title">Briefing</h2>
        <p>{challenge.description}</p>
      </section>
      <section className="guide-section" aria-labelledby="completion-title">
        <h2 id="completion-title">Task completion</h2>
        <p>Shared progress has not been loaded. No completion is reported.</p>
      </section>
      <section className="guide-section" aria-labelledby="debrief-title">
        <h2 id="debrief-title">Debrief</h2>
        <p>A Debrief will follow verified and saved completion.</p>
      </section>
      <section className="context-map" aria-labelledby="map-title">
        <Orbit className="size-12 text-muted-foreground" aria-hidden="true" />
        <h2 id="map-title">Mission context</h2>
        <p>
          A contextual map will appear here. No live position or pass data is
          available.
        </p>
      </section>
    </article>
  );
}

export function NotFound() {
  return (
    <article className="challenge-page">
      <h1>Not found</h1>
      <p>This page is not available.</p>
      <Link className="text-primary underline" to="/challenges/hello-satellite">
        Browse Hello, Satellite!
      </Link>
    </article>
  );
}

// KSAT-12: mount the Context/useReducer Attempt provider here, outside Outlet.
// Route content is viewed content only; runtime, drafts and live tools belong
// to this persistent shell and must use the authoritative active Attempt.
export function Workstation() {
  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">
        Skip to work area
      </a>
      <p className="width-notice">
        This demo requires a desktop window at least 1280px wide. Widen your
        window or scroll horizontally; your work stays open.
      </p>
      <div className="workstation">
        <header className="app-header">
          <div className="brand">
            <Satellite aria-hidden="true" />
            <span>Knight Sat Sim</span>
          </div>
          <span className="text-muted-foreground">Ground-station practice</span>
          <span className="simulation-label">Simulation only</span>
        </header>
        <aside className="left-rail" aria-label="Navigation and files">
          <div className="pane-heading">
            <h2>Challenges</h2>
          </div>
          <div className="navigation-content">
            <nav aria-label="Challenges">
              <h2 className="eyebrow">Basic operations</h2>
              <p className="rail-caption">Browse Briefings</p>
              {challenges.map((challenge, index) => (
                <NavLink
                  key={challenge.id}
                  to={`/challenges/${challenge.id}`}
                  className="challenge-link"
                >
                  <span className="challenge-number" aria-hidden="true">
                    0{index + 1}
                  </span>
                  <span>{challenge.title}</span>
                </NavLink>
              ))}
              <div className="later-track">
                <span>Offensive</span>
                <span>Coming later</span>
              </div>
              <div className="later-track">
                <span>Defensive</span>
                <span>Coming later</span>
              </div>
            </nav>
            <section
              className="files-placeholder"
              aria-labelledby="files-title"
            >
              <h2 id="files-title">
                <Folder aria-hidden="true" />
                Workspace files
              </h2>
              <p>No Workspace is connected.</p>
            </section>
            {import.meta.env.DEV && (
              <Link className="developer-link" to="/dev/components">
                Component examples
              </Link>
            )}
          </div>
        </aside>
        <section className="workspace-pane" aria-label="Workspace pane">
          <div className="pane-heading">
            <h2>Workspace</h2>
            <span>No active Attempt</span>
          </div>
          <Tabs className="workspace-tabs" defaultValue="terminal">
            <TabsList aria-label="Workspace panels" variant="line">
              <TabsTrigger value="terminal">
                <Terminal aria-hidden="true" />
                Terminal
              </TabsTrigger>
              <TabsTrigger value="editor">
                <FileCode aria-hidden="true" />
                Editor
              </TabsTrigger>
              <TabsTrigger value="notes">
                <BookOpen aria-hidden="true" />
                Notes
              </TabsTrigger>
            </TabsList>
            <TabsContent value="terminal" keepMounted>
              <div className="workspace-empty">
                <Terminal aria-hidden="true" />
                <h3>Terminal not connected</h3>
                <p>
                  No terminal session is running. Terminal access will be available once a session starts.
                </p>
              </div>
            </TabsContent>
            <TabsContent value="editor" keepMounted>
              <div className="workspace-empty">
                <FileCode aria-hidden="true" />
                <h3>No file open</h3>
                <p>The editor will share saved files with the terminal.</p>
              </div>
            </TabsContent>
            <TabsContent value="notes" keepMounted>
              <div className="workspace-empty">
                <BookOpen aria-hidden="true" />
                <h3>Notes not available yet</h3>
                <p>Session notes will be saved in your Workspace.</p>
              </div>
            </TabsContent>
          </Tabs>
          <section
            className="session-details"
            aria-labelledby="sim-state-title"
          >
            <h2 id="sim-state-title">Satellite Sim state</h2>
            <p>No session connected. Telemetry is unavailable.</p>
          </section>
        </section>
        <main id="main-content" className="guide-pane" tabIndex={-1}>
          <div className="pane-heading">
            <h2>Challenge guide</h2>
            <span>Browse & learn</span>
          </div>
          <div className="page-content">
            <Outlet />
          </div>
        </main>
        <footer
          className="status-bar"
          aria-label="Connection and command status"
        >
          <span>
            <WifiOff aria-hidden="true" />
            Session services not connected
          </span>
          <span>Command delivery: unavailable</span>
        </footer>
      </div>
    </div>
  );
}
