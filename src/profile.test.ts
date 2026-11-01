import { describe, expect, it } from "vitest";

import { answerInRun, planRun, scoreAnswer } from "./game";
import {
  ACCOUNT_KEY,
  type AccountRemote,
  afterAnswer,
  afterLearn,
  afterLiveRun,
  afterRun,
  combineBaselines,
  createProfileStore,
  EMPTY_PROFILE,
  EMPTY_TOTALS,
  foldGuest,
  GUEST_KEY,
  type InsertResult,
  inOrder,
  loadGuest,
  loadProfile,
  type Profile,
  type ProfileStore,
  replay,
  RETRY_MS,
  saveGuest,
  saveProfile,
  type Stamp,
  STORAGE_KEY,
  type Table,
  type Totals,
  totalsOf,
  V1_STORAGE_KEY,
} from "./profile";
import type { Award } from "./trophies";
import type { BankTopic } from "./types";

const TOPICS: BankTopic[] = Array.from({ length: 12 }, (_, i) => ({
  name: `Topic ${i + 1}`,
  kind: "evergreen",
  learn: ["easy"],
  quiz: ["easy"],
}));

function memoryStorage(entries: Record<string, string> = {}) {
  const data = new Map(Object.entries(entries));
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
  };
}

/** Stamp number `n`: a fixed id, and a time `n` seconds after a fixed moment. */
function stamp(n: number): Stamp {
  return {
    id: `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`,
    at: new Date(Date.UTC(2026, 10, 1, 12, 0, n)).toISOString(),
  };
}

/** Ids for new guests, in order, distinct from the stamps above. */
function idMaker() {
  let next = 0;
  return () => {
    next += 1;
    return `aaaaaaaa-0000-4000-8000-${String(next).padStart(12, "0")}`;
  };
}

const easy = (correct: boolean, streak: number) => scoreAnswer("easy", correct, streak, 30);

describe("updates", () => {
  it("adds points, remembers what was seen and awards each tier once", () => {
    const score = scoreAnswer("easy", true, 5, 30);
    const [profile, earned] = afterAnswer(EMPTY_PROFILE, "easy", 7, "Quasars", score, true, 5);

    expect(profile.points).toBe(200);
    expect(profile.seenItems).toEqual([7]);
    expect(profile.played.easy).toEqual(["Quasars"]);
    expect(profile.trophies).toEqual({ "first-light": "bronze", "hot-streak": "bronze" });
    expect(earned).toEqual([
      { kind: "trophy", id: "first-light", tier: "bronze" },
      { kind: "trophy", id: "hot-streak", tier: "bronze" },
    ]);
    expect(afterAnswer(profile, "easy", 8, "Auroras", score, true, 6)[1]).toEqual([]);
  });

  it("pops a rank-up with the answer that crossed it", () => {
    const start: Profile = { ...EMPTY_PROFILE, points: 950, correct: 3, answered: 3 };
    const [, earned] = afterAnswer(start, "easy", 1, "t", scoreAnswer("easy", true, 1, 30), true, 1);

    expect(earned).toContainEqual({ kind: "rank", name: "Cadet", points: 1_000 });
  });

  it("counts learned topics towards Explorer", () => {
    let profile = EMPTY_PROFILE;
    let earned: Award[] = [];
    for (let i = 0; i < 10; i += 1) {
      [profile, earned] = afterLearn(profile, i, `Topic ${i}`);
    }
    expect(earned).toEqual([{ kind: "trophy", id: "explorer", tier: "bronze" }]);
    expect(afterLearn(profile, 1, "Topic 1")[0].learned).toHaveLength(10);
  });

  it("counts finished runs and gives their trophies; an ended run changes nothing", () => {
    let run = planRun(TOPICS, "easy", 10, []);
    for (let i = 0; i < 10; i += 1) {
      run = answerInRun(run, i, "t", true, 30).run;
    }
    const [finished, earned] = afterRun(EMPTY_PROFILE, run, 300);

    expect(finished.finishedRuns).toBe(1);
    expect(earned).toEqual([
      { kind: "trophy", id: "finisher", tier: "bronze" },
      { kind: "trophy", id: "perfect-run", tier: "bronze" },
    ]);

    const ended = { ...run, results: run.results.slice(0, 4) };
    expect(afterRun(EMPTY_PROFILE, ended, 40)).toEqual([EMPTY_PROFILE, []]);
  });

  it("counts live runs towards Web researcher", () => {
    const [once, first] = afterLiveRun(EMPTY_PROFILE);
    const [, again] = afterLiveRun(once);

    expect(once.liveRuns).toBe(1);
    expect(first).toEqual([{ kind: "trophy", id: "web-researcher", tier: "bronze" }]);
    expect(again).toEqual([]);
  });
});

