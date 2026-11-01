/**
 * Optional sign-in (docs/SESSIONS.md, Decisions, 2026-10-30): Google, or an email that carries
 * both a link and a 6-digit code, through Supabase Auth with the publishable key only (hard rule
 * 5). Guests play exactly as before.
 *
 * Off unless the site is built with VITE_ACCOUNTS=on and the project's address and publishable
 * key (VITE_SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY). Off, nothing here runs and no request
 * goes to Supabase. On, the auth library (@supabase/auth-js) is still loaded only when it is
 * needed: the visitor starts a sign-in, comes back from one, or already has a session in this
 * browser. A guest who never signs in downloads none of it.
 *
 * The session is kept in local storage under SESSION_KEY (no cookies). Sign-in uses the PKCE
 * flow, so a link works only in the browser that asked for it; the code works anywhere.
 */
import type { GoTrueClient } from "@supabase/auth-js";

/** Where the session is kept. The PKCE code verifier sits next to it, under this plus a suffix. */
export const SESSION_KEY = "cosmic-quiz:session";
/** The account page (wired into the router by ui). */
export const ACCOUNT_PATH = "/account";
/** Supabase sends a code of this many digits (its default). */
export const CODE_LENGTH = 6;

export const UNAVAILABLE = "Sign-in is not available right now. Try again later.";
export const LINK_IN_ANOTHER_BROWSER =
  "That sign-in link works only in the browser that asked for it. Enter the 6-digit code from " +
  "the email instead.";

// --- Configuration ------------------------------------------------------------------------------

/** The Supabase project the browser talks to: its address and publishable key. */
export interface SupabaseProject {
  url: string;
  key: string;
}

function envText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** The project, or null when the build was not given one. */
export function supabaseProject(): SupabaseProject | null {
  const url = envText(import.meta.env.VITE_SUPABASE_URL).replace(/\/+$/, "");
  const key = envText(import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY);
  return url && key ? { url, key } : null;
}

/** The build flag, compared as written so the bundler can drop the auth library from a build
 * without it. */
const FLAG_ON = import.meta.env.VITE_ACCOUNTS === "on";

/** Whether this build has accounts: the flag is on and a project is configured. */
export const ACCOUNTS_ENABLED = FLAG_ON && supabaseProject() !== null;

// --- Pure helpers -------------------------------------------------------------------------------

/** The search parameters Supabase adds when it sends a visitor back after a sign-in. */
const RETURN_PARAMS = ["code", "error", "error_code", "error_description"] as const;

/** Whether this address is a return from Supabase (a code to exchange, or an error). */
export function isAuthReturn(search: string): boolean {
  const params = new URLSearchParams(search);
  return params.has("code") || params.has("error_description");
}

/** The address without Supabase's return parameters: path, remaining search and hash. */
export function withoutAuthParams(url: URL): string {
  const params = new URLSearchParams(url.search);
  for (const name of RETURN_PARAMS) {
    params.delete(name);
  }
  const search = params.toString();
  return url.pathname + (search ? `?${search}` : "") + url.hash;
}

/** Whether this browser holds a saved session (read without loading the auth library). */
export function hasStoredSession(storage: Pick<Storage, "getItem"> | undefined): boolean {
  try {
    return storage?.getItem(SESSION_KEY) != null;
  } catch {
    return false;
  }
}

