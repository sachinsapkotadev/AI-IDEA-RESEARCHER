/**
 * Demo/mock data for pages without backend endpoints.
 * Clearly labeled as demo data. Never mixed with real API responses.
 *
 * These are used ONLY for pages where the backend does not yet
 * expose the corresponding endpoints (Ideas, Agents, Reports, etc.)
 */

import type { ResearchRun, ResearchSource } from './types';

// ---- Research demo data (used as fallback when backend is offline) ----

export const DEMO_RESEARCH_RUNS: ResearchRun[] = [
  {
    id: 1,
    topic: 'AI-powered code review tools for startups',
    status: 'completed',
    sources_found: 12,
    sources_used: 8,
    result: {
      topic: 'AI-powered code review tools for startups',
      summary: 'Growing market for AI code review tools targeting early-stage startups.',
      findings: [
        'Market growing at 25% CAGR',
        'Key players: CodeRabbit, Codacy, SonarQube',
        'Gap in startup-specific context',
      ],
      problems: [
        'Existing tools are expensive for early-stage startups',
        'No tool provides startup-specific code quality advice',
      ],
      opportunities: [
        'Affordable AI code review with startup context',
        'Integration with GitHub PR workflow',
      ],
      source_references: [],
        uncertainties: [
        'Long-term viability of AI code review market',
      ],
    },
    started_at: '2026-09-20T10:30:00Z',
    completed_at: '2026-09-20T10:33:00Z',
    created_at: '2026-09-20T10:30:00Z',
  },
  {
    id: 2,
    topic: 'SaaS automation for e-commerce returns',
    status: 'completed',
    sources_found: 15,
    sources_used: 10,
    result: {
      topic: 'SaaS automation for e-commerce returns',
      summary: 'E-commerce returns processing is a major pain point for small businesses.',
      findings: [
        'Average return rate: 20-30% for online retail',
        'Small businesses spend 15+ hours/week on returns',
        'Existing solutions target enterprise only',
      ],
      problems: [
        'Manual returns processing is time-consuming',
        'High cost of returns management for small stores',
      ],
      opportunities: [
        'AI-powered returns processing for Shopify stores',
        'Automated label generation and refund processing',
      ],
      source_references: [],
      uncertainties: [
        'Shopify platform dependency risk',
      ],
    },
    started_at: '2026-09-19T14:15:00Z',
    completed_at: '2026-09-19T14:19:00Z',
    created_at: '2026-09-19T14:15:00Z',
  },
  {
    id: 3,
    topic: 'Developer tools for API documentation',
    status: 'running',
    sources_found: 5,
    sources_used: 0,
    result: null,
    started_at: '2026-09-21T08:00:00Z',
    completed_at: null,
    created_at: '2026-09-21T08:00:00Z',
  },
];

export const DEMO_SOURCES: ResearchSource[] = [
  { id: 1, title: 'CodeRabbit - AI Code Reviews', url: 'https://coderabbit.ai', source_type: 'web', domain: 'coderabbit.ai', quality: 'high', status: 'success', word_count: 2400, rank: 1 },
  { id: 2, title: 'SonarQube Pricing', url: 'https://sonarcloud.io', source_type: 'web', domain: 'sonarcloud.io', quality: 'medium', status: 'success', word_count: 1800, rank: 2 },
  { id: 3, title: 'Codacy AI Review', url: 'https://codacy.com', source_type: 'web', domain: 'codacy.com', quality: 'high', status: 'success', word_count: 3100, rank: 3 },
];

// ---- Future endpoint demo data ----
// These will be replaced with real API calls when backend endpoints exist.

export const DEMO_IDEAS = [
  {
    id: 1,
    title: 'ReviewBot — AI Code Review for Early-Stage Startups',
    problem: 'Early-stage startups lack resources for thorough code reviews.',
    target_users: 'Solo founders and small dev teams (1-5 people)',
    solution: 'AI-powered code review with startup-specific context.',
    category: 'Developer Tools',
    status: 'validated' as const,
    technical_complexity: 'medium' as const,
    created_at: '2026-09-20T12:00:00Z',
    research_id: 1,
  },
  {
    id: 2,
    title: 'ReturnEasy — Automated E-commerce Returns',
    problem: 'E-commerce businesses spend 15+ hours/week processing returns.',
    target_users: 'Shopify and WooCommerce store owners',
    solution: 'AI agent that handles return requests automatically.',
    category: 'E-commerce',
    status: 'in_progress' as const,
    technical_complexity: 'high' as const,
    created_at: '2026-09-19T16:00:00Z',
    research_id: 2,
  },
];

export const DEMO_AGENTS = [
  { id: 1, name: 'Research Agent', type: 'researcher', status: 'idle' as const, model: 'claude-3.5-sonnet', last_run: '2026-09-21T08:00:00Z', tokens_used: 45200 },
  { id: 2, name: 'Market Analyst', type: 'analyst', status: 'idle' as const, model: 'gpt-4o', last_run: '2026-09-20T14:00:00Z', tokens_used: 32100 },
];

export const DEMO_REPORTS = [
  { id: 1, title: 'AI Code Review Tools — Market Analysis', research_id: 1, status: 'generated' as const, created_at: '2026-09-20T13:00:00Z' },
];

export const DEMO_GITHUB = {
  connected: false,
  repos_tracked: 0,
  trending: [],
};

export const DEMO_AUTOMATION = {
  enabled: false,
  schedule: '0 9 * * *',
  last_run: '2026-09-20T09:00:00Z',
  next_run: '2026-09-22T09:00:00Z',
  topics: ['AI-powered code review tools', 'SaaS automation for e-commerce'],
};

export const DEMO_MODELS = [
  { id: 1, provider: 'Anthropic', name: 'Claude 3.5 Sonnet', status: 'active' as const, capabilities: ['Research', 'Analysis', 'Writing'], priority: 1 },
  { id: 2, provider: 'OpenAI', name: 'GPT-4o', status: 'active' as const, capabilities: ['Research', 'Analysis', 'Code'], priority: 2 },
];