describe("storage", () => {
  it("saves and loads version 2", () => {
    const storage = memoryStorage();
    const [profile] = afterLiveRun(
      afterAnswer(EMPTY_PROFILE, "hard", 3, "Quasars", scoreAnswer("hard", true, 1, 5), true, 1)[0],
    );
    saveProfile(storage, profile);

    expect(storage.data.has(STORAGE_KEY)).toBe(true);
    // Version 2 kept totals only; its history starts empty.
    expect(loadProfile(storage)).toEqual({ ...profile, log: [] });
  });

  it("carries a version 1 profile over, its badges becoming bronze trophies", () => {
    const v1 = {
      points: 4_250,
      answered: 80,
      correct: 61,
      bestStreak: 7,
      badges: ["first-light", "hot-streak", "perfect-run", "made-up"],
      seenItems: [3, 4],
      played: { easy: ["Quasars"], medium: [], hard: [] },
      learned: ["Auroras"],
    };
    const storage = memoryStorage({ [V1_STORAGE_KEY]: JSON.stringify(v1) });

    const loaded = loadProfile(storage);

    expect(loaded).toEqual({
      points: 4_250,
      answered: 80,
      correct: 61,
      bestStreak: 7,
      trophies: { "first-light": "bronze", "hot-streak": "bronze", "perfect-run": "bronze" },
      finishedRuns: 0,
      liveRuns: 0,
      seenItems: [3, 4],
      played: { easy: ["Quasars"], medium: [], hard: [] },
      learned: ["Auroras"],
      log: [],
    });
    // A higher tier comes with the next matching event: 61 correct answers is past 50.
    const [, earned] = afterAnswer(loaded, "easy", 9, "t", scoreAnswer("easy", true, 1, 30), true, 1);
    expect(earned).toEqual([{ kind: "trophy", id: "first-light", tier: "silver" }]);
  });

  it("prefers version 2, and falls back to version 1 if version 2 is corrupt", () => {
    const v1 = JSON.stringify({ points: 10, badges: ["explorer"] });
    const v2 = JSON.stringify({ points: 20, trophies: { explorer: "gold" } });

    expect(loadProfile(memoryStorage({ [V1_STORAGE_KEY]: v1, [STORAGE_KEY]: v2 }))).toMatchObject({
      points: 20,
      trophies: { explorer: "gold" },
    });
    expect(loadProfile(memoryStorage({ [V1_STORAGE_KEY]: v1, [STORAGE_KEY]: "{broken" }))).toMatchObject({
      points: 10,
      trophies: { explorer: "bronze" },
    });
  });

  it("keeps valid fields and drops the rest", () => {
    const saved = JSON.stringify({
      points: 50,
      liveRuns: -1,
      trophies: { explorer: "platinum", finisher: "silver", nonsense: "gold" },
      seenItems: [1, -2, "x"],
    });

    expect(loadProfile(memoryStorage({ [STORAGE_KEY]: saved }))).toMatchObject({
      points: 50,
      liveRuns: 0,
      trophies: { finisher: "silver" },
      seenItems: [1],
    });
    expect(loadProfile(memoryStorage({ [STORAGE_KEY]: "{broken" }))).toEqual(EMPTY_PROFILE);
  });

  it("works with storage blocked", () => {
    const blocked = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(loadProfile(blocked)).toEqual(EMPTY_PROFILE);
    expect(loadProfile(undefined)).toEqual(EMPTY_PROFILE);
    expect(() => saveProfile(blocked, EMPTY_PROFILE)).not.toThrow();
  });
});

// --- Accounts (version 3) ---------------------------------------------------------------------