/** A plausible email address: one @, something on both sides, a dot in the domain. */
export function isEmail(text: string): boolean {
  const email = text.trim();
  return email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/** The digits of a typed code, or null unless there are exactly CODE_LENGTH of them. Spaces
 * and dashes are allowed, as people copy codes in groups. */
export function codeDigits(text: string): string | null {
  const digits = text.replace(/[\s-]/g, "");
  return new RegExp(`^\\d{${CODE_LENGTH}}$`).test(digits) ? digits : null;
}

// --- State --------------------------------------------------------------------------------------

/** The signed-in player, as the page needs it. */
export interface Account {
  id: string;
  email: string | null;
}

export type SessionState =
  /** Accounts are not in this build. */
  | { status: "off" }
  /** Checking a saved session or a return from a sign-in. */
  | { status: "loading" }
  /** Not signed in. `notice` says why a sign-in just failed, if one did. */
  | { status: "guest"; notice: string | null }
  | { status: "signed-in"; account: Account };

export const OFF: SessionState = { status: "off" };
const LOADING: SessionState = { status: "loading" };
const GUEST: SessionState = { status: "guest", notice: null };

/** The part of a Supabase session this module reads. */
export interface AuthSession {
  access_token: string;
  user: { id: string; email?: string | undefined };
}

interface AuthResult {
  error: { message: string } | null;
}

/**
 * The calls this module makes on the auth client: a subset of @supabase/auth-js's GoTrueClient,
 * so the tests can pass a fake one.
 */
export interface AuthApi {
  initialize(): Promise<AuthResult>;
  getSession(): Promise<{ data: { session: AuthSession | null } }>;
  onAuthStateChange(callback: (event: string, session: AuthSession | null) => void): unknown;
  signInWithOAuth(credentials: {
    provider: "google";
    options: { redirectTo: string };
  }): Promise<AuthResult>;
  signInWithOtp(credentials: {
    email: string;
    options: { emailRedirectTo: string; shouldCreateUser: boolean };
  }): Promise<AuthResult>;
  verifyOtp(params: {
    email: string;
    token: string;
    type: "email";
  }): Promise<AuthResult & { data: { session: AuthSession | null } }>;
  signOut(options: { scope: "local" }): Promise<AuthResult>;
}

/** What the session store needs from the browser, so the tests can stand in for it. */
export interface SessionDeps {
  enabled: boolean;
  storage: Pick<Storage, "getItem"> | undefined;
  /** The page's address now. */
  here: () => URL;
  /** Replace the address without a reload or a new history entry. */
  replaceUrl: (url: string) => void;
  /** Where Supabase sends the visitor back to after a sign-in. */
  returnTo: () => string;
  /** Load and construct the auth client (the dynamic import, in the browser). */
  load: () => Promise<AuthApi>;
}

export interface SessionStore {
  state(): SessionState;
  subscribe(listener: () => void): () => void;
  /** Check a saved session or a return from a sign-in, if there is one. Safe to call often. */
  start(): void;
  /** Each sign-in step returns an error message to show, or null when it went through. */
  signInWithGoogle(): Promise<string | null>;
  sendEmailCode(email: string): Promise<string | null>;
  verifyEmailCode(email: string, code: string): Promise<string | null>;
  signOut(): Promise<void>;
  /** The signed-in player's access token (refreshed when due), or null for a guest. */
  accessToken(): Promise<string | null>;
}

function signedIn(session: AuthSession): SessionState {
  return {
    status: "signed-in",
    account: { id: session.user.id, email: session.user.email ?? null },
  };
}

function sameState(a: SessionState, b: SessionState): boolean {
  if (a.status === "signed-in" && b.status === "signed-in") {
    return a.account.id === b.account.id && a.account.email === b.account.email;
  }
  if (a.status === "guest" && b.status === "guest") {
    return a.notice === b.notice;
  }
  return a.status === b.status;
}

/** Why a return from Supabase did not sign the visitor in, in words for the page. */
function returnNotice(here: URL, error: { message: string } | null): string | null {
  const params = new URLSearchParams(here.search);
  const described = params.get("error_description");
  if (described) {
    return described;
  }
  if (!error) {
    return null;
  }
  // The PKCE code verifier is kept in the browser that started the sign-in.
  return params.has("code") ? LINK_IN_ANOTHER_BROWSER : UNAVAILABLE;
}

export function createSessionStore(deps: SessionDeps): SessionStore {
  const needsCheck = () => hasStoredSession(deps.storage) || isAuthReturn(deps.here().search);
  let state: SessionState = !deps.enabled ? OFF : needsCheck() ? LOADING : GUEST;
  let client: Promise<AuthApi> | null = null;
  const listeners = new Set<() => void>();

  function set(next: SessionState): void {
    if (sameState(state, next)) {
      return;
    }
    state = next;
    for (const listener of listeners) {
      listener();
    }
  }

  /** The auth client, loaded and initialised once: a code in the address is exchanged for a
   * session and a saved session is refreshed if due. */
  function connect(): Promise<AuthApi> {
    client ??= (async () => {
      const api = await deps.load();
      const here = deps.here();
      const { error } = await api.initialize();
      if (isAuthReturn(here.search)) {
        deps.replaceUrl(withoutAuthParams(here));
      }
      const { data } = await api.getSession();
      set(
        data.session
          ? signedIn(data.session)
          : { status: "guest", notice: returnNotice(here, error) },
      );
      // Fires on every sign-in, sign-out and token refresh, in this tab and others.
      api.onAuthStateChange((_event, session) => {
        set(session ? signedIn(session) : GUEST);
      });
      return api;
    })().catch((error: unknown) => {
      client = null;
      set({ status: "guest", notice: UNAVAILABLE });
      throw error;
    });
    return client;
  }

  async function connected(): Promise<AuthApi | null> {
    if (!deps.enabled) {
      return null;
    }
    try {
      return await connect();
    } catch {
      return null;
    }
  }

  return {
    state: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    start() {
      if (state.status === "loading") {
        void connected();
      }
    },
    async signInWithGoogle() {
      const api = await connected();
      if (!api) {
        return UNAVAILABLE;
      }
      // On success the browser leaves for Google; this page does not continue.
      const { error } = await api.signInWithOAuth({
        provider: "google",
        options: { redirectTo: deps.returnTo() },
      });
      return error ? error.message : null;
    },
    async sendEmailCode(email) {
      if (!isEmail(email)) {
        return "Enter your email address.";
      }
      const api = await connected();
      if (!api) {
        return UNAVAILABLE;
      }
      const { error } = await api.signInWithOtp({
        email: email.trim(),
        options: { emailRedirectTo: deps.returnTo(), shouldCreateUser: true },
      });
      return error ? error.message : null;
    },
    async verifyEmailCode(email, code) {
      const digits = codeDigits(code);
      if (!digits) {
        return `Enter the ${CODE_LENGTH}-digit code from the email.`;
      }
      const api = await connected();
      if (!api) {
        return UNAVAILABLE;
      }
      const { data, error } = await api.verifyOtp({
        email: email.trim(),
        token: digits,
        type: "email",
      });
      if (error) {
        return error.message;
      }
      if (data.session) {
        set(signedIn(data.session));
      }
      return null;
    },
    async signOut() {
      const api = client ? await connected() : null;
      // "local" ends this browser's session only; other devices stay signed in.
      await api?.signOut({ scope: "local" });
      set(deps.enabled ? GUEST : OFF);
    },
    async accessToken() {
      if (state.status !== "signed-in" && state.status !== "loading") {
        return null;
      }
      const api = await connected();
      if (!api) {
        return null;
      }
      const { data } = await api.getSession();
      return data.session?.access_token ?? null;
    },
  };
}

// --- The browser's store ------------------------------------------------------------------------

function browserDeps(): SessionDeps {
  const project = supabaseProject();
  const enabled = ACCOUNTS_ENABLED && project !== null && typeof window !== "undefined";
  let storage: Storage | undefined;
  try {
    storage = enabled ? window.localStorage : undefined;
  } catch {
    storage = undefined;
  }
  return {
    enabled,
    storage,
    here: () => new URL(window.location.href),
    replaceUrl: (url) => window.history.replaceState(window.history.state, "", url),
    returnTo: () => window.location.origin + window.location.pathname,
    async load() {
      if (!FLAG_ON || !project) {
        throw new Error("accounts are not configured");
      }
      const { GoTrueClient } = await import("@supabase/auth-js");
      const auth: GoTrueClient = new GoTrueClient({
        url: `${project.url}/auth/v1`,
        headers: { apikey: project.key },
        storageKey: SESSION_KEY,
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        flowType: "pkce",
      });
      return auth;
    },
  };
}

/** The one session of this page. */
export const session: SessionStore = createSessionStore(browserDeps());

/** The header the API needs to know who is signed in: `{ Authorization: "Bearer <token>" }`, or
 * nothing for a guest (and nothing is loaded or sent to find that out). For src/api.ts. */
export async function authHeader(): Promise<Record<string, string>> {
  const token = await session.accessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
