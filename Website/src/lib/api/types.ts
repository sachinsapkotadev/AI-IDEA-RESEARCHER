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

// ---- API Error ----
export interface ApiErrorResponse {
  detail?: string | { code: string; message: string };
}

// ---- Future endpoints (not yet implemented in backend) ----
// These types are placeholders for when the backend adds these endpoints.

export interface Idea {
  id: number;
  title: string;
  problem: string;
  target_users: string;
  solution: string;
  category: string;
  status: 'draft' | 'validated' | 'in_progress' | 'archived';
  technical_complexity: 'low' | 'medium' | 'high';
  created_at: string;
  research_id?: number;
}

export interface Report {
  id: number;
  title: string;
  research_id: number;
  status: 'draft' | 'generated' | 'pushed';
  created_at: string;
  github_branch?: string;
}

export interface Agent {
  id: number;
  name: string;
  type: string;
  status: 'idle' | 'running' | 'error';
  model?: string;
  last_run?: string;
  tokens_used?: number;
}

export interface Model {
  id: number;
  provider: string;
  name: string;
  status: 'active' | 'unavailable';
  capabilities: string[];
  priority: number;
  last_checked?: string;
}

export interface GithubStatus {
  connected: boolean;
  repository?: string;
  branch?: string;
  recent_branches?: string[];
  last_sync?: string;
}

export interface AutomationConfig {
  daily_research: boolean;
  schedule: string;
  topics: string[];
  last_run?: string;
  next_run?: string;
  status: 'active' | 'paused' | 'error';
  notifications: boolean;
}