/** A finished 10-question EASY run, every answer right, played with stamps from `from`. */
function playRun(start: Profile, from: number): Profile {
  let profile = start;
  let run = planRun(TOPICS, "easy", 10, [], () => 0.5);
  for (const [index, topic] of run.topics.entries()) {
    const answered = answerInRun(run, 100 + index, topic, true, 5);
    run = answered.run;
    [profile] = afterAnswer(
      profile,
      "easy",
      100 + index,
      topic,
      answered.score,
      true,
      run.streak,
      { choice: 1, seconds: 5 },
      stamp(from + index),
    );
  }
  return afterRun(profile, run, 50, stamp(from + 10))[0];
}

describe("history", () => {
  it("records each update as an event with its own id", () => {
    const [answered] = afterAnswer(
      EMPTY_PROFILE,
      "hard",
      3,
      "Quasars",
      scoreAnswer("hard", true, 1, 5),
      true,
      1,
      { choice: 2, seconds: 5 },
      stamp(1),
    );
    const [read] = afterLearn(answered, 4, "Auroras", stamp(2));
    const [searched] = afterLiveRun(read, stamp(3));

    expect(searched.log).toEqual([
      {
        ...stamp(1),
        kind: "answer",
        itemId: 3,
        topic: "Quasars",
        difficulty: "hard",
        correct: true,
        choice: 2,
        seconds: 5,
        streak: 1,
        points: 375,
      },
      { ...stamp(2), kind: "read", itemId: 4, topic: "Auroras" },
      { ...stamp(3), kind: "search" },
    ]);
    expect(playRun(EMPTY_PROFILE, 10).log.at(-1)).toEqual({
      ...stamp(20),
      kind: "run",
      difficulty: "easy",
      length: 10,
      correct: 10,
      seconds: 50,
    });
  });

  it("leaves the choice and seconds empty when the page does not pass them", () => {
    const [profile] = afterAnswer(EMPTY_PROFILE, "easy", 1, "t", easy(false, 0), false, 0);
    expect(profile.log[0]).toMatchObject({ choice: null, seconds: null, points: 0 });
  });

  it("gives each new event a later time than the one before", () => {
    const [first] = afterLiveRun(EMPTY_PROFILE);
    const [second] = afterLiveRun(first);
    const [a, b] = second.log;
    expect(a && b && a.at < b.at).toBe(true);
    expect(a?.id).not.toBe(b?.id);
  });
});

describe("replay", () => {
  it("gives the same profile as playing: points, streaks, trophies and lists", () => {
    let played = playRun(EMPTY_PROFILE, 1);
    [played] = afterLearn(played, 7, "Auroras", stamp(30));
    [played] = afterLiveRun(played, stamp(31));
    [played] = afterAnswer(played, "easy", 8, "Comets", easy(false, 0), false, 0, {}, stamp(32));

    expect(replay([], played.log)).toEqual(totalsOf(played));
    expect(played.trophies).toMatchObject({ finisher: "bronze", "perfect-run": "bronze" });
  });

  it("changes nothing when an event comes twice (merging twice)", () => {
    const played = playRun(EMPTY_PROFILE, 1);
    expect(replay([], [...played.log, ...played.log])).toEqual(replay([], played.log));
  });

  it("follows the order things happened, not the order they arrive", () => {
    const played = playRun(EMPTY_PROFILE, 1);
    const shuffled = [...played.log].reverse();
    expect(replay([], shuffled)).toEqual(replay([], played.log));
    expect(inOrder(shuffled).map((event) => event.id)).toEqual(played.log.map((e) => e.id));
  });

  it("starts from the baselines and recalculates the points from the history", () => {
    const baseline: Totals = { ...EMPTY_TOTALS, points: 500, answered: 4, correct: 4 };
    const [profile] = afterAnswer(EMPTY_PROFILE, "easy", 1, "t", easy(true, 1), true, 1, {}, stamp(1));

    const totals = replay([baseline], profile.log);

    expect(totals.points).toBe(500 + 100);
    expect(totals.answered).toBe(5);
    expect(totals.correct).toBe(5);
    // First light's bronze comes from the history; the baseline had no trophy.
    expect(totals.trophies["first-light"]).toBe("bronze");
  });

  it("joins baselines: counts add up, the best streak and tiers are the highest", () => {
    const a: Totals = {
      ...EMPTY_TOTALS,
      points: 100,
      bestStreak: 3,
      trophies: { explorer: "silver" },
      learned: ["Mars", "Venus"],
      seenItems: [1, 2],
      played: { easy: ["Mars"], medium: [], hard: [] },
    };
    const b: Totals = {
      ...EMPTY_TOTALS,
      points: 50,
      bestStreak: 7,
      trophies: { explorer: "bronze", finisher: "gold" },
      learned: ["Venus", "Pluto"],
      seenItems: [2, 3],
      played: { easy: ["Pluto"], medium: [], hard: [] },
    };

    expect(combineBaselines([a, b])).toEqual({
      ...EMPTY_TOTALS,
      points: 150,
      bestStreak: 7,
      trophies: { explorer: "silver", finisher: "gold" },
      learned: ["Mars", "Venus", "Pluto"],
      seenItems: [1, 2, 3],
      played: { easy: ["Mars", "Pluto"], medium: [], hard: [] },
    });
  });
});

