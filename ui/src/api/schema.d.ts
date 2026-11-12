// Generated from FastAPI app.openapi() components.schemas for KSAT-62.
// Edit server/api/schemas.py and regenerate when the API changes.

export interface Challenge {
  challenge_id: string;
  title: string;
  availability: "available" | "locked";
  prerequisite_ids: (string)[];
  completed: boolean;
}

export interface ChallengeList {
  challenges: (Challenge)[];
  progress: Progress;
}

export interface Check {
  field: string;
  passed: boolean;
  message: string;
}

export interface Feedback {
  code: string;
  message: string;
}

export interface HistoryEntry {
  time: string;
  direction: "uplink" | "downlink";
  packet_hex: string;
  origin: "raw_player" | "satellite";
  pass_index: number | null;
  feedback: Feedback | null;
}

export interface PassView {
  pass_run_id: string;
  status: "not_started" | "running" | "finished" | "interrupted";
  receiver_ready: boolean;
  received_count: number;
}

export interface Progress {
  completed_challenge_ids: (string)[];
}

export interface Session {
  session_id: string;
  challenge_id: string;
  status: "starting" | "running" | "failed";
  state: StateView;
  history: (HistoryEntry)[];
  pass: PassView | null;
  goal_reached: boolean;
  completion: "not_yet" | "saved" | "save_failed";
  checks: (Check)[];
}

export interface SessionResponse {
  session: Session | null;
}

export interface StateView {
  mode: "SAFE" | "NOMINAL";
  antenna_deployed: boolean;
  deploy_count: number;
  heater_on: boolean;
  battery_pct: number;
  uptime_s: number;
  commands_received: number;
  last_seq_seen: number | null;
}
