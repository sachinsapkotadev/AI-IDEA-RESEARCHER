const API_BASE = import.meta.env.PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!res.ok) {
      if (res.status === 401) throw new ApiError('Unauthorized', 401);
      if (res.status === 403) throw new ApiError('Forbidden', 403);
      if (res.status === 404) throw new ApiError('Not found', 404);
      if (res.status >= 500) throw new ApiError('Server error', res.status);
      throw new ApiError(`Request failed: ${res.status}`, res.status);
    }

    return await res.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    // Backend unavailable or network error
    throw new ApiError('Backend unavailable', 0);
  }
}

// ---- Health ----
export async function getHealth() {
  return request<{ status: string }>('/api/health');
}

// ---- Research ----
export interface Research {
  id: string;
  topic: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
  duration?: number;
  ideas_count?: number;
  report_id?: string;
}

export async function getResearch(): Promise<Research[]> {
  return request<Research[]>('/api/research');
}

export async function getResearchById(id: string): Promise<Research> {
  return request<Research>(`/api/research/${id}`);
}

export async function createResearch(topic: string): Promise<Research> {
  return request<Research>('/api/research', {
    method: 'POST',
    body: JSON.stringify({ topic }),
  });
}

// ---- Ideas ----
export interface Idea {
  id: string;
  title: string;
  problem: string;
  target_users: string;
  solution: string;
  category: string;
  status: 'draft' | 'validated' | 'in_progress' | 'archived';
  technical_complexity: 'low' | 'medium' | 'high';
  created_at: string;
  research_id?: string;
}

export async function getIdeas(): Promise<Idea[]> {
  return request<Idea[]>('/api/ideas');
}

export async function getIdeaById(id: string): Promise<Idea> {
  return request<Idea>(`/api/ideas/${id}`);
}

// ---- Reports ----
export interface Report {
  id: string;
  title: string;
  research_id: string;
  status: 'draft' | 'generated' | 'pushed';
  created_at: string;
  github_branch?: string;
}

export async function getReports(): Promise<Report[]> {
  return request<Report[]>('/api/reports');
}

// ---- Agents ----
export interface Agent {
  id: string;
  name: string;
  type: string;
  status: 'idle' | 'running' | 'error';
  model?: string;
  last_run?: string;
  tokens_used?: number;
}

export async function getAgents(): Promise<Agent[]> {
  return request<Agent[]>('/api/agents');
}

// ---- Models ----
export interface Model {
  id: string;
  provider: string;
  name: string;
  status: 'active' | 'unavailable';
  capabilities: string[];
  priority: number;
  last_checked?: string;
}

export async function getModels(): Promise<Model[]> {
  return request<Model[]>('/api/models');
}

// ---- GitHub ----
export interface GithubStatus {
  connected: boolean;
  repository?: string;
  branch?: string;
  recent_branches?: string[];
  last_sync?: string;
}

export async function getGithubStatus(): Promise<GithubStatus> {
  return request<GithubStatus>('/api/github/status');
}

// ---- Automation ----
export interface AutomationConfig {
  daily_research: boolean;
  schedule: string;
  topics: string[];
  last_run?: string;
  next_run?: string;
  status: 'active' | 'paused' | 'error';
  notifications: boolean;
}

export async function getAutomationStatus(): Promise<AutomationConfig> {
  return request<AutomationConfig>('/api/automation');
}
