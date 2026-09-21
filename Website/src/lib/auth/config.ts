/**
 * Firebase configuration — reads public environment variables.
 *
 * These are CLIENT-side config values, not secrets.
 * They are safe to expose in browser JavaScript.
 */

export interface FirebaseConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  storageBucket: string;
  messagingSenderId: string;
  appId: string;
}

/**
 * Get Firebase config from environment variables.
 * Returns null if not configured (expected in development without Firebase).
 */
export function getFirebaseConfig(): FirebaseConfig | null {
  const apiKey = import.meta.env.PUBLIC_FIREBASE_API_KEY;
  const authDomain = import.meta.env.PUBLIC_FIREBASE_AUTH_DOMAIN;
  const projectId = import.meta.env.PUBLIC_FIREBASE_PROJECT_ID;
  const storageBucket = import.meta.env.PUBLIC_FIREBASE_STORAGE_BUCKET;
  const messagingSenderId = import.meta.env.PUBLIC_FIREBASE_MESSAGING_SENDER_ID;
  const appId = import.meta.env.PUBLIC_FIREBASE_APP_ID;

  // If no API key is set, Firebase is not configured
  if (!apiKey) return null;

  return {
    apiKey,
    authDomain: authDomain || '',
    projectId: projectId || '',
    storageBucket: storageBucket || '',
    messagingSenderId: messagingSenderId || '',
    appId: appId || '',
  };
}

/**
 * Check if Firebase is configured in the environment.
 */
export function isFirebaseConfigured(): boolean {
  return getFirebaseConfig() !== null;
}
