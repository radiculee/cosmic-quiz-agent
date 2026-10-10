/**
 * The scenes behind the app (DESIGN.md decision 4): the observatory as a still behind every inner
 * page, and on the home page a slideshow in which the scenes take turns, each crossfading in over
 * the one before. Pure rules over plain data, so they are tested without a browser
 * (slideshow.test.ts); src/components/Scene.tsx runs them.
 *
 * The slideshow stops for people who prefer reduced motion (the observatory stays), while the
 * player has paused it, and while the tab is hidden (WCAG 2.2.2). A scene takes its turn only
 * once its image is decoded, so a crossfade never shows half an image.
 */

export interface Scene {
  id: string;
  /** WebP at 1280, 1920 and 2560 px wide, for `srcset`. */
  srcSet: string;
}

/**
 * In turn order, the observatory first: it is the still on inner pages and the image index.html
 * preloads. The file names carry a version, so they are cached for good (vercel.json); a changed
 * image gets a new name. The portal scene is left out until it has a version with clear sky for
 * the title (decided 2026-10-10).
 */
export const SCENES: readonly Scene[] = [
  {
    id: "observatory",
    srcSet:
      "/scenes/observatory-v1-1280.webp 1280w, /scenes/observatory-v1-1920.webp 1920w, /scenes/observatory-v1-2560.webp 2560w",
  },
  {
    id: "piano",
    srcSet:
      "/scenes/piano-v1-1280.webp 1280w, /scenes/piano-v1-1920.webp 1920w, /scenes/piano-v1-2560.webp 2560w",
  },
  {
    id: "glasshouse",
    srcSet:
      "/scenes/glasshouse-v1-1280.webp 1280w, /scenes/glasshouse-v1-1920.webp 1920w, /scenes/glasshouse-v1-2560.webp 2560w",
  },
];

/** The observatory as JPEG, for a browser without WebP (the other scenes are then never shown). */
export const STILL_FALLBACK = "/scenes/observatory-v1-1920.jpg";

/**
 * How wide a scene is drawn, so the browser picks the right file: the full width up to 4:3 (the
 * whole scene, pinned to the bottom), wider than the screen between 4:3 and the images' 85:48
 * (`cover`, filled by height), and the full width beyond. Matches index.css, and the preload in
 * index.html (slideshow.test.ts checks both).
 */
export const SCENE_SIZES = "(max-aspect-ratio: 4/3) 100vw, (max-aspect-ratio: 85/48) 178vh, 100vw";

/** Each scene's turn, and its crossfade (index.css draws the fade in the same time). */
export const SHOW_MS = 10_000;
export const FADE_MS = 1_500;

export interface Slideshow {
  /** The scene showing, or fading in: an index into SCENES. */
  current: number;
  /** The scene under it while it fades in; null once the fade has ended. */
  under: number | null;
  /** Which scenes are decoded and so can take a turn. */
  ready: readonly boolean[];
  /** When the current scene's turn started (ms on the page's clock). */
  since: number;
}

/** What decides whether the scenes take turns. */
export interface Conditions {
  /** On the home page: every other page shows the still. */
  home: boolean;
  reducedMotion: boolean;
  /** The player pressed Pause. */
  paused: boolean;
  /** The tab is in the background. */
  hidden: boolean;
}

export function startSlideshow(now: number): Slideshow {
  return { current: 0, under: null, ready: SCENES.map(() => false), since: now };
}

/** Whether the scenes take turns now. */
export function rotating(conditions: Conditions): boolean {
  return (
    conditions.home && !conditions.reducedMotion && !conditions.paused && !conditions.hidden
  );
}

/**
 * The scene a page rests on, or null to keep the one showing: inner pages and reduced motion show
 * the observatory; on the home page, a paused or hidden slideshow keeps its scene.
 */
export function restingScene(conditions: Pick<Conditions, "home" | "reducedMotion">): number | null {
  return conditions.home && !conditions.reducedMotion ? null : 0;
}

/**
 * Whether to fetch the other scenes now: only while they would take turns, and only once the
 * first has been decoded, so they never compete with it. An inner page loads one scene only.
 */
export function wantsOtherScenes(state: Slideshow, conditions: Conditions): boolean {
  return rotating(conditions) && state.ready[0] === true;
}

/** The next scene that is ready, in order and wrapping around; null when no other one is. */
export function nextScene(state: Slideshow): number | null {
  for (let step = 1; step < SCENES.length; step++) {
    const index = (state.current + step) % SCENES.length;
    if (state.ready[index] === true) {
      return index;
    }
  }
  return null;
}

/** Milliseconds left in the current scene's turn (0 once it is over). */
export function timeLeft(since: number, now: number): number {
  return Math.max(0, since + SHOW_MS - now);
}

/** Fade `scene` in over the one showing, which stays under it until the fade ends. */
export function show(state: Slideshow, scene: number, now: number): Slideshow {
  if (scene === state.current) {
    return state;
  }
  return { ...state, current: scene, under: state.current, since: now };
}

/**
 * The current scene's turn is over: fade to the next ready scene. If none is ready yet, the scene
 * showing starts another turn.
 */
export function advance(state: Slideshow, now: number): Slideshow {
  const next = nextScene(state);
  return next === null ? { ...state, since: now } : show(state, next, now);
}

/** The fade has ended: nothing needs to stay under the scene showing. */
export function settle(state: Slideshow): Slideshow {
  return state.under === null ? state : { ...state, under: null };
}

/** A scene's image is decoded. */
export function markReady(state: Slideshow, scene: number): Slideshow {
  if (state.ready[scene] !== false) {
    return state;
  }
  return { ...state, ready: state.ready.map((ready, index) => ready || index === scene) };
}

/**
 * The scenes take turns again (after a pause, a hidden tab, or on arriving at the home page): the
 * scene showing gets a full turn.
 */
export function resume(state: Slideshow, now: number): Slideshow {
  return { ...state, since: now };
}

export type Layer = "top" | "under" | "hidden";

/**
 * How a scene is drawn: the current one on top (fading in when it has just changed), the one it
 * replaces under it at full strength, so the fade never shows the sky through both, and the rest
 * hidden.
 */
export function layer(state: Slideshow, scene: number): Layer {
  if (scene === state.current) {
    return "top";
  }
  return scene === state.under ? "under" : "hidden";
}
