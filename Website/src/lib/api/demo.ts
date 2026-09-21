/**
 * Demo/mock data for when the backend is unavailable.
 * Clearly separated from real API responses.
 * Replace with real API calls when backend endpoints exist.
 */

import type { Research, Idea, Agent, Model, Report, GithubStatus, AutomationConfig } from './client';

export const DEMO_RESEARCH: Research[] = [
  {
    id: 'r-001',
    topic: 'AI-powered code review tools for startups',
    status: 'completed',
    created_at: '2026-09-20T10:30:00Z',
    duration: 180,
    ideas_count: 3,
    report_id: 'rep-001',
  },
  {
    id: 'r-002',
    topic: 'SaaS automation for e-commerce returns',
    status: 'completed',
    created_at: '2026-09-19T14:15:00Z',
    duration: 240,
    ideas_count: 2,
    report_id: 'rep-002',
  },
  {
    id: 'r-003',
    topic: 'Developer tools for API documentation',
    status: 'running',
    created_at: '2026-09-21T08:00:00Z',
    ideas_count: 0,
  },
  {
    id: 'r-004',
    topic: 'Market analysis: no-code AI builders',
    status: 'pending',
    created_at: '2026-09-21T09:00:00Z',
  },
];

export const DEMO_IDEAS: Idea[] = [
  {
    id: 'i-001',
    title: 'ReviewBot — AI Code Review for Early-Stage Startups',
    problem: 'Early-stage startups lack resources for thorough code reviews, leading to technical debt and security vulnerabilities.',
    target_users: 'Solo founders and small dev teams (1-5 people)',
    solution: 'AI-powered code review tool that provides instant, actionable feedback on PRs with startup-specific context.',
    category: 'Developer Tools',
    status: 'validated',
    technical_complexity: 'medium',
    created_at: '2026-09-20T12:00:00Z',
    research_id: 'r-001',
  },
  {
    id: 'i-002',
    title: 'ShipFast — CI/CD Pipeline Generator',
    problem: 'Setting up CI/CD takes days for small teams who just want to ship features.',
    target_users: 'Indie hackers and small startups',
    solution: 'One-click CI/CD pipeline generator with smart defaults for common stacks.',
    category: 'Developer Tools',
    status: 'draft',
    technical_complexity: 'high',
    created_at: '2026-09-20T12:30:00Z',
    research_id: 'r-001',
  },
  {
    id: 'i-003',
    title: 'ReturnEasy — Automated E-commerce Returns',
    problem: 'E-commerce businesses spend 15+ hours/week processing returns manually.',
    target_users: 'Shopify and WooCommerce store owners',
    solution: 'AI agent that handles return requests, generates labels, processes refunds, and analyzes return patterns.',
    category: 'E-commerce',
    status: 'in_progress',
    technical_complexity: 'high',
    created_at: '2026-09-19T16:00:00Z',
    research_id: 'r-002',
  },
  {
    id: 'i-004',
    title: 'DocuForge — AI API Documentation',
    problem: 'API docs are often outdated and take significant effort to maintain.',
    target_users: 'API-first startups and open-source maintainers',
    solution: 'AI that generates and maintains API documentation from code with automatic updates.',
    category: 'Developer Tools',
    status: 'draft',
    technical_complexity: 'medium',
    created_at: '2026-09-21T08:30:00Z',
  },
];

export const DEMO_AGENTS: Agent[] = [
  { id: 'a-001', name: 'Research Agent', type: 'researcher', status: 'idle', model: 'claude-3.5-sonnet', last_run: '2026-09-21T08:00:00Z', tokens_used: 45200 },
  { id: 'a-002', name: 'Market Analyst', type: 'analyst', status: 'idle', model: 'gpt-4o', last_run: '2026-09-20T14:00:00Z', tokens_used: 32100 },
  { id: 'a-003', name: 'Competitor Analyst', type: 'analyst', status: 'idle', model: 'claude-3.5-sonnet', last_run: '2026-09-20T14:30:00Z', tokens_used: 28400 },
  { id: 'a-004', name: 'Idea Generator', type: 'generator', status: 'running', model: 'gpt-4o', last_run: '2026-09-21T08:15:00Z', tokens_used: 67800 },
  { id: 'a-005', name: 'Technical Analyst', type: 'analyst', status: 'idle', model: 'claude-3.5-sonnet', last_run: '2026-09-20T15:00:00Z', tokens_used: 19600 },
  { id: 'a-006', name: 'Validation Planner', type: 'planner', status: 'idle', model: 'gpt-4o', last_run: '2026-09-20T16:00:00Z', tokens_used: 22300 },
  { id: 'a-007', name: 'Report Writer', type: 'writer', status: 'idle', model: 'claude-3.5-sonnet', last_run: '2026-09-20T16:30:00Z', tokens_used: 15900 },
];

export const DEMO_REPORTS: Report[] = [
  { id: 'rep-001', title: 'AI Code Review Tools — Market Analysis', research_id: 'r-001', status: 'pushed', created_at: '2026-09-20T13:00:00Z', github_branch: 'research/ai-code-review-2026-09-20' },
  { id: 'rep-002', title: 'E-commerce Returns Automation — Opportunity Report', research_id: 'r-002', status: 'generated', created_at: '2026-09-19T18:00:00Z' },
];

export const DEMO_MODELS: Model[] = [
  { id: 'm-001', provider: 'Anthropic', name: 'Claude 3.5 Sonnet', status: 'active', capabilities: ['Research', 'Analysis', 'Writing'], priority: 1, last_checked: '2026-09-21T00:00:00Z' },
  { id: 'm-002', provider: 'OpenAI', name: 'GPT-4o', status: 'active', capabilities: ['Research', 'Analysis', 'Code'], priority: 2, last_checked: '2026-09-21T00:00:00Z' },
  { id: 'm-003', provider: 'Google', name: 'Gemini 1.5 Pro', status: 'active', capabilities: ['Research', 'Analysis'], priority: 3, last_checked: '2026-09-21T00:00:00Z' },
  { id: 'm-004', provider: 'OpenAI', name: 'GPT-4o Mini', status: 'active', capabilities: ['Research', 'Writing'], priority: 4, last_checked: '2026-09-21T00:00:00Z' },
];

export const DEMO_GITHUB: GithubStatus = {
  connected: false,
  repository: null,
  branch: null,
  recent_branches: [],
  last_sync: null,
};

export const DEMO_AUTOMATION: AutomationConfig = {
  daily_research: false,
  schedule: '0 9 * * *',
  topics: [],
  status: 'paused',
  notifications: false,
};
