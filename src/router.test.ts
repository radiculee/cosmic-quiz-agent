import { describe, expect, it } from "vitest";

import {
  createHistoryRouter,
  explorePath,
  isPlainLeftClick,
  learnTopicPath,
  matchRoute,
  type RouterHost,
  topicForSlug,
  topicSlug,
} from "./router";
import type { BankTopic } from "./types";

describe("matchRoute", () => {
  it("knows every page", () => {
    expect(matchRoute("/")).toEqual({ page: "home" });
    expect(matchRoute("/learn")).toEqual({ page: "learn" });
    expect(matchRoute("/quiz")).toEqual({ page: "quiz" });
    expect(matchRoute("/explore")).toEqual({ page: "explore" });
    expect(matchRoute("/explore/stats")).toEqual({ page: "explore-stats" });
    expect(matchRoute("/trophies")).toEqual({ page: "trophies" });
    expect(matchRoute("/learn/black-holes")).toEqual({ page: "learn-topic", slug: "black-holes" });
  });

  it("ignores trailing slashes and case in a slug, and decodes it", () => {
    expect(matchRoute("/quiz/")).toEqual({ page: "quiz" });
    expect(matchRoute("/learn/Black-Holes/")).toEqual({ page: "learn-topic", slug: "black-holes" });
    expect(matchRoute("/learn/caf%C3%A9")).toEqual({ page: "learn-topic", slug: `caf${String.fromCharCode(0xe9)}` });
  });

  it("sends anything else to not-found", () => {
    expect(matchRoute("/nope")).toEqual({ page: "not-found" });
    expect(matchRoute("/learn/a/b")).toEqual({ page: "not-found" });
    expect(matchRoute("/quizzes")).toEqual({ page: "not-found" });
    expect(matchRoute("/explore/other")).toEqual({ page: "not-found" });
    expect(matchRoute("/learn/%E0%A4%A")).toEqual({ page: "learn-topic", slug: "%e0%a4%a" });
  });
});

describe("topic slugs", () => {
  const names = [
    "Black holes",
    "Europa's hidden ocean",
    "Sagittarius A*",
    "Light-years and cosmic distances",
    "The life cycle of a Sun-like star",
    "White dwarf planets in second-generation systems",
  ];

  it("are lower case words joined by hyphens, without apostrophes or accents", () => {
    expect(topicSlug("Black holes")).toBe("black-holes");
    expect(topicSlug("Europa's hidden ocean")).toBe("europas-hidden-ocean");
    expect(topicSlug(`Titan${String.fromCharCode(0x2019)}s lakes`)).toBe("titans-lakes");
    expect(topicSlug("Sagittarius A*")).toBe("sagittarius-a");
    expect(topicSlug("  The  Big Bang! ")).toBe("the-big-bang");
    expect(topicSlug(`Caf${String.fromCharCode(0xe9)} au lait`)).toBe("cafe-au-lait");
  });

  it("lead back to their topic", () => {
    const topics: BankTopic[] = names.map((name) => ({
      name,
      kind: "evergreen",
      learn: ["easy"],
      quiz: [],
    }));
    for (const name of names) {
      const path = learnTopicPath(name);
      const route = matchRoute(path);
      expect(route.page).toBe("learn-topic");
      expect(route.page === "learn-topic" && topicForSlug(topics, route.slug)?.name).toBe(name);
    }
    expect(topicForSlug(topics, "no-such-topic")).toBeUndefined();
  });

  it("fill the web page's form through the address", () => {
    expect(explorePath("Pulsars & magnetars", "hard")).toBe(
      "/explore?topic=Pulsars+%26+magnetars&difficulty=hard",
    );
  });
});

/** A stand-in for `window`: a history stack the router pushes to, and Back and Forward. */
function fakeHost(start = "/") {
  const target = new EventTarget();
  const entries = [start];
  let index = 0;
  const scrolls: number[] = [];
  const assigned: string[] = [];
  const location = {
    get href() {
      return `https://cosmic.example${entries[index] ?? "/"}`;
    },
    get pathname() {
      return new URL(this.href).pathname;
    },
    get search() {
      return new URL(this.href).search;
    },
    get hash() {
      return new URL(this.href).hash;
    },
    origin: "https://cosmic.example",
    assign: (url: string | URL) => void assigned.push(String(url)),
  };
  const host: RouterHost = {
    location,
    history: {
      pushState: (_data: unknown, _unused: string, url?: string | URL | null) => {
        entries.splice(index + 1, entries.length, String(url));
        index += 1;
      },
      replaceState: (_data: unknown, _unused: string, url?: string | URL | null) => {
        entries[index] = String(url);
      },
    },
    addEventListener: (type, listener) => target.addEventListener(type, listener),
    removeEventListener: (type, listener) => target.removeEventListener(type, listener),
    dispatchEvent: (event) => target.dispatchEvent(event),
    scrollTo: (_x, y) => void scrolls.push(y),
  };
  const back = () => {
    index -= 1;
    target.dispatchEvent(new Event("popstate"));
  };
  return { host, entries, scrolls, assigned, back };
}

describe("createHistoryRouter", () => {
  it("pushes a new page, scrolls to the top and tells subscribers", () => {
    const { host, entries, scrolls } = fakeHost();
    const router = createHistoryRouter(host);
    const seen: string[] = [];
    const unsubscribe = router.subscribe(() => seen.push(router.current()));

    router.navigate("/learn");
    router.navigate("/explore?topic=Pulsars");

    expect(entries).toEqual(["/", "/learn", "/explore?topic=Pulsars"]);
    expect(seen).toEqual(["/learn", "/explore?topic=Pulsars"]);
    expect(scrolls).toEqual([0, 0]);
    unsubscribe();
    router.navigate("/quiz");
    expect(seen).toHaveLength(2);
  });

  it("follows Back through popstate", () => {
    const { host, back } = fakeHost();
    const router = createHistoryRouter(host);
    const seen: string[] = [];
    router.subscribe(() => seen.push(router.current()));

    router.navigate("/quiz");
    back();

    expect(seen).toEqual(["/quiz", "/"]);
  });

  it("replaces without a new entry, skips the current page, and leaves other sites", () => {
    const { host, entries, scrolls, assigned } = fakeHost("/learn");
    const router = createHistoryRouter(host);

    router.navigate("/learn");
    router.navigate("/learn/quasars", { replace: true });
    router.navigate("https://github.com/radiculee");

    expect(entries).toEqual(["/learn/quasars"]);
    expect(scrolls).toEqual([]);
    expect(assigned).toEqual(["https://github.com/radiculee"]);
  });
});

describe("isPlainLeftClick", () => {
  const plain = {
    button: 0,
    metaKey: false,
    ctrlKey: false,
    shiftKey: false,
    altKey: false,
    defaultPrevented: false,
  };

  it("leaves new-tab clicks to the browser", () => {
    expect(isPlainLeftClick(plain)).toBe(true);
    expect(isPlainLeftClick({ ...plain, ctrlKey: true })).toBe(false);
    expect(isPlainLeftClick({ ...plain, metaKey: true })).toBe(false);
    expect(isPlainLeftClick({ ...plain, button: 1 })).toBe(false);
    expect(isPlainLeftClick({ ...plain, defaultPrevented: true })).toBe(false);
  });
});
