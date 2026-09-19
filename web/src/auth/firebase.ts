/**
 * Google sign-in.
 *
 * The browser holds the Firebase session; the backend only ever sees the ID
 * token, which it verifies itself. When no Firebase config is present - a
 * plain `bun run dev` with the backend in `AUTH_MODE=dev` - sign-in is a local
 * stub, so the whole app stays runnable without any cloud setup.
 */

import { initializeApp, type FirebaseApp } from 'firebase/app';
import {
  GoogleAuthProvider,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signOut as fbSignOut,
  type Auth,
  type User as FirebaseUser,
} from 'firebase/auth';

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
};

export const firebaseEnabled = Boolean(config.apiKey && config.projectId);

let app: FirebaseApp | undefined;
let auth: Auth | undefined;

function client(): Auth {
  if (!auth) {
    app = initializeApp(config);
    auth = getAuth(app);
  }
  return auth;
}

export interface Account {
  name: string;
  email: string;
}

function toAccount(user: FirebaseUser): Account {
  return { name: user.displayName ?? user.email ?? 'player', email: user.email ?? '' };
}

export async function signIn(): Promise<Account> {
  if (!firebaseEnabled) return { name: 'Dev', email: 'dev@localhost' };
  const provider = new GoogleAuthProvider();
  const { user } = await signInWithPopup(client(), provider);
  return toAccount(user);
}

export async function signOut(): Promise<void> {
  if (firebaseEnabled) await fbSignOut(client());
}

/** Attached as a bearer token to every backend call. Null in dev mode. */
export async function idToken(): Promise<string | null> {
  if (!firebaseEnabled) return null;
  return (await client().currentUser?.getIdToken()) ?? null;
}

/**
 * Resolves once Firebase has restored (or ruled out) a persisted session, so
 * a refresh does not bounce the player back to the login screen.
 */
export function restore(): Promise<Account | null> {
  if (!firebaseEnabled) return Promise.resolve(null);
  return new Promise((resolve) => {
    const stop = onAuthStateChanged(client(), (user) => {
      stop();
      resolve(user ? toAccount(user) : null);
    });
  });
}
