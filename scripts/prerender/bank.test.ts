import { describe, expect, it } from "vitest";

import { fetchTopics, siteOf } from "./bank.ts";

const LEVELS = ["easy", "medium", "hard"];

function learn(id: number, name: string, difficulty: string, extra: object = {}) {
  return {
    id,
    difficulty,
    explanation: `${name} at ${difficulty}`,
    topics: { name },
    sources: [
      { ordinal: 2, url: "https://www.esa.int/b", quote: "second" },
      { ordinal: 1, url: "https://en.wikipedia.org/a", quote: "first" },
    ],
    ...extra,
  };
}

function quiz(name: string, difficulty: string) {
  return { difficulty, topics: { name } };
}

/** A stand-in for the bank: answers by mode, in pages of the size the reader asks for. */
function bank(learnRows: object[], quizRows: object[]): { fetcher: typeof fetch; calls: string[] } {
  const calls: string[] = [];
  const fetcher = (async (input: string | URL | Request, init?: RequestInit) => {
    const address = String(input);
    calls.push(address);
    expect((init?.headers as Record<string, string>)["apikey"]).toBe("publishable");
    const rows = address.includes("mode=eq.learn") ? learnRows : quizRows;
    const offset = Number(new URL(address).searchParams.get("offset"));
    const limit = Number(new URL(address).searchParams.get("limit"));
    return new Response(JSON.stringify(rows.slice(offset, offset + limit)), { status: 200 });
  }) as typeof fetch;
  return { fetcher, calls };
}

const ACCESS = { url: "https://example.supabase.co/", key: "publishable" };

describe("fetchTopics", () => {
  it("returns topics with every level in both modes, alphabetically, with the easiest explanation", async () => {
    const full = (name: string, firstId: number) => [
      learn(firstId + 2, name, "hard"),
      learn(firstId, name, "easy"),
      learn(firstId + 1, name, "medium"),
    ];
    const { fetcher } = bank(
      [...full("Mars", 10), ...full("Black holes", 20), learn(30, "Pulsars", "easy")],
      [
        ...LEVELS.map((level) => quiz("Mars", level)),
        ...LEVELS.map((level) => quiz("Black holes", level)),
        quiz("Pulsars", "easy"),
      ],
    );

    const topics = await fetchTopics(ACCESS, fetcher);

    expect(topics.map((topic) => [topic.name, topic.slug, topic.explanation])).toEqual([
      ["Black holes", "black-holes", "Black holes at easy"],
      ["Mars", "mars", "Mars at easy"],
    ]);
  });

  it("leaves out a topic that lacks a quiz level, as Learn does", async () => {
    const rows = LEVELS.map((level, index) => learn(index, "Comets", level));
    const { fetcher } = bank(rows, [quiz("Comets", "easy"), quiz("Comets", "medium")]);

    expect(await fetchTopics(ACCESS, fetcher)).toEqual([]);
  });

  it("orders sources as the site does and names each by its host", async () => {
    const rows = LEVELS.map((level, index) => learn(index, "Comets", level));
    const { fetcher } = bank(rows, LEVELS.map((level) => quiz("Comets", level)));

    const [topic] = await fetchTopics(ACCESS, fetcher);

    expect(topic?.sources.map((source) => [source.site, source.quote])).toEqual([
      ["en.wikipedia.org", "first"],
      ["esa.int", "second"],
    ]);
  });

  it("asks only for what players may see, with the publishable key", async () => {
    const rows = LEVELS.map((level, index) => learn(index, "Comets", level));
    const { fetcher, calls } = bank(rows, LEVELS.map((level) => quiz("Comets", level)));

    await fetchTopics(ACCESS, fetcher);

    expect(calls).toHaveLength(2);
    for (const call of calls) {
      expect(call).toContain("https://example.supabase.co/rest/v1/items?");
      expect(call).toContain("status=eq.published");
      expect(call).toContain("report_count=lt.2");
    }
  });

  it("keeps the first of two topics that share an address", async () => {
    const both = ["Dark matter", "Dark-matter"].flatMap((name, index) =>
      LEVELS.map((level, at) => learn(index * 10 + at, name, level)),
    );
    const quizzes = ["Dark matter", "Dark-matter"].flatMap((name) => LEVELS.map((level) => quiz(name, level)));
    const { fetcher } = bank(both, quizzes);

    const topics = await fetchTopics(ACCESS, fetcher);

    expect(topics.map((topic) => topic.slug)).toEqual(["dark-matter"]);
  });

  it("reads every page when the bank has more rows than one page", async () => {
    const many = Array.from({ length: 2300 }, (_, index) => quiz("Comets", LEVELS[index % 3]!));
    const rows = LEVELS.map((level, index) => learn(index, "Comets", level));
    const { fetcher, calls } = bank(rows, many);

    expect(await fetchTopics(ACCESS, fetcher)).toHaveLength(1);
    expect(calls.filter((call) => call.includes("mode=eq.quiz"))).toHaveLength(3);
  });

  it("fails the build loudly when the bank refuses", async () => {
    const refuse = (async () => new Response("no", { status: 401 })) as typeof fetch;

    await expect(fetchTopics(ACCESS, refuse)).rejects.toThrow(/401/);
  });
});

describe("siteOf", () => {
  it("drops www and keeps the host", () => {
    expect(siteOf("https://www.nasa.gov/x")).toBe("nasa.gov");
    expect(siteOf("not a url")).toBe("not a url");
  });
});
