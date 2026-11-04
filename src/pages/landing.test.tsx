import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Profile } from "../profile";
import { EMPTY_PROFILE } from "../profile";
import type { Quota, BankTopic } from "../types";
import type { TopicsState } from "../useTopics";
import { ExplorePage } from "./ExplorePage";
import { HomePage } from "./HomePage";
import { LearnPage } from "./LearnPage";
import { QuizPage } from "./QuizPage";
import type { PageProps } from "./common";

// The pages are rendered once on the server: no effects run, so the router and the quota hook are
// replaced with fixed answers.
let quota: { kind: "loading" } | { kind: "loaded"; quota: Quota } = { kind: "loading" };
const quotaRequests = vi.fn();

vi.mock("../router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../router")>()),
  useLocation: () => new URL("https://example.test/explore"),
  usePageTitle: () => undefined,
}));
vi.mock("../useQuota", () => ({
  useQuota: () => {
    quotaRequests();
    return [quota, () => undefined];
  },
}));

const OPEN: Quota = { remaining: 5, limit: 5, resets_at: "2026-11-05T00:00:00Z", global_open: true };

function topic(name: string, extra: Partial<BankTopic> = {}): BankTopic {
  return { name, kind: "evergreen", learn: ["easy"], quiz: ["easy"], ...extra };
}

function loaded(count: number): TopicsState {
  return { kind: "loaded", topics: Array.from({ length: count }, (_, i) => topic(`Topic ${i}`)) };
}

function props(topicsState: TopicsState, profile: Profile = EMPTY_PROFILE): PageProps {
  return {
    topicsState,
    retryTopics: () => undefined,
    profile,
    updateProfile: () => [],
    celebrate: () => undefined,
    difficulty: "easy",
    setDifficulty: () => undefined,
  };
}

function text(html: string): string {
  return html.replace(/<[^>]*>/g, "");
}

const SCORING = "EASY 100, MEDIUM 200, HARD 300 points a correct answer.";

beforeEach(() => {
  quota = { kind: "loading" };
  quotaRequests.mockClear();
});

describe("HomePage", () => {
  const render = (topicsState: TopicsState, profile = EMPTY_PROFILE) =>
    renderToStaticMarkup(<HomePage {...props(topicsState, profile)} slideshow={null} />);

  it("orders the cards Quiz, Learn, Web and makes only Quiz the main card", () => {
    const page = render(loaded(3));
    const html = page.slice(page.indexOf('aria-label="Ways in"'), page.indexOf("</nav>"));
    const at = (label: string) => html.indexOf(`>${label}</span>`);
    expect(at("Quiz")).toBeGreaterThan(-1);
    expect(at("Quiz")).toBeLessThan(at("Learn"));
    expect(at("Learn")).toBeLessThan(at("Web"));
    expect(html.match(/bg-teal /g)).toHaveLength(1);
    expect(html.indexOf("bg-teal ")).toBeLessThan(at("Learn"));
  });

  it("shows no status until there is something to say, and makes no quota request", () => {
    const html = text(render(loaded(3)));
    expect(html).not.toMatch(/\d+ of \d+ read/);
    expect(html).not.toContain("Best streak");
    expect(html).not.toContain("Not played yet");
    expect(html).not.toContain("left today");
    expect(quotaRequests).not.toHaveBeenCalled();
  });

  it("shows the Learn and Quiz statuses once their count is above zero", () => {
    const profile = { ...EMPTY_PROFILE, learned: ["Topic 0", "Topic 1"], bestStreak: 4 };
    const html = text(render(loaded(3), profile));
    expect(html).toContain("2 of 3 read");
    expect(html).toContain("Best streak 4");
  });
});

describe("LearnPage", () => {
  const render = (topicsState: TopicsState) =>
    renderToStaticMarkup(<LearnPage {...props(topicsState)} />);

  it("puts the progress line below the grid when nothing is typed", () => {
    const html = render(loaded(3));
    expect(html.match(/0 of 3 read at EASY\./g)).toHaveLength(1);
    expect(html.indexOf("read at EASY")).toBeGreaterThan(html.lastIndexOf("/learn/"));
    expect(html).not.toContain("topics match");
  });

  it("keeps one live region on the page when nothing is typed", () => {
    const html = render(loaded(3));
    expect(html).toContain('<div aria-live="polite"></div>');
  });
});

