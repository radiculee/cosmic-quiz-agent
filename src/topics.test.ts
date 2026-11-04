import { describe, expect, it } from "vitest";

import {
  FACT_CATEGORIES,
  filterTopics,
  findTopic,
  randomTopic,
  searchStatus,
  suggest,
  suggestAny,
  topicKey,
  topicStatus,
  topicVisual,
} from "./topics";
import type { BankTopic, TopicImage } from "./types";

const TOPICS: BankTopic[] = [
  { name: "Quasars", kind: "evergreen", learn: ["easy", "medium", "hard"], quiz: ["hard"] },
  { name: "Dark energy", kind: "evergreen", learn: ["easy"], quiz: ["easy", "medium"] },
  { name: "Sagittarius A*", kind: "evergreen", learn: ["medium"], quiz: ["easy"] },
  { name: "Magnetars", kind: "evergreen", learn: ["easy"], quiz: ["easy"] },
];

function topic(name: string): BankTopic {
  return {
    name,
    kind: "custom",
    learn: ["easy", "medium", "hard"],
    quiz: ["easy", "medium", "hard"],
  };
}

describe("topicKey", () => {
  // The same cases as TOPIC_KEYS in tests/test_api.py: the two rules must not drift apart.
  it.each([
    ["The Cosmic Microwave Background", "cosmic microwave background"],
    ["Cosmic Microwave Background", "cosmic microwave background"],
    ["THE  big   BANG ", "big bang"],
    ["the\tSun", "sun"],
    ["The", "the"],
    [" the ", "the"],
    ["The The Who", "the who"],
    ["Theia", "theia"],
    ["Theory of relativity", "theory of relativity"],
    ["Other worlds", "other worlds"],
    ["", ""],
    ["   ", ""],
  ])("compares %j as %j", (name, key) => {
    expect(topicKey(name)).toBe(key);
  });
});

describe("findTopic", () => {
  it("ignores case and extra spaces", () => {
    expect(findTopic(TOPICS, "  dark   ENERGY ")?.name).toBe("Dark energy");
    expect(findTopic(TOPICS, "")).toBeUndefined();
  });

  it("ignores one leading The on either side, and keeps the stored name", () => {
    expect(findTopic([topic("The Big Bang")], "Big Bang")?.name).toBe("The Big Bang");
    expect(findTopic([topic("Big Bang")], "the big bang")?.name).toBe("Big Bang");
    expect(findTopic([topic("Big Bang")], "The The Big Bang")).toBeUndefined();
  });

  it("prefers the name as typed when the bank has both spellings", () => {
    const both = [topic("The Big Bang"), topic("Big Bang")];

    expect(findTopic(both, "big bang")?.name).toBe("Big Bang");
    expect(findTopic(both, "THE BIG BANG")?.name).toBe("The Big Bang");
  });

  it("does not let The alone match every topic or an empty name", () => {
    const named = [topic("The Moon"), topic("Mars")];

    expect(findTopic(named, "The")).toBeUndefined();
    expect(findTopic(named, " the ")).toBeUndefined();
    expect(findTopic([topic("The")], "the")?.name).toBe("The");
    expect(findTopic([topic("The")], "")).toBeUndefined();
  });

  it("does not take a word that only starts with The for The", () => {
    expect(findTopic([topic("Theia")], "ia")).toBeUndefined();
    expect(findTopic([topic("Theia")], "The ia")).toBeUndefined();
  });
});

describe("suggest", () => {
  it("lists only topics playable at the mode and difficulty, prefix matches first", () => {
    const names = suggest(TOPICS, "a", "quiz", "easy").map((t) => t.name);
    expect(names).toEqual(["Dark energy", "Magnetars", "Sagittarius A*"]);
    expect(suggest(TOPICS, "ma", "quiz", "easy").map((t) => t.name)).toEqual([
      "Magnetars",
    ]);
  });

  it("shows everything playable for an empty query", () => {
    expect(suggest(TOPICS, "", "learn", "easy")).toHaveLength(3);
  });
});