describe("the guest", () => {
  it("carries a version 2 profile over as a baseline with a new guest id", () => {
    const v2 = { ...EMPTY_TOTALS, points: 900, answered: 9, correct: 8, learned: ["Mars"] };
    const storage = memoryStorage({ [STORAGE_KEY]: JSON.stringify(v2) });

    const guest = loadGuest(storage, idMaker());

    expect(guest.guestId).toBe("aaaaaaaa-0000-4000-8000-000000000001");
    expect(guest.baseline).toEqual(v2);
    expect(guest.profile).toEqual({ ...v2, log: [] });
  });

  it("saves and loads version 3 with its history, dropping events that do not parse", () => {
    const storage = memoryStorage();
    const [profile] = afterLearn(EMPTY_PROFILE, 4, "Auroras", stamp(1));
    saveGuest(storage, { guestId: stamp(9).id, baseline: null, profile });
    expect(loadGuest(storage, idMaker())).toEqual({ guestId: stamp(9).id, baseline: null, profile });

    const saved = JSON.parse(storage.getItem(GUEST_KEY) ?? "{}") as { profile: { log: unknown[] } };
    saved.profile.log.push({ id: "x", at: "never", kind: "answer" });
    storage.setItem(GUEST_KEY, JSON.stringify(saved));
    expect(loadGuest(storage, idMaker()).profile.log).toHaveLength(1);
  });

  it("folds its oldest events into the baseline past the limit, keeping the totals", () => {
    const played = playRun(EMPTY_PROFILE, 1);
    const guest = { guestId: stamp(99).id, baseline: null, profile: played };

    const folded = foldGuest(guest, 4);

    expect(folded.profile.log).toEqual(played.log.slice(-4));
    expect(replay(folded.baseline ? [folded.baseline] : [], folded.profile.log)).toEqual(
      totalsOf(played),
    );
  });
});

/** Supabase's tables for one signed-in player, as row-level security shows them. */
class FakeServer implements AccountRemote {
  tables: Record<Table, Map<string, Record<string, unknown>>> = {
    player_answers: new Map(),
    player_reads: new Map(),
    player_runs: new Map(),
    player_searches: new Map(),
    player_baselines: new Map(),
  };
  online = true;
  /** Migration 011's row caps, made small: more rows than this and the insert is refused. */
  caps: Partial<Record<Table, number>> = {};
  inserts = 0;

  async insert(table: Table, rows: readonly Record<string, unknown>[]): Promise<InsertResult> {
    this.inserts += 1;
    if (!this.online) {
      return "failed";
    }
    const stored = this.tables[table];
    const cap = this.caps[table];
    // The cap's trigger runs before the conflict check, so a repeated row counts too, and one
    // row over the cap refuses the whole statement.
    if (cap !== undefined && stored.size + rows.length > cap) {
      return "capped";
    }
    for (const row of rows) {
      const key = String(table === "player_baselines" ? row.guest_id : row.id);
      if (!stored.has(key)) {
        stored.set(key, { ...row });
      }
    }
    return "stored";
  }

  async readAll(table: Table): Promise<Record<string, unknown>[] | null> {
    return this.online ? [...this.tables[table].values()] : null;
  }

  count(table: Table): number {
    return this.tables[table].size;
  }
}