describe("QuizPage setup", () => {
  const render = (topicsState: TopicsState) =>
    renderToStaticMarkup(<QuizPage {...props(topicsState)} />);

  it("ends with the length note and drops the scoring chip", () => {
    const html = render(loaded(39));
    const note = "EASY: 39 of 60 questions so far. 60 opens as the bank grows.";
    expect(html.match(/questions so far/g)).toHaveLength(1);
    expect(html.indexOf("Start")).toBeLessThan(html.indexOf("How the quiz works"));
    expect(html.indexOf("Where the questions come from")).toBeLessThan(html.indexOf("Rank"));
    expect(html.indexOf(note)).toBeGreaterThan(html.indexOf("Where the questions come from"));
    // The scoring text is now a step in the card, so it appears once.
    expect(html.match(/EASY 100, MEDIUM 200/g)).toHaveLength(1);
    expect(html.indexOf(SCORING)).toBeGreaterThan(html.indexOf("How the quiz works"));
    // The control still points at the note.
    const id = /id="([^"]+)" class="scene-note[^"]*"[^>]*>EASY: 39/.exec(html)?.[1];
    expect(id).toBeDefined();
  });

  it("puts the note right above Start when no length is available", () => {
    const html = render(loaded(5));
    expect(html.match(/questions so far/g)).toHaveLength(1);
    const note = html.indexOf("questions so far");
    expect(note).toBeGreaterThan(-1);
    expect(note).toBeLessThan(html.indexOf("Start"));
    expect(html.indexOf("Start")).toBeLessThan(html.indexOf("How the quiz works"));
    expect(html).toContain("disabled");
  });
});

describe("ExplorePage landing", () => {
  const render = (topicsState: TopicsState = loaded(3)) =>
    renderToStaticMarkup(<ExplorePage {...props(topicsState)} statsOpen={false} />);

  it("has one topic box, in the page, above Go, and a quiet Surprise me under it", () => {
    quota = { kind: "loaded", quota: OPEN };
    const html = render();
    expect(html.match(/role="combobox"/g)).toHaveLength(1);
    const box = html.indexOf('role="combobox"');
    const go = html.indexOf(">Go</button>");
    const surprise = html.indexOf(">Surprise me</button>");
    expect(box).toBeGreaterThan(-1);
    expect(box).toBeLessThan(go);
    expect(go).toBeLessThan(surprise);
    expect(html).toContain("min-h-11");
    expect(html).toContain("underline");
  });

  it("orders the title line, the buttons, Mission Control, the quota and the note", () => {
    quota = { kind: "loaded", quota: OPEN };
    const html = render();
    const order = [
      "Research any astronomy or space topic that is not in the bank yet.",
      ">Go</button>",
      ">Surprise me</button>",
      ">Mission Control</button>",
      "5 of 5 left today",
      "It reads NASA, ESA, arXiv and Wikipedia live",
    ].map((part) => html.indexOf(part));
    expect(order.every((at) => at > -1)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(text(html)).toContain("The explanations open once you have answered the questions.");
  });

  it("says nothing under an empty box, and puts the cap notice under the buttons", () => {
    quota = { kind: "loaded", quota: { ...OPEN, global_open: false } };
    const html = render();
    expect(html).not.toContain("Any astronomy or space topic.");
    expect(html).not.toContain("left today");
    expect(html.indexOf(">Surprise me</button>")).toBeLessThan(html.indexOf("reached its limit"));
    expect(html.indexOf("reached its limit")).toBeLessThan(html.indexOf(">Mission Control</button>"));
  });

  it("keeps the hint for a state that explains Go", () => {
    expect(text(render({ kind: "loading" }))).toContain("Loading topics...");
  });
});
