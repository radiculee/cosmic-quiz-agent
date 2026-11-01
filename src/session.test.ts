import { describe, expect, it } from "vitest";

import {
  ACCOUNTS_ENABLED,
  type AuthApi,
  type AuthSession,
  codeDigits,
  createSessionStore,
  hasStoredSession,
  isAuthReturn,
  isEmail,
  LINK_IN_ANOTHER_BROWSER,
  SESSION_KEY,
  type SessionDeps,
  session,
  UNAVAILABLE,
  withoutAuthParams,
} from "./session";

const PLAYER: AuthSession = {
  access_token: "token-1",
  user: { id: "0b0e6f9c-3f5e-4d0a-9a43-6f1d2b7c8e10", email: "player@example.com" },
};

/** A stand-in for @supabase/auth-js that records each call. */
class FakeAuth implements AuthApi {
  calls: string[] = [];
  session: AuthSession | null;
  initError: { message: string } | null = null;
  replyError: { message: string } | null = null;
  lastArgs: unknown = null;
  private listener: ((event: string, session: AuthSession | null) => void) | null = null;

  constructor(session: AuthSession | null = null) {
    this.session = session;
  }

  async initialize() {
    this.calls.push("initialize");
    return { error: this.initError };
  }

  async getSession() {
    this.calls.push("getSession");
    return { data: { session: this.session } };
  }

  onAuthStateChange(callback: (event: string, session: AuthSession | null) => void) {
    this.listener = callback;
    return {};
  }

  async signInWithOAuth(credentials: Parameters<AuthApi["signInWithOAuth"]>[0]) {
    this.calls.push("signInWithOAuth");
    this.lastArgs = credentials;
    return { error: this.replyError };
  }

  async signInWithOtp(credentials: Parameters<AuthApi["signInWithOtp"]>[0]) {
    this.calls.push("signInWithOtp");
    this.lastArgs = credentials;
    return { error: this.replyError };
  }

  async verifyOtp(params: Parameters<AuthApi["verifyOtp"]>[0]) {
    this.calls.push("verifyOtp");
    this.lastArgs = params;
    return { data: { session: this.replyError ? null : PLAYER }, error: this.replyError };
  }

  async signOut(options: { scope: "local" }) {
    this.calls.push("signOut");
    this.lastArgs = options;
    this.session = null;
    return { error: null };
  }

  /** Supabase reporting a change, as it does on sign-in, sign-out or a refresh in any tab. */
  emit(session: AuthSession | null) {
    this.listener?.("SIGNED_IN", session);
  }
}

interface Harness {
  deps: SessionDeps;
  auth: FakeAuth;
  loads: () => number;
  replaced: string[];
}

function harness(
  options: { enabled?: boolean; stored?: boolean; url?: string; auth?: FakeAuth } = {},
): Harness {
  const auth = options.auth ?? new FakeAuth();
  let loads = 0;
  const replaced: string[] = [];
  const deps: SessionDeps = {
    enabled: options.enabled ?? true,
    storage: { getItem: (key) => (options.stored && key === SESSION_KEY ? "{}" : null) },
    here: () => new URL(options.url ?? "https://curiosity.example/quiz"),
    replaceUrl: (url) => replaced.push(url),
    returnTo: () => "https://curiosity.example/quiz",
    load: async () => {
      loads += 1;
      return auth;
    },
  };
  return { deps, auth, loads: () => loads, replaced };
}

/** Let the store's pending promises settle. */
async function settle() {
  for (let i = 0; i < 5; i += 1) {
    await Promise.resolve();
  }
}

