/**
 * Authentication service for the AI Idea Researcher frontend.
 *
 * This module provides a clean interface for authentication.
 * Currently returns unauthenticated state — no fake tokens or sessions.
 *
 * When Firebase authentication is enabled, this module will:
 * 1. Initialize Firebase Auth
 * 2. Track auth state changes
 * 3. Provide ID tokens for backend API authorization
 *
 * Security notes:
 * - Firebase ID tokens are attached to API requests via Authorization header
 * - The backend MUST verify Firebase tokens before granting access
 * - Frontend-only "protection" is NOT security
 * - This module never stores secrets in localStorage/cookies
 */

import type { AuthState, AuthStateCallback, AuthService, User } from './types';
import { UNAUTHENTICATED_STATE, LOADING_STATE } from './types';

/**
 * Current auth state (client-side only).
 */
let currentState: AuthState = LOADING_STATE;
const listeners: Set<AuthStateCallback> = new Set();

/**
 * Notify all listeners of state change.
 */
function notifyListeners(): void {
  listeners.forEach((cb) => {
    try {
      cb(currentState);
    } catch {
      // Don't let listener errors break the auth system
    }
  });
}

/**
 * Update auth state.
 */
function setState(state: AuthState): void {
  currentState = state;
  notifyListeners();
}

/**
 * Get the current authentication state.
 */
export function getAuthState(): AuthState {
  return currentState;
}

/**
 * Check if the user is authenticated.
 */
export function isAuthenticated(): boolean {
  return currentState.isAuthenticated && currentState.user !== null;
}

/**
 * Get the current user.
 */
export function getCurrentUser(): User | null {
  return currentState.user;
}

/**
 * Subscribe to auth state changes.
 * Returns an unsubscribe function.
 */
export function onAuthStateChanged(callback: AuthStateCallback): () => void {
  listeners.add(callback);
  // Immediately call with current state
  callback(currentState);
  return () => {
    listeners.delete(callback);
  };
}

/**
 * Get a Firebase ID token for API authorization.
 * Returns null when not authenticated.
 *
 * When Firebase is connected, this will call:
 * firebase.auth().currentUser.getIdToken()
 */
export async function getIdToken(): Promise<string | null> {
  if (!currentState.isAuthenticated || !currentState.user) {
    return null;
  }
  // TODO: Replace with real Firebase token when Firebase Auth is connected
  // return firebase.auth().currentUser?.getIdToken() ?? null;
  return null;
}

/**
 * Sign out the current user.
 */
export async function signOut(): Promise<void> {
  // TODO: Replace with real Firebase signout
  // await firebase.auth().signOut();
  setState(UNAUTHENTICATED_STATE);
  if (typeof window !== 'undefined') {
    window.location.href = '/';
  }
}

/**
 * Initialize authentication.
 *
 * Call this once when the app starts.
 * When Firebase is connected, this will:
 * 1. Initialize Firebase app
 * 2. Start listening for auth state changes
 * 3. Set up the auth state persistence
 */
export function initAuth(): void {
  // Check if Firebase is configured
  const apiKey = import.meta.env.PUBLIC_FIREBASE_API_KEY;

  if (!apiKey) {
    // Firebase not configured — set unauthenticated state
    setState(UNAUTHENTICATED_STATE);
    return;
  }

  // TODO: Initialize Firebase Auth when SDK is installed
  // import { initializeApp } from 'firebase/app';
  // import { getAuth, onAuthStateChanged } from 'firebase/auth';
  //
  // const app = initializeApp(getFirebaseConfig());
  // const auth = getAuth(app);
  //
  // onAuthStateChanged(auth, (firebaseUser) => {
  //   if (firebaseUser) {
  //     setState({
  //       isAuthenticated: true,
  //       user: {
  //         uid: firebaseUser.uid,
  //         email: firebaseUser.email,
  //         displayName: firebaseUser.displayName,
  //         photoURL: firebaseUser.photoURL,
  //       },
  //       isLoading: false,
  //     });
  //   } else {
  //     setState(UNAUTHENTICATED_STATE);
  //   }
  // });

  // For now, just set unauthenticated
  setState(UNAUTHENTICATED_STATE);
}

// Export the auth service interface for components that need it
export const authService: AuthService = {
  getState: getAuthState,
  onStateChange: onAuthStateChanged,
  getIdToken,
  signOut,
};

export type { AuthState, AuthStateCallback, User } from './types';
