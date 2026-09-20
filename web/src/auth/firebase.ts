/**
 * Google sign-in.
 *
 * The browser holds the Firebase session; the backend only ever sees the ID
 * token, which it verifies itself.
 *
 * The Firebase project config is fetched from the backend at boot rather than
 * compiled in. Those six values are public - they name the project, they
 * authorise nothing - but fetching them means the same built bundle runs
 * locally and in deployment, and that `AUTH_MODE` on the backend is the only
 * switch: with it set to `dev` the backend sends no config, and sign-in here
 * becomes a local stub. The two halves cannot disagree about whether this
 * install has real accounts.
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

interface FirebaseConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  appId: string;
  storageBucket: string;
  messagingSenderId: string;
}

let config: FirebaseConfig | null = null;

/**
 * Awaited once, before the app renders. A backend that cannot be reached
 * leaves `config` null, which lands the player on the login screen and then
 * on the error screen - the honest outcome, and better than a blank page.
 */
export async function loadConfig(): Promise<void> {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;
    const body = await res.json();
    if (!body?.firebase) return;
    const f = body.firebase;
    config = {
      apiKey: f.api_key,
      authDomain: f.auth_domain,
      projectId: f.project_id,
      appId: f.app_id,
      storageBucket: f.storage_bucket,
      messagingSenderId: f.messaging_sender_id,
    };
  } catch {
    // Offline, or the backend is down. Handled as dev mode; the first real
    // API call will surface the failure properly.
  }
}

export function firebaseEnabled(): boolean {
  return config !== null;
}

let app: FirebaseApp | undefined;
let auth: Auth | undefined;

function client(): Auth {
  if (!auth) {
    app = initializeApp(config!);
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
  if (!firebaseEnabled()) return { name: 'Dev', email: 'dev@localhost' };
  const provider = new GoogleAuthProvider();
  const { user } = await signInWithPopup(client(), provider);
  return toAccount(user);
}

export async function signOut(): Promise<void> {
  if (firebaseEnabled()) await fbSignOut(client());
}

/** Attached as a bearer token to every backend call. Null in dev mode. */
export async function idToken(): Promise<string | null> {
  if (!firebaseEnabled()) return null;
  return (await client().currentUser?.getIdToken()) ?? null;
}

/**
 * Resolves once Firebase has restored (or ruled out) a persisted session, so
 * a refresh does not bounce the player back to the login screen.
 */
export function restore(): Promise<Account | null> {
  if (!firebaseEnabled()) return Promise.resolve(null);
  return new Promise((resolve) => {
    const stop = onAuthStateChanged(client(), (user) => {
      stop();
      resolve(user ? toAccount(user) : null);
    });
  });
}
