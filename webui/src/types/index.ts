// User types
export interface User {
  id: number;
  username: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// Model types
export interface LLMModel {
  id: number;
  name: string;
  provider: string;
  model_type: string;
  api_base: string;
  model_identifier: string;
  description: string;
  is_active: boolean;
  created_at: string;
}

export interface LLMModelCreate {
  name: string;
  provider: string;
  model_type: string;
  api_base: string;
  api_key: string;
  model_identifier: string;
  description?: string;
}

// Dataset types
export interface DatasetItem {
  id: number;
  dataset_id: number;
  input_text: string;
  expected_output: string;
  scene_label: string;
  difficulty: string;
  sort_order: number;
  created_at: string;
}

export interface Dataset {
  id: number;
  name: string;
  description: string;
  scene: string;
  status: string;
  version: string;
  item_count: number;
  created_by: number | null;
  reviewer_id: number | null;
  review_comment: string;
  created_at: string;
  updated_at: string;
}

// Metric types
export interface Metric {
  id: number;
  name: string;
  code: string;
  description: string;
  metric_type: string;
  config_json: string;
  status: string;
  is_active: boolean;
  created_at: string;
}

// Eval types
export interface EvalTask {
  id: number;
  name: string;
  project_id: number | null;
  model_id: number;
  dataset_id: number;
  metric_ids: string;
  prompt_content: string;
  prompt_id: number | null;
  status: string;
  schedule_type: string;
  cron_expression: string;
  total_items: number;
  completed_items: number;
  overall_score: number;
  error_message: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface EvalResult {
  id: number;
  eval_task_id: number;
  dataset_item_id: number;
  model_output: string;
  expected_output: string;
  scores_json: string;
  latency_ms: number;
  created_at: string;
}

// Prompt / Optimization types
export interface Prompt {
  id: number;
  name: string;
  description: string;
  scene: string;
  current_version: string;
  current_content: string;
  best_score: number;
  project_id: number | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface PromptVersion {
  id: number;
  prompt_id: number;
  version: string;
  content: string;
  score: number;
  source: string;
  optimization_task_id: number | null;
  created_at: string;
}

export interface OptimizationTask {
  id: number;
  name: string;
  project_id: number | null;
  model_id: number;
  optimizer_model_id: number;
  dataset_id: number;
  initial_prompt: string;
  best_prompt: string;
  best_score: number;
  baseline_score: number;
  max_rounds: number;
  current_round: number;
  status: string;
  score_history_json: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface OptimizationRound {
  id: number;
  optimization_task_id: number;
  round_number: number;
  prompt_before: string;
  best_prompt_after: string;
  score_before: number;
  score_after: number;
  candidates_json: string;
  error_samples_json: string;
  created_at: string;
}

// Project types
export interface Project {
  id: number;
  name: string;
  description: string;
  project_type: string;
  status: string;
  created_by: number | null;
  created_at: string;
}

export interface ProjectDashboard {
  project: Project;
  dataset_count: number;
  eval_task_count: number;
  optimization_task_count: number;
  best_prompt_score: number;
  latest_eval_scores: string;
}

// Report types
export interface EvalReport {
  task_id: number;
  task_name: string;
  status: string;
  overall_score: number;
  total_items: number;
  metric_summary: Record<string, { avg: number; max: number; min: number; median: number }>;
  score_distribution: Record<string, number>;
  charts: {
    score_distribution: { categories: string[]; values: number[] };
    metric_comparison: { metrics: string[]; avg_scores: number[] };
    item_scores: { ids: number[]; scores: number[] };
  };
  item_details: Array<{
    result_id: number;
    dataset_item_id: number;
    model_output: string;
    expected_output: string;
    scores: Record<string, any>;
    avg_score: number;
    latency_ms: number;
  }>;
}

export interface OptimizationReport {
  task_id: number;
  task_name: string;
  status: string;
  baseline_score: number;
  best_score: number;
  improvement: number;
  total_rounds: number;
  current_round: number;
  best_prompt: string;
  initial_prompt: string;
  rounds: Array<{
    round_number: number;
    score_before: number;
    score_after: number;
    improvement: number;
    candidates: Array<{ index: number; prompt: string; score: number }>;
  }>;
  charts: {
    score_history: { rounds: string[]; scores: number[] };
    improvement_per_round: { rounds: number[]; improvements: number[] };
    prompt_evolution: { rounds: string[]; best_scores: number[] };
  };
}

// Common
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
