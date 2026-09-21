/**
 * API client for the AI Idea Researcher backend.
 *
 * All backend communication goes through this module.
 * Uses only PUBLIC_* env vars exposed to the browser.
 */

import type {
  HealthResponse,
  ResearchRun,
  ResearchListResponse,
  ResearchCreateRequest,
  ResearchSourcesResponse,
} from './types';

const API_BASE = import.meta.env.PUBLIC_API_URL || 'http://localhost:8000';

// ---- Error Handling ----

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

/**
 * Parse backend error response into a user-friendly message.
 */
function parseErrorMessage(data: unknown, status: number): string {
  if (typeof data === 'object' && data !== null) {
    const obj = data as Record<string, unknown>;

    // AIErrorResponse format: { detail: { code, message } }
    if (obj.detail && typeof obj.detail === 'object') {
      const detail = obj.detail as Record<string, unknown>;
      if (detail.message) return String(detail.message);
      if (detail.code) return String(detail.code);
    }

    // Simple detail string
    if (typeof obj.detail === 'string') return obj.detail;

    // Error message field
    if (typeof obj.message === 'string') return obj.message;
    if (typeof obj.error === 'string') return obj.error;
  }

  // Fallback by status code
  const statusMessages: Record<number, string> = {
    400: 'Invalid request',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'Not found',
    422: 'Validation error',
    429: 'Too many requests. Try again later.',
    500: 'Server error',
    502: 'Backend gateway error',
    503: 'Service temporarily unavailable',
    504: 'Request timed out',
  };

  return statusMessages[status] || `Request failed (${status})`;
}

/**
 * Make an API request with proper error handling.
 */
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;

  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
  } catch (err) {
    // Network failure / backend unavailable
    throw new ApiError(
      'Unable to connect to the backend. Please check if the server is running.',
      0,
    );
  }

  // Parse response body
  let data: unknown;
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      data = await res.json();
    } catch {
      throw new ApiError('Invalid response from server', res.status);
    }
  } else {
    data = await res.text();
  }

  if (!res.ok) {
    const message = parseErrorMessage(data, res.status);
    const code =
      typeof data === 'object' && data !== null
        ? ((data as Record<string, unknown>).detail &&
            typeof (data as Record<string, unknown>).detail === 'object'
            ? ((data as Record<string, unknown>).detail as Record<string, unknown>)
                .code as string | undefined
            : undefined)
        : undefined;
    throw new ApiError(message, res.status, code);
  }

  return data as T;
}

// ---- Health ----

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

// ---- Research ----

export async function getResearchList(
  page = 1,
  pageSize = 20,
): Promise<ResearchListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return request<ResearchListResponse>(`/api/research?${params}`);
}

export async function getResearchById(id: number): Promise<ResearchRun> {
  return request<ResearchRun>(`/api/research/${id}`);
}

export async function createResearch(
  topic: string,
): Promise<ResearchRun> {
  const body: ResearchCreateRequest = { topic };
  return request<ResearchRun>('/api/research', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getResearchSources(
  researchId: number,
): Promise<ResearchSourcesResponse> {
  return request<ResearchSourcesResponse>(`/api/research/${researchId}/sources`);
}
