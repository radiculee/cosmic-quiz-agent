import { describe, expect, it } from "vitest";

import indexHtml from "../index.html?raw";
import {
  advance,
  type Conditions,
  layer,
  markReady,
  nextScene,
  restingScene,
  resume,
  rotating,
  SCENE_SIZES,
  SCENES,
  settle,
  show,
  SHOW_MS,
  type Slideshow,
  startSlideshow,
  timeLeft,
  wantsOtherScenes,
} from "./slideshow";

const HOME: Conditions = { home: true, reducedMotion: false, paused: false, hidden: false };

/** A slideshow with the given scenes decoded, showing `current`. */
function withReady(ready: readonly number[], current = 0): Slideshow {
  let state = { ...startSlideshow(0), current };
  for (const scene of ready) {
    state = markReady(state, scene);
  }
  return state;
}

describe("the scenes", () => {
  it("take turns in order, the observatory first", () => {
    expect(SCENES.map((scene) => scene.id)).toEqual(["observatory", "piano", "glasshouse"]);
  });

  it("each come at three versioned widths", () => {
    for (const scene of SCENES) {
      const widths = [1280, 1920, 2560].map(
        (width) => `/scenes/${scene.id}-v1-${width}.webp ${width}w`,
      );
      expect(scene.srcSet).toBe(widths.join(", "));
    }
  });
});

describe("when the scenes take turns", () => {
  it("only on the home page, and not under reduced motion, paused or in a hidden tab", () => {
    expect(rotating(HOME)).toBe(true);
    expect(rotating({ ...HOME, home: false })).toBe(false);
    expect(rotating({ ...HOME, reducedMotion: true })).toBe(false);
    expect(rotating({ ...HOME, paused: true })).toBe(false);
    expect(rotating({ ...HOME, hidden: true })).toBe(false);
  });

  it("inner pages and reduced motion rest on the observatory; home keeps its scene", () => {
    expect(restingScene({ home: false, reducedMotion: false })).toBe(0);
    expect(restingScene({ home: true, reducedMotion: true })).toBe(0);
    expect(restingScene({ home: false, reducedMotion: true })).toBe(0);
    expect(restingScene({ home: true, reducedMotion: false })).toBeNull();
  });

  it("fetches the other scenes only once the first is decoded, and only to rotate them", () => {
    const fresh = startSlideshow(0);
    const firstReady = markReady(fresh, 0);
    expect(wantsOtherScenes(fresh, HOME)).toBe(false);
    expect(wantsOtherScenes(firstReady, HOME)).toBe(true);
    expect(wantsOtherScenes(firstReady, { ...HOME, home: false })).toBe(false);
    expect(wantsOtherScenes(firstReady, { ...HOME, reducedMotion: true })).toBe(false);
    expect(wantsOtherScenes(firstReady, { ...HOME, paused: true })).toBe(false);
    expect(wantsOtherScenes(firstReady, { ...HOME, hidden: true })).toBe(false);
  });
});

describe("the next scene", () => {
  it("is the next one in order, wrapping around after the last", () => {
    expect(nextScene(withReady([0, 1, 2], 0))).toBe(1);
    expect(nextScene(withReady([0, 1, 2], 1))).toBe(2);
    expect(nextScene(withReady([0, 1, 2], 2))).toBe(0);
  });

  it("skips a scene that is not decoded yet", () => {
    expect(nextScene(withReady([0, 2], 0))).toBe(2);
    expect(nextScene(withReady([0, 2], 2))).toBe(0);
  });

  it("is none when no other scene is ready", () => {
    expect(nextScene(withReady([0], 0))).toBeNull();
    expect(nextScene(withReady([], 0))).toBeNull();
  });
});

describe("a turn", () => {
  it("lasts SHOW_MS from when it started", () => {
    expect(SHOW_MS).toBe(10_000);
    expect(timeLeft(1_000, 1_000)).toBe(SHOW_MS);
    expect(timeLeft(1_000, 6_000)).toBe(5_000);
    expect(timeLeft(1_000, 1_000 + SHOW_MS + 50)).toBe(0);
  });

  it("goes round every ready scene in order", () => {
    let state = withReady([0, 1, 2]);
    const seen = [state.current];
    for (let turn = 1; turn <= 4; turn++) {
      state = settle(advance(state, turn * SHOW_MS));
      seen.push(state.current);
    }
    expect(seen).toEqual([0, 1, 2, 0, 1]);
  });

  it("starts again on the same scene when no other is ready", () => {
    const state = withReady([0]);
    const after = advance(state, SHOW_MS);
    expect(after.current).toBe(0);
    expect(after.under).toBeNull();
    expect(after.since).toBe(SHOW_MS);
  });

  it("is a full one after a pause or a hidden tab", () => {
    const state = { ...withReady([0, 1]), since: 0 };
    expect(timeLeft(state.since, 9_000)).toBe(1_000);
    const resumed = resume(state, 30_000);
    expect(timeLeft(resumed.since, 30_000)).toBe(SHOW_MS);
    expect(resumed.current).toBe(0);
  });
});

describe("the crossfade", () => {
  it("draws the new scene on top of the old one until the fade ends", () => {
    const fading = show(withReady([0, 1, 2]), 1, 500);
    expect(fading.since).toBe(500);
    expect([0, 1, 2].map((scene) => layer(fading, scene))).toEqual(["under", "top", "hidden"]);

    const settled = settle(fading);
    expect([0, 1, 2].map((scene) => layer(settled, scene))).toEqual(["hidden", "top", "hidden"]);
  });

  it("changes nothing when the scene is already showing", () => {
    const state = withReady([0, 1]);
    expect(show(state, 0, 999)).toBe(state);
  });

  it("shows the first scene on top from the start", () => {
    const state = startSlideshow(0);
    expect(layer(state, 0)).toBe("top");
    expect(layer(state, 1)).toBe("hidden");
  });
});

describe("decoding", () => {
  it("marks a scene ready once, and leaves the state alone after that", () => {
    const state = markReady(startSlideshow(0), 2);
    expect(state.ready).toEqual([false, false, true]);
    expect(markReady(state, 2)).toBe(state);
  });
});

describe("the page's own files", () => {
  it("preload exactly the file the first scene will use", () => {
    const preload = /<link\s+rel="preload"[^>]*>/.exec(indexHtml)?.[0] ?? "";
    expect(preload).toContain('as="image"');
    expect(preload).toContain('type="image/webp"');
    expect(preload).toContain(`imagesrcset="${SCENES[0]?.srcSet ?? "missing"}"`);
    expect(preload).toContain(`imagesizes="${SCENE_SIZES}"`);
  });

  it("pick the full-width file up to 4:3, where index.css shows the whole scene", () => {
    expect(SCENE_SIZES.startsWith("(max-aspect-ratio: 4/3) 100vw")).toBe(true);
  });
});
