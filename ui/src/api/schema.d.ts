// Generated from FastAPI OpenAPI components.schemas for KSAT-87.

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
