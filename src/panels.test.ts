import { describe, expect, it } from "vitest";

import { loadPanel, PANEL_KEY_PREFIX, savePanel } from "./panels";

function memoryStorage(entries: Record<string, string> = {}) {
  const data = new Map(Object.entries(entries));
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
  };
}

const refusing = {
  getItem: () => {
    throw new Error("blocked");
  },
  setItem: () => {
    throw new Error("blocked");
  },
};

describe("loadPanel", () => {
  it("starts closed when nothing was saved", () => {
    expect(loadPanel(memoryStorage(), "explanation")).toBe(false);
    expect(loadPanel(memoryStorage(), "sources")).toBe(false);
  });

  it("starts closed when there is no storage or it refuses to answer", () => {
    expect(loadPanel(undefined, "sources")).toBe(false);
    expect(loadPanel(refusing, "sources")).toBe(false);
  });

  it("starts closed on a value it does not know", () => {
    expect(loadPanel(memoryStorage({ [`${PANEL_KEY_PREFIX}sources`]: "yes" }), "sources")).toBe(
      false,
    );
  });
});

describe("savePanel", () => {
  it("remembers the last choice for each panel on its own", () => {
    const storage = memoryStorage();
    savePanel(storage, "explanation", true);
    savePanel(storage, "sources", true);
    savePanel(storage, "sources", false);
    expect(loadPanel(storage, "explanation")).toBe(true);
    expect(loadPanel(storage, "sources")).toBe(false);
  });

  it("does not throw where storage refuses or is missing", () => {
    expect(() => savePanel(refusing, "sources", true)).not.toThrow();
    expect(() => savePanel(undefined, "sources", true)).not.toThrow();
  });
});