describe("the helpers", () => {
  it("recognises a return from Supabase", () => {
    expect(isAuthReturn("?code=abc")).toBe(true);
    expect(isAuthReturn("?error=access_denied&error_description=Denied")).toBe(true);
    expect(isAuthReturn("?topic=Mars")).toBe(false);
    expect(isAuthReturn("")).toBe(false);
  });

  it("removes only Supabase's parameters from an address", () => {
    const url = new URL("https://curiosity.example/explore?topic=Mars&code=abc&error=x#top");
    expect(withoutAuthParams(url)).toBe("/explore?topic=Mars#top");
    expect(withoutAuthParams(new URL("https://curiosity.example/quiz?code=abc"))).toBe("/quiz");
  });

  it("finds a saved session without the auth library, and survives blocked storage", () => {
    expect(hasStoredSession({ getItem: (key) => (key === SESSION_KEY ? "{}" : null) })).toBe(true);
    expect(hasStoredSession({ getItem: () => null })).toBe(false);
    expect(hasStoredSession(undefined)).toBe(false);
    const blocked = {
      getItem: (): string | null => {
        throw new Error("blocked");
      },
    };
    expect(hasStoredSession(blocked)).toBe(false);
  });

  it("accepts a plausible email address", () => {
    expect(isEmail(" player@example.com ")).toBe(true);
    expect(isEmail("player@example")).toBe(false);
    expect(isEmail("player example.com")).toBe(false);
    expect(isEmail("")).toBe(false);
    expect(isEmail(`${"a".repeat(250)}@x.ie`)).toBe(false);
  });

  it("reads a 6-digit code typed with spaces or a dash", () => {
    expect(codeDigits("123456")).toBe("123456");
    expect(codeDigits("123 456")).toBe("123456");
    expect(codeDigits("123-456")).toBe("123456");
    expect(codeDigits("12345")).toBeNull();
    expect(codeDigits("12345a")).toBeNull();
  });
});

describe("with accounts off", () => {
  it("is off in a build without the flag, as in these tests", () => {
    expect(ACCOUNTS_ENABLED).toBe(false);
    expect(session.state()).toEqual({ status: "off" });
  });

  it("never loads the auth library or sends anything", async () => {
    const h = harness({ enabled: false, stored: true, url: "https://curiosity.example/?code=x" });
    const store = createSessionStore(h.deps);
    store.start();
    expect(store.state()).toEqual({ status: "off" });
    expect(await store.accessToken()).toBeNull();
    expect(await store.signInWithGoogle()).toBe(UNAVAILABLE);
    expect(await store.sendEmailCode("player@example.com")).toBe(UNAVAILABLE);
    await store.signOut();
    expect(h.loads()).toBe(0);
    expect(h.auth.calls).toEqual([]);
  });
});

describe("a guest", () => {
  it("loads nothing until they start a sign-in", async () => {
    const h = harness();
    const store = createSessionStore(h.deps);
    store.start();
    await settle();
    expect(store.state()).toEqual({ status: "guest", notice: null });
    expect(await store.accessToken()).toBeNull();
    expect(h.loads()).toBe(0);
  });

  it("signs in with Google, coming back to the same page", async () => {
    const h = harness();
    const store = createSessionStore(h.deps);
    expect(await store.signInWithGoogle()).toBeNull();
    expect(h.auth.lastArgs).toEqual({
      provider: "google",
      options: { redirectTo: "https://curiosity.example/quiz" },
    });
  });

  it("is sent an email with a link and a code, then signs in with the code", async () => {
    const h = harness();
    const store = createSessionStore(h.deps);
    const seen: string[] = [];
    store.subscribe(() => seen.push(store.state().status));

    expect(await store.sendEmailCode(" player@example.com ")).toBeNull();
    expect(h.auth.lastArgs).toEqual({
      email: "player@example.com",
      options: { emailRedirectTo: "https://curiosity.example/quiz", shouldCreateUser: true },
    });

    expect(await store.verifyEmailCode("player@example.com", "123 456")).toBeNull();
    expect(h.auth.lastArgs).toEqual({
      email: "player@example.com",
      token: "123456",
      type: "email",
    });
    expect(store.state()).toEqual({
      status: "signed-in",
      account: { id: PLAYER.user.id, email: "player@example.com" },
    });
    expect(seen).toContain("signed-in");
  });

  it("is told what to fix before anything is sent", async () => {
    const h = harness();
    const store = createSessionStore(h.deps);
    expect(await store.sendEmailCode("not an email")).toBe("Enter your email address.");
    expect(await store.verifyEmailCode("player@example.com", "12")).toBe(
      "Enter the 6-digit code from the email.",
    );
    expect(h.loads()).toBe(0);
  });

  it("sees Supabase's message when a step is refused", async () => {
    const auth = new FakeAuth();
    auth.replyError = { message: "Token has expired or is invalid" };
    const store = createSessionStore(harness({ auth }).deps);
    expect(await store.verifyEmailCode("player@example.com", "123456")).toBe(
      "Token has expired or is invalid",
    );
    expect(store.state()).toEqual({ status: "guest", notice: null });
  });

  it("can try again after the auth library failed to load", async () => {
    const h = harness();
    let fail = true;
    const store = createSessionStore({
      ...h.deps,
      load: async () => {
        if (fail) {
          throw new Error("offline");
        }
        return h.auth;
      },
    });
    expect(await store.signInWithGoogle()).toBe(UNAVAILABLE);
    expect(store.state()).toEqual({ status: "guest", notice: UNAVAILABLE });
    fail = false;
    expect(await store.signInWithGoogle()).toBeNull();
  });
});