describe("filterTopics", () => {
  it("lists every match for the grid, with no cap", () => {
    const many: BankTopic[] = Array.from({ length: 12 }, (_, i) => ({
      name: `Nebula ${String(i).padStart(2, "0")}`,
      kind: "evergreen",
      learn: ["easy"],
      quiz: [],
    }));
    expect(filterTopics(many, "neb", "learn", "easy")).toHaveLength(12);
    expect(suggest(many, "neb", "learn", "easy")).toHaveLength(8);
    expect(filterTopics(TOPICS, "", "learn", "easy").map((t) => t.name)).toEqual([
      "Dark energy",
      "Magnetars",
      "Quasars",
    ]);
  });
});

describe("randomTopic", () => {
  it("picks a playable topic other than the current one", () => {
    const picked = randomTopic(TOPICS, "quiz", "easy", "Dark energy", () => 0);
    expect(picked?.name).toBe("Sagittarius A*");
  });

  it("prefers topics not yet played, then any other", () => {
    expect(randomTopic(TOPICS, "quiz", "easy", "", () => 0, ["Dark energy"])?.name).toBe(
      "Sagittarius A*",
    );
    const all = ["Dark energy", "Sagittarius A*", "Magnetars"];
    expect(randomTopic(TOPICS, "quiz", "easy", "Magnetars", () => 0, all)?.name).toBe(
      "Dark energy",
    );
  });

  it("treats the two spellings of a name as one topic", () => {
    const both = [topic("Big Bang"), topic("Mars")];

    expect(randomTopic(both, "quiz", "easy", "The Big Bang", () => 0)?.name).toBe("Mars");
    expect(randomTopic(both, "quiz", "easy", "", () => 0, ["The Big Bang"])?.name).toBe("Mars");
  });

  it("falls back to the current topic when it is the only one", () => {
    expect(randomTopic(TOPICS, "quiz", "hard", "Quasars", () => 0.5)?.name).toBe("Quasars");
    expect(randomTopic(TOPICS, "learn", "hard", "", () => 0)?.name).toBe("Quasars");
  });
});

describe("topicStatus", () => {
  it("tells ready, unknown and available-elsewhere apart", () => {
    expect(topicStatus(TOPICS, "", "quiz", "easy").kind).toBe("empty");
    expect(topicStatus(TOPICS, "quasars", "quiz", "hard").kind).toBe("ready");
    expect(topicStatus(TOPICS, "Pulsars", "quiz", "hard").kind).toBe("unknown");
    expect(topicStatus(TOPICS, "Quasars", "quiz", "easy")).toEqual({
      kind: "elsewhere",
      topic: TOPICS[0],
      difficulties: ["hard"],
    });
  });
});

describe("suggestAny", () => {
  it("suggests every bank topic that matches, whatever it has", () => {
    expect(suggestAny(TOPICS, "a").map((t) => t.name)).toEqual([
      "Dark energy",
      "Magnetars",
      "Quasars",
      "Sagittarius A*",
    ]);
  });
});

describe("suggestions and a leading The", () => {
  const named = [topic("Comets"), topic("Mars"), topic("The Moon"), topic("Weather on Titan")];

  it("finds a topic with or without The in the query", () => {
    expect(suggestAny(named, "moon").map((t) => t.name)).toEqual(["The Moon"]);
    expect(suggestAny(named, "the moon").map((t) => t.name)).toEqual(["The Moon"]);
    expect(suggestAny(named, "the mars").map((t) => t.name)).toEqual(["Mars"]);
  });

  it("keeps The in the query for words inside a name", () => {
    expect(suggestAny(named, "the m").map((t) => t.name)).toEqual(["Mars", "The Moon"]);
  });

  it("still shows The topics while only The is typed", () => {
    expect(suggestAny(named, "the").map((t) => t.name)).toEqual(["The Moon", "Weather on Titan"]);
  });

  it("ranks a name that starts with the query first, past its The", () => {
    expect(suggestAny(named, "mo").map((t) => t.name)).toEqual(["The Moon"]);
    const ranked = [topic("Atmosphere of Venus"), topic("The Moon")];
    expect(suggestAny(ranked, "mo").map((t) => t.name)).toEqual(["The Moon", "Atmosphere of Venus"]);
  });
});

