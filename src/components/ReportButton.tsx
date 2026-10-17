import { type FormEvent, useState } from "react";

import { reportFailureMessage, reportItem } from "../api";

type State = "idle" | "open" | "sending" | "sent" | "already" | "failed";

/** "Report a problem": two reports from different visitors hide an item until it is checked. */
export function ReportButton({ itemId }: { itemId: number }) {
  const [state, setState] = useState<State>("idle");
  const [reason, setReason] = useState("");
  const [failure, setFailure] = useState("");

  async function send(event: FormEvent) {
    event.preventDefault();
    setState("sending");
    try {
      setState((await reportItem(itemId, reason)) ? "already" : "sent");
    } catch (error) {
      setFailure(reportFailureMessage(error));
      setState("failed");
    }
  }

  if (state === "sent" || state === "already") {
    return (
      <p role="status" className="text-sm text-slate">
        {state === "sent" ? "Thanks, it will be looked at." : "You have already reported this one."}
      </p>
    );
  }

  if (state === "idle") {
    return (
      <button
        type="button"
        onClick={() => setState("open")}
        className="text-sm text-slate underline underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
      >
        Report a problem
      </button>
    );
  }

  return (
    <form onSubmit={send} className="flex w-full flex-col gap-3 sm:flex-row sm:items-center">
      <label htmlFor={`report-${itemId}`} className="sr-only">
        What looks wrong?
      </label>
      <input
        id={`report-${itemId}`}
        type="text"
        maxLength={300}
        placeholder="What looks wrong? (optional)"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        className="min-w-0 flex-1 rounded-md border border-white/10 bg-void px-3 py-2 text-base text-ink placeholder:text-slate/70 focus:border-teal focus:outline-none"
      />
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={state === "sending"}
          className="rounded-md border border-rust/60 px-3 py-2 font-pixel text-[8px] uppercase text-ink hover:border-rust disabled:opacity-50"
        >
          {state === "sending" ? "Sending" : "Send report"}
        </button>
        <button
          type="button"
          onClick={() => setState("idle")}
          className="text-sm text-slate hover:text-ink"
        >
          Cancel
        </button>
      </div>
      {state === "failed" && (
        <p role="alert" className="text-sm text-rust">
          {failure}
        </p>
      )}
    </form>
  );
}
