export type ProgressMap = Record<string, Record<string, unknown>>;

export interface UserInfo {
  display_name: string;
  dojo_cohort: string;
}

export interface TaskItem {
  id: string;
  name: string;
  category: string;
  counts: Record<string, number>;
  start_count: number;
  progress_bar_suffix: string;
  scoreboard_display: string;
  number_of_cohorts: number;
  sort_priority: string;
  current_count: number;
  target_count: number | null;
}

export interface BootstrapResponse {
  user: UserInfo;
  tasks: TaskItem[];
  progress_by_requirement_id: ProgressMap;
  pinned_task_ids: string[];
  available_cohorts: string[];
  default_filters: Record<string, string>;
}

export interface SubmitProgressRequest {
  requirement_id: string;
  count_increment: number;
  minutes_spent: number;
}

export interface SubmitProgressResponse {
  submitted_payload: {
    cohort: string;
    requirementId: string;
    previousCount: number;
    newCount: number;
    incrementalMinutesSpent: number;
    date: string;
    notes: string;
  };
  upstream_response: unknown;
}

