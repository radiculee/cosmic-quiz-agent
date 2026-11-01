import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import { PATHS } from "../router";
import { ACCOUNT_PATH, CODE_LENGTH, session } from "../session";
import { useSession } from "../useSession";
import { Link } from "./Link";

const TRIGGER =
  "rounded-lg border border-white/10 bg-surface px-3 py-2 font-pixel text-[10px] uppercase " +
  "leading-none text-teal transition-colors hover:border-white/25 focus-visible:outline-2 " +
  "focus-visible:outline-offset-2 focus-visible:outline-teal disabled:cursor-default " +
  "disabled:opacity-40";
const PRIMARY =
  "w-full rounded-lg bg-teal px-4 py-3 font-pixel text-[10px] uppercase text-void " +
  "hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "focus-visible:outline-teal disabled:cursor-default disabled:opacity-40";
const SECONDARY =
  "w-full rounded-lg border border-white/15 px-4 py-3 text-sm font-medium text-ink " +
  "hover:border-teal hover:text-teal focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "focus-visible:outline-teal disabled:cursor-default disabled:opacity-40";
const TEXT_BUTTON =
  "text-sm text-teal underline underline-offset-4 hover:text-ink focus-visible:outline-2 " +
  "focus-visible:outline-offset-2 focus-visible:outline-teal";

type Step = { kind: "email" } | { kind: "code"; email: string };

/**
 * Sign-in for the header (ui places it). Accounts are optional: with them off this renders
 * nothing; signed in, it links to the account page; otherwise it opens a small panel with
 * Google, or an email that carries a link and a code.
 */
export function SignInButton() {
  const state = useSession();
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const panelId = useId();

  // Close on Escape (focus back to the button) or a click outside the panel.
  useEffect(() => {
    if (!open) {
      return undefined;
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    }
    function onPointer(event: PointerEvent) {
      const target = event.target;
      if (
        target instanceof Node &&
        !panel.current?.contains(target) &&
        !trigger.current?.contains(target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  // A notice (a sign-in that failed on the way back) opens the panel to show it.
  const notice = state.status === "guest" ? state.notice : null;
  useEffect(() => {
    if (notice) {
      setOpen(true);
    }
  }, [notice]);

  if (state.status === "off") {
    return null;
  }
  if (state.status === "signed-in") {
    const who = state.account.email ?? "your account";
    return (
      <Link to={ACCOUNT_PATH} className={TRIGGER} aria-label={`Account, signed in as ${who}`}>
        Account
      </Link>
    );
  }
  const loading = state.status === "loading";
  return (
    <div className="relative">
      <button
        ref={trigger}
        type="button"
        className={TRIGGER}
        disabled={loading}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((was) => !was)}
      >
        {loading ? "Signing in" : "Sign in"}
      </button>
      {open && !loading ? (
        <div
          ref={panel}
          id={panelId}
          role="dialog"
          aria-label="Sign in"
          className="absolute right-0 top-full z-30 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-white/10 bg-surface p-4 shadow-xl"
        >
          <SignInPanel notice={notice} />
        </div>
      ) : null}
    </div>
  );
}

function SignInPanel({ notice }: { notice: string | null }) {
  const [step, setStep] = useState<Step>({ kind: "email" });
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(notice);
  const emailId = useId();
  const codeId = useId();
  const google = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    google.current?.focus();
  }, []);

  async function run(action: () => Promise<string | null>): Promise<boolean> {
    setBusy(true);
    setError(null);
    const message = await action();
    setBusy(false);
    setError(message);
    return message === null;
  }

  async function sendCode(event: FormEvent) {
    event.preventDefault();
    if (await run(() => session.sendEmailCode(email))) {
      setCode("");
      setStep({ kind: "code", email: email.trim() });
    }
  }

  async function verify(event: FormEvent, sentTo: string) {
    event.preventDefault();
    await run(() => session.verifyEmailCode(sentTo, code));
  }

  return (
    <div className="space-y-4 text-sm leading-relaxed text-ink">
      <p className="text-slate">
        Optional. Signing in saves your progress to an account, so it is kept and follows you
        to other devices. <Link to={PATHS.privacy} className={TEXT_BUTTON}>Privacy</Link>
      </p>
      <button
        ref={google}
        type="button"
        className={SECONDARY}
        disabled={busy}
        onClick={() => void run(() => session.signInWithGoogle())}
      >
        Continue with Google
      </button>
      <div className="flex items-center gap-3 text-slate" aria-hidden="true">
        <span className="h-px flex-1 bg-white/10" />
        <span className="font-pixel text-[8px] uppercase">or</span>
        <span className="h-px flex-1 bg-white/10" />
      </div>
      {step.kind === "email" ? (
        <form onSubmit={(event) => void sendCode(event)} className="space-y-3" noValidate>
          <label htmlFor={emailId} className="block font-medium">
            Email
            <input
              id={emailId}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-1 w-full rounded-lg border border-white/15 bg-void px-3 py-2 text-base text-ink placeholder:text-slate focus-visible:border-teal focus-visible:outline-none"
            />
          </label>
          <button type="submit" className={PRIMARY} disabled={busy}>
            Email me a sign-in code
          </button>
        </form>
      ) : (
        <form onSubmit={(event) => void verify(event, step.email)} className="space-y-3" noValidate>
          <p>
            We sent a link and a {CODE_LENGTH}-digit code to{" "}
            <span className="font-medium break-all">{step.email}</span>. Open the link in this
            browser, or enter the code here.
          </p>
          <label htmlFor={codeId} className="block font-medium">
            Code
            <input
              id={codeId}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              value={code}
              onChange={(event) => setCode(event.target.value)}
              className="mt-1 w-full rounded-lg border border-white/15 bg-void px-3 py-2 text-base text-ink placeholder:text-slate focus-visible:border-teal focus-visible:outline-none tracking-[0.3em]"
            />
          </label>
          <button type="submit" className={PRIMARY} disabled={busy}>
            Sign in
          </button>
          <button
            type="button"
            className={TEXT_BUTTON}
            onClick={() => {
              setError(null);
              setStep({ kind: "email" });
            }}
          >
            Use another email
          </button>
        </form>
      )}
      {error ? (
        <p role="alert" className="text-gold">
          {error}
        </p>
      ) : null}
    </div>
  );
}
