/**
 * Reads the published bank for the build, with the publishable key and the same rules the site
 * applies (published items with fewer than 2 reports, which row-level security enforces too).
 * Only topics that Learn lists are returned: those with every level in both modes
 * (agent/bank.py, BankTopic.complete). Pure apart from `fetch`, which is passed in.
 */
import { topicSlug } from "../../src/slug.ts";

export interface PageSource {
  url: string;
  site: string;
  quote: string;
}

/** A Learn topic, with the easiest explanation the bank has for it. */
export interface PageTopic {
  name: string;
  slug: string;
  explanation: string;
  sources: PageSource[];
}

export interface BankAccess {
  url: string;
  key: string;
}

const LEVELS = ["easy", "medium", "hard"];
const PAGE_SIZE = 1000;
const VISIBLE = "status=eq.published&report_count=lt.2";

type Json = Record<string, unknown>;

function isRecord(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(row: Json, field: string): string {
  const value = row[field];
  if (typeof value !== "string") {
    throw new Error(`the bank sent a row without a text "${field}"`);
  }
  return value;
}

function topicName(row: Json): string {
  const topic = row["topics"];
  if (!isRecord(topic)) {
    throw new Error('the bank sent a row without its "topics"');
  }
  return text(topic, "name");
}

/** A page's host without "www.", as the site labels a source (agent/store.py, domain). */
export function siteOf(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return url;
  }
}

async function readAll(access: BankAccess, query: string, fetcher: typeof fetch): Promise<Json[]> {
  const rows: Json[] = [];
  for (;;) {
    const address = `${access.url.replace(/\/+$/, "")}/rest/v1/items?${query}&limit=${PAGE_SIZE}&offset=${rows.length}`;
    const reply = await fetcher(address, { headers: { apikey: access.key } });
    if (!reply.ok) {
      throw new Error(`the bank answered ${reply.status} to ${query.slice(0, 40)}`);
    }
    const page: unknown = await reply.json();
    if (!Array.isArray(page)) {
      throw new Error("the bank did not send a list of rows");
    }
    rows.push(...page.filter(isRecord));
    if (page.length < PAGE_SIZE) {
      return rows;
    }
  }
}

function sourcesOf(row: Json): PageSource[] {
  const list = row["sources"];
  if (!Array.isArray(list)) {
    return [];
  }
  return list
    .filter(isRecord)
    .sort((a, b) => Number(a["ordinal"]) - Number(b["ordinal"]))
    .map((source) => {
      const url = text(source, "url");
      return { url, site: siteOf(url), quote: text(source, "quote") };
    });
}

/** Every complete Learn topic, alphabetical, with its easiest published explanation. */
export async function fetchTopics(
  access: BankAccess,
  fetcher: typeof fetch = fetch,
): Promise<PageTopic[]> {
  const learn = await readAll(
    access,
    `select=id,difficulty,explanation,topics!inner(name),sources(ordinal,url,quote)` +
      `&mode=eq.learn&${VISIBLE}&order=id.asc`,
    fetcher,
  );
  const quiz = await readAll(
    access,
    `select=difficulty,topics!inner(name)&mode=eq.quiz&${VISIBLE}&order=id.asc`,
    fetcher,
  );

  const levels = new Map<string, Set<string>>();
  const add = (key: string, row: Json) => {
    const found = levels.get(key) ?? new Set<string>();
    found.add(text(row, "difficulty"));
    levels.set(key, found);
  };
  for (const row of learn) {
    add(`learn|${topicName(row)}`, row);
  }
  for (const row of quiz) {
    add(`quiz|${topicName(row)}`, row);
  }
  const complete = (name: string): boolean =>
    ["learn", "quiz"].every((mode) => LEVELS.every((level) => levels.get(`${mode}|${name}`)?.has(level)));

  const best = new Map<string, { rank: number; row: Json }>();
  for (const row of learn) {
    const name = topicName(row);
    const rank = LEVELS.indexOf(text(row, "difficulty"));
    const held = best.get(name);
    if (rank >= 0 && complete(name) && (!held || rank < held.rank)) {
      best.set(name, { rank, row });
    }
  }

  const topics: PageTopic[] = [];
  const taken = new Set<string>();
  for (const [name, { row }] of [...best].sort((a, b) => a[0].toLowerCase().localeCompare(b[0].toLowerCase()))) {
    const slug = topicSlug(name);
    if (!slug || taken.has(slug)) {
      continue; // two names with one address: the first keeps it, as topicForSlug does
    }
    taken.add(slug);
    topics.push({ name, slug, explanation: text(row, "explanation"), sources: sourcesOf(row) });
  }
  return topics;
}
