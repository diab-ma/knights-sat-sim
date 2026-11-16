// Generated from FastAPI app.openapi() components.schemas.

export interface ApiError {
  code: string;
  message: string;
}

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

export interface ErrorResponse {
  error: ApiError;
}

export interface Progress {
  completed_challenge_ids: (string)[];
}

export interface ResetProgressRequest {
  confirm: "RESET DEMO PROGRESS";
}


export interface ReadyBrief {
  scenario_id: string;
  brief: StationSetup;
  starting_setup: StationSetup;
}

export interface ReadyCheck {
  checks: (Check)[];
  completion: "not_yet" | "saved" | "save_failed";
}

export interface StationSetup {
  satellite_id: string;
  pass_start_utc: string;
  receive_frequency_hz: number;
  receive_mode: string;
  tracking_enabled: boolean;
}

export interface HTTPValidationError {
  detail?: (ValidationError)[];
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}