interface World {
  server: FakeServer;
  storage: ReturnType<typeof memoryStorage>;
  scheduled: (() => void)[];
  warnings: string[];
  open: (options?: { guestLogLimit?: number; remote?: boolean }) => ProfileStore;
}

/** One browser (its storage) and the account's server; `open` loads the page. */
function world(entries: Record<string, string> = {}): World {
  const server = new FakeServer();
  const storage = memoryStorage(entries);
  const scheduled: (() => void)[] = [];
  const warnings: string[] = [];
  const newId = idMaker();
  return {
    server,
    storage,
    scheduled,
    warnings,
    open: (options = {}) =>
      createProfileStore({
        storage,
        remote: options.remote === false ? null : server,
        newId,
        schedule: (task, ms) => {
          expect(ms).toBe(RETRY_MS);
          scheduled.push(task);
        },
        warn: (message) => warnings.push(message),
        ...(options.guestLogLimit === undefined ? {} : { guestLogLimit: options.guestLogLimit }),
      }),
  };
}

const USER = "11111111-1111-4111-8111-111111111111";

function guestIdIn(storage: ReturnType<typeof memoryStorage>): string {
  const saved = JSON.parse(storage.getItem(GUEST_KEY) ?? "{}") as { guestId?: string };
  return saved.guestId ?? "";
}

