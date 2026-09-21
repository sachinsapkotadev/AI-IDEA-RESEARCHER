/**
 * TypeScript types for the AI Idea Researcher backend API.
 * Aligned with actual FastAPI schemas from the backend.
 */

// ---- Health ----
export interface HealthResponse {
  status: string;
}

export interface DatabaseHealthResponse {
  status: string;
  database: string;
}

export interface AiHealthResponse {
  status: string;
  provider: string;
  configured_keys: number;
}

export interface GithubHealthResponse {
  status: string;
  configured: boolean;
}

// ---- Research ----
export type ResearchStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface ResearchResult {
  topic: string;
  summary: string;
  findings: string[];
  problems: string[];
  opportunities: string[];
  source_references: string[];
  uncertainties: string[];
}

export interface ResearchRun {
  id: number;
  topic: string;
  status: ResearchStatus;
  sources_found: number;
  sources_used: number;
  result: ResearchResult | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ResearchRunResponse {
  id: number;
  topic: string;
  status: ResearchStatus;
  sources_found: number;
  sources_used: number;
  result: ResearchResult | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ResearchListResponse {
  items: ResearchRun[];
  total: number;
  page: number;
  page_size: number;
}

export interface ResearchCreateRequest {
  topic: string;
}

// ---- Sources ----
export type SourceStatus = 'success' | 'failed' | 'unknown' | 'partial';
export type SourceType = 'web' | 'news' | 'academic' | 'other';

export interface ResearchSource {
  id: number;
  title: string;
  url: string | null;
  source_type: SourceType;
  domain: string | null;
  quality: string | null;
  status: SourceStatus;
  word_count: number | null;
  rank: number | null;
}

export interface ResearchSourcesResponse {
  research_id: number;
  topic: string;
  sources: ResearchSource[];
}

// ---- Analysis ----
export interface AnalysisAcceptResponse {
  research_id: number;
  status: 'accepted';
  message: string;
}

export interface AnalysisStatusResponse {
  research_id: number;
  status: string;
  current_agent: string | null;
  completed_agents: number;
  total_agents: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface AgentRun {
  agent_name: string;
  status: string;
  model: string | null;
  started_at: string | null;
  completed_at: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
}

export interface AgentsResponse {
  research_id: number;
  agents: AgentRun[];
}

// ---- Ideas ----
export type IdeaStatus = 'draft' | 'validated' | 'in_progress' | 'archived';

export interface Idea {
  id: number;
  research_run_id: number;
  title: string;
  problem: string;
  solution: string;
  target_users: string;
  mvp: string;
  monetization: string;
  differentiation: string;
  technical_complexity: string;
  risks: string;
  validation_plan: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface IdeaListResponse {
  items: Idea[];
  total: number;
  page: number;
  page_size: number;
}

export interface ResearchIdeasResponse {
  research_id: number;
  topic: string;
  ideas: Idea[];
}

// ---- Report ----
export interface ReportTriggerResponse {
  research_id: number;
  status: string;
  message?: string;
}

export interface ReportContent {
  research_id: number;
  content: string | null;
  status: string;
  created_at?: string;
}

// ---- GitHub ----
export interface GithubPublishResponse {
  research_id: number;
  status: string;
  message?: string;
  branch?: string;
}

export interface GithubPublicationStatus {
  research_id: number;
  status: string;
  branch?: string;
  repository?: string;
  message?: string;
}

// ---- AI Status ----
export interface AiStatusResponse {
  provider: string;
  configured_key_slots: number;
  available_key_slots: number;
  default_model: string;
  status: string;
}

export interface AiModelsResponse {
  models: Record<string, string>;
}

// ---- API Error ----
export interface ApiErrorResponse {
  detail?: string | { code: string; message: string };
}
