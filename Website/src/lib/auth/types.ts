/**
 * Authentication types for the AI Idea Researcher frontend.
 *
 * These types define the auth abstraction layer.
 * When Firebase is connected, these types are populated with real data.
 */

/**
 * User profile from Firebase Auth.
 */
export interface User {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
}

/**
 * Authentication state.
 */
export interface AuthState {
  /** Whether the user is authenticated. */
  isAuthenticated: boolean;
  /** The current user, or null if not authenticated. */
  user: User | null;
  /** Whether auth state is still loading. */
  isLoading: boolean;
}

/**
 * Auth state change callback type.
 */
export type AuthStateCallback = (state: AuthState) => void;

/**
 * Auth service interface — abstraction over Firebase Auth.
 * This allows swapping auth providers without rewriting components.
 */
export interface AuthService {
  /** Get the current auth state. */
  getState(): AuthState;
  /** Subscribe to auth state changes. Returns unsubscribe function. */
  onStateChange(callback: AuthStateCallback): () => void;
  /** Get a Firebase ID token for API authorization. Returns null if not authenticated. */
  getIdToken(): Promise<string | null>;
  /** Sign out the current user. */
  signOut(): Promise<void>;
}

/**
 * Default unauthenticated state.
 */
export const UNAUTHENTICATED_STATE: AuthState = {
  isAuthenticated: false,
  user: null,
  isLoading: false,
};

/**
 * Loading state (initial).
 */
export const LOADING_STATE: AuthState = {
  isAuthenticated: false,
  user: null,
  isLoading: true,
};
