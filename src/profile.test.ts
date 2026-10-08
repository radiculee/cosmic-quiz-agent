import { describe, expect, it } from "vitest";

import { answerInRun, planRun, scoreAnswer } from "./game";
import {
  afterAnswer,
  afterLearn,
  afterLiveRun,
  afterRun,
  EMPTY_PROFILE,
  loadProfile,
  type Profile,
  saveProfile,
  STORAGE_KEY,
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
  };
}

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
    expect(loadProfile(storage)).toEqual(profile);
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