describe("a saved session", () => {
  it("is checked on start and gives the access token", async () => {
    const h = harness({ stored: true, auth: new FakeAuth(PLAYER) });
    const store = createSessionStore(h.deps);
    expect(store.state()).toEqual({ status: "loading" });
    store.start();
    store.start();
    await settle();
    expect(h.loads()).toBe(1);
    expect(store.state()).toEqual({
      status: "signed-in",
      account: { id: PLAYER.user.id, email: "player@example.com" },
    });
    expect(await store.accessToken()).toBe("token-1");
  });

  it("that has ended leaves a guest", async () => {
    const h = harness({ stored: true, auth: new FakeAuth(null) });
    const store = createSessionStore(h.deps);
    store.start();
    await settle();
    expect(store.state()).toEqual({ status: "guest", notice: null });
  });

  it("follows Supabase's sign-in changes, telling listeners only of real ones", async () => {
    const h = harness({ stored: true, auth: new FakeAuth(PLAYER) });
    const store = createSessionStore(h.deps);
    let told = 0;
    store.subscribe(() => {
      told += 1;
    });
    store.start();
    await settle();
    expect(told).toBe(1);
    h.auth.emit({ ...PLAYER, access_token: "token-2" });
    expect(told).toBe(1);
    h.auth.emit(null);
    expect(store.state()).toEqual({ status: "guest", notice: null });
    expect(told).toBe(2);
  });

  it("signs out in this browser only", async () => {
    const h = harness({ stored: true, auth: new FakeAuth(PLAYER) });
    const store = createSessionStore(h.deps);
    store.start();
    await settle();
    await store.signOut();
    expect(h.auth.lastArgs).toEqual({ scope: "local" });
    expect(store.state()).toEqual({ status: "guest", notice: null });
    expect(await store.accessToken()).toBeNull();
  });
});

describe("a return from a sign-in", () => {
  it("is exchanged for a session and the code is taken out of the address", async () => {
    const url = "https://curiosity.example/explore?topic=Mars&code=abc";
    const h = harness({ url, auth: new FakeAuth(PLAYER) });
    const store = createSessionStore(h.deps);
    expect(store.state()).toEqual({ status: "loading" });
    store.start();
    await settle();
    expect(h.replaced).toEqual(["/explore?topic=Mars"]);
    expect(store.state().status).toBe("signed-in");
  });

  it("opened in another browser asks for the code instead", async () => {
    const auth = new FakeAuth(null);
    auth.initError = { message: "PKCE code verifier not found in storage." };
    const h = harness({ url: "https://curiosity.example/quiz?code=abc", auth });
    const store = createSessionStore(h.deps);
    store.start();
    await settle();
    expect(store.state()).toEqual({ status: "guest", notice: LINK_IN_ANOTHER_BROWSER });
    expect(h.replaced).toEqual(["/quiz"]);
  });

  it("with an error shows Supabase's description", async () => {
    const url = "https://curiosity.example/quiz?error=access_denied&error_description=Denied";
    const h = harness({ url });
    const store = createSessionStore(h.deps);
    store.start();
    await settle();
    expect(store.state()).toEqual({ status: "guest", notice: "Denied" });
  });
});
