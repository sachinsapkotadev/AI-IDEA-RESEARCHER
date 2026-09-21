/**
 * Authentication abstraction layer.
 *
 * This module provides a clean interface for future authentication.
 * Currently returns unauthenticated state — no fake tokens or sessions.
 *
 * When backend auth is implemented, replace these functions with
 * real API calls.
 */

export interface User {
  id: string;
  name: string;
  email: string;
  plan: 'free' | 'pro' | 'enterprise';
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
}

/**
 * Get the current authenticated user.
 * Returns null when not authenticated.
 */
export function getCurrentUser(): User | null {
  // TODO: Replace with real auth check when backend auth is implemented
  return null;
}

/**
 * Check if the user is authenticated.
 */
export function isAuthenticated(): boolean {
  return getCurrentUser() !== null;
}

/**
 * Get the current auth state.
 */
export function getAuthState(): AuthState {
  const user = getCurrentUser();
  return {
    isAuthenticated: user !== null,
    user,
  };
}

/**
 * Log out the current user.
 * Placeholder — no real session to destroy yet.
 */
export function logout(): void {
  // TODO: Clear session/token when auth is implemented
  if (typeof window !== 'undefined') {
    window.location.href = '/';
  }
}