describe("searchStatus", () => {
  it("does not offer a paid search for a topic the bank has under the other spelling", () => {
    const stored = topic("The Cosmic Microwave Background");

    expect(searchStatus([stored], "Cosmic Microwave Background")).toEqual({
      kind: "complete",
      topic: stored,
    });
    expect(searchStatus([topic("Big Bang")], "The Big Bang").kind).toBe("complete");
  });

  it("treats The alone as a new topic, not as every topic", () => {
    expect(searchStatus([topic("The Moon")], "The")).toEqual({ kind: "new" });
  });

  it("counts what a search would make: a question and an explanation at each level", () => {
    expect(searchStatus(TOPICS, " ")).toEqual({ kind: "empty" });
    expect(searchStatus(TOPICS, "Pulsars")).toEqual({ kind: "new" });
    // Quasars: explanations at every level, but a question only at HARD.
    expect(searchStatus(TOPICS, "quasars")).toEqual({
      kind: "partial",
      topic: TOPICS[0],
      missing: 2,
    });
    // Sagittarius A*: an explanation only at MEDIUM and a question only at EASY.
    expect(searchStatus(TOPICS, "Sagittarius A*")).toMatchObject({ missing: 4 });
  });

  it("is complete, and so free, only when the bank has every item", () => {
    const full: BankTopic = {
      name: "Pulsars",
      kind: "custom",
      learn: ["easy", "medium", "hard"],
      quiz: ["easy", "medium", "hard"],
    };
    expect(searchStatus([full], "pulsars")).toEqual({ kind: "complete", topic: full });
    const noHardExplanation: BankTopic = { ...full, learn: ["easy", "medium"] };
    expect(searchStatus([noHardExplanation], "pulsars")).toMatchObject({
      kind: "partial",
      missing: 1,
    });
  });
});

describe("topicVisual", () => {
  const IMAGE: TopicImage = {
    src: "/media/quasars-0123456789-card.webp",
    width: 640,
    height: 360,
    preview: "/media/quasars-abcdef0123-preview.webp",
    credit: "ESO, CC BY 4.0, via Wikimedia Commons",
    licence: "CC BY 4.0",
    licence_url: "https://creativecommons.org/licenses/by/4.0",
    page_url: "https://commons.wikimedia.org/wiki/File:Quasar.jpg",
    source: "wikipedia",
  };
  const base: BankTopic = { name: "Quasars", kind: "evergreen", learn: ["easy"], quiz: ["hard"] };

  it("draws the picture when the topic has a complete one", () => {
    expect(topicVisual({ ...base, image: IMAGE })).toEqual({ kind: "image", image: IMAGE });
  });

  it("draws the fact, with its category, when there is no picture", () => {
    const fact = { category: "galaxy", text: "Quasars outshine whole galaxies." };

    expect(topicVisual({ ...base, fact })).toEqual({ kind: "fact", fact, category: "galaxy" });
  });

  it("falls back to the general category for one it does not know", () => {
    const fact = { category: "comets-and-friends", text: "A fact." };

    const visual = topicVisual({ ...base, fact });

    expect(visual.kind === "fact" && visual.category).toBe("space");
    expect(FACT_CATEGORIES).toContain("space");
  });

  it("draws nothing for a topic the image fill has not reached, as an older API sends it", () => {
    expect(topicVisual(base)).toEqual({ kind: "none" });
  });

  it("prefers the picture when both are present", () => {
    const fact = { category: "galaxy", text: "A fact." };

    expect(topicVisual({ ...base, image: IMAGE, fact }).kind).toBe("image");
  });

  it("refuses a picture that is not served from this site or is incomplete", () => {
    const elsewhere = { ...IMAGE, src: "https://upload.wikimedia.org/x.jpg" };
    const sneaky = { ...IMAGE, src: "/media/../api/x" };
    const previewElsewhere = { ...IMAGE, preview: "https://example.com/p.webp" };
    const uncredited = { ...IMAGE, credit: "" };
    const empty = { ...IMAGE, width: 0 };

    for (const image of [elsewhere, sneaky, previewElsewhere, uncredited, empty]) {
      expect(topicVisual({ ...base, image }).kind).toBe("none");
    }
  });

  it("falls back to the fact when the picture is malformed", () => {
    const fact = { category: "galaxy", text: "A fact." };

    const visual = topicVisual({ ...base, image: { ...IMAGE, credit: "" }, fact });

    expect(visual.kind).toBe("fact");
  });
});