describe("accounts", () => {
  it("with accounts off, plays as a guest and sends nothing", async () => {
    const w = world();
    const store = w.open({ remote: false });
    store.update((p) => afterLearn(p, 4, "Auroras", stamp(1)));
    await store.signIn(USER);
    await store.flush();

    expect(store.profile().learned).toEqual(["Auroras"]);
    expect(w.server.inserts).toBe(0);
    expect(w.storage.data.has(GUEST_KEY)).toBe(true);
  });

  it("adds the guest's progress on sign-in: reads joined, answers added, points recalculated", async () => {
    // Another device already saved a read and a right answer to the account.
    const w = world({
      [STORAGE_KEY]: JSON.stringify({ ...EMPTY_TOTALS, points: 1_000, answered: 10, correct: 10 }),
    });
    w.server.tables.player_reads.set(stamp(50).id, {
      id: stamp(50).id,
      at: stamp(50).at,
      item_id: 9,
      topic: "Mars",
    });
    w.server.tables.player_answers.set(stamp(51).id, {
      id: stamp(51).id,
      at: stamp(51).at,
      item_id: 9,
      topic: "Mars",
      difficulty: "hard",
      choice: null,
      correct: true,
      seconds: null,
      streak: 1,
      points: 300,
    });
    const store = w.open();
    store.update((p) => afterLearn(p, 4, "Auroras", stamp(1)));
    store.update((p) => afterAnswer(p, "easy", 5, "Auroras", easy(true, 1), true, 1, {}, stamp(2)));

    await store.signIn(USER);

    const profile = store.profile();
    expect(profile.learned).toEqual(["Mars", "Auroras"]);
    expect(profile.points).toBe(1_000 + 100 + 300);
    expect(profile.answered).toBe(12);
    expect(w.server.count("player_baselines")).toBe(1);
    expect(w.server.count("player_answers")).toBe(2);
    expect(w.server.count("player_reads")).toBe(2);
    // The guest moved into the account: this browser now has a fresh guest with a new id.
    expect(guestIdIn(w.storage)).toBe("aaaaaaaa-0000-4000-8000-000000000002");
    expect(loadGuest(w.storage, idMaker()).profile).toEqual(EMPTY_PROFILE);
  });

  it("changes nothing when the same progress is added twice", async () => {
    const w = world();
    const first = w.open();
    first.update((p) => afterLearn(p, 4, "Auroras", stamp(1)));
    const saved = w.storage.getItem(GUEST_KEY) ?? "";
    await first.signIn(USER);
    const before = first.profile();

    // The same guest record again (as if the browser had not heard the server's reply).
    w.storage.setItem(GUEST_KEY, saved);
    const again = w.open();
    await again.signIn(USER);

    expect(again.profile()).toEqual(before);
    expect(w.server.count("player_reads")).toBe(1);
  });

  it("sign in, sign out, play as a guest, sign in again: the new guest's progress is added", async () => {
    const v2 = { ...EMPTY_TOTALS, points: 400, answered: 4, correct: 4, learned: ["Mars"] };
    const w = world({ [STORAGE_KEY]: JSON.stringify(v2) });
    // Two events a guest before it folds, so the second guest has a baseline of its own.
    const store = w.open({ guestLogLimit: 2 });
    const firstGuest = "aaaaaaaa-0000-4000-8000-000000000001";

    await store.signIn(USER);
    store.signOut();
    const secondGuest = guestIdIn(w.storage);
    expect(secondGuest).not.toBe(firstGuest);
    store.update((p) => afterLearn(p, 4, "Auroras", stamp(1)));
    store.update((p) => afterAnswer(p, "easy", 5, "Auroras", easy(true, 1), true, 1, {}, stamp(2)));
    store.update((p) => afterLearn(p, 6, "Venus", stamp(3)));
    expect(guestIdIn(w.storage)).toBe(secondGuest);
    await store.signIn(USER);

    expect([...w.server.tables.player_baselines.keys()].sort()).toEqual(
      [firstGuest, secondGuest].sort(),
    );
    expect(store.profile()).toMatchObject({ points: 400 + 100, answered: 5 });
    // Baselines hold no times, so only what was read is checked, not its order.
    expect([...store.profile().learned].sort()).toEqual(["Auroras", "Mars", "Venus"]);
  });

  it("keeps the guest until the server has every row, and tries again", async () => {
    const w = world();
    const store = w.open();
    store.update((p) => afterLearn(p, 4, "Auroras", stamp(1)));
    w.server.online = false;

    await store.signIn(USER);

    expect(store.profile().learned).toEqual(["Auroras"]);
    expect(loadGuest(w.storage, idMaker()).profile.log).toHaveLength(1);
    expect(w.scheduled).toHaveLength(1);

    w.server.online = true;
    w.scheduled[0]?.();
    await store.flush();
    expect(w.server.count("player_reads")).toBe(1);
    expect(loadGuest(w.storage, idMaker()).profile.log).toEqual([]);
  });

  it("sends signed-in play as it happens", async () => {
    const w = world();
    const store = w.open();
    await store.signIn(USER);
    const awards = store.update((p) => afterLiveRun(p, stamp(1)));
    await store.flush();

    expect(awards).toEqual([{ kind: "trophy", id: "web-researcher", tier: "bronze" }]);
    expect(store.profile()).toMatchObject({ liveRuns: 1, log: [] });
    expect(w.server.count("player_searches")).toBe(1);
    const cache = JSON.parse(w.storage.getItem(`${ACCOUNT_KEY}:${USER}`) ?? "{}") as {
      outbox?: unknown[];
    };
    expect(cache.outbox).toEqual([]);
  });

  it("drops a row over the cap, says so once and does not retry it; retries other failures", async () => {
    const w = world();
    const store = w.open();
    await store.signIn(USER);
    w.server.caps.player_reads = 1;

    store.update((p) => afterLearn(p, 1, "Mars", stamp(1)));
    store.update((p) => afterLearn(p, 2, "Venus", stamp(2)));
    store.update((p) => afterLearn(p, 3, "Pluto", stamp(3)));
    await store.flush();

    expect(w.server.count("player_reads")).toBe(1);
    expect(w.warnings).toHaveLength(1);
    expect(w.scheduled).toHaveLength(0);
    const cached = JSON.parse(w.storage.getItem(`${ACCOUNT_KEY}:${USER}`) ?? "{}") as {
      outbox?: unknown[];
    };
    expect(cached.outbox).toEqual([]);

    w.server.online = false;
    store.update((p) => afterLiveRun(p, stamp(4)));
    await store.flush();
    expect(w.scheduled).toHaveLength(1);
    expect(w.warnings).toHaveLength(1);
  });

  it("shows a fresh guest after sign-out and clears the account's cache", async () => {
    const w = world();
    const store = w.open();
    store.update((p) => afterLearn(p, 4, "Auroras", stamp(1)));
    await store.signIn(USER);
    expect(w.storage.data.has(`${ACCOUNT_KEY}:${USER}`)).toBe(true);

    store.signOut();

    expect(store.profile()).toEqual(EMPTY_PROFILE);
    expect(w.storage.data.has(`${ACCOUNT_KEY}:${USER}`)).toBe(false);
  });
});
