import { useCallback, useEffect, useRef, useState } from "react";

import {
  advance,
  FADE_MS,
  type Layer,
  layer,
  markReady,
  restingScene,
  resume,
  rotating,
  SCENE_SIZES,
  SCENES,
  type Scene as SceneFiles,
  settle,
  show,
  SHOW_MS,
  startSlideshow,
  STILL_FALLBACK,
  timeLeft,
  wantsOtherScenes,
} from "../slideshow";
import { usePageHidden } from "../useBrowserState";

const now = () => performance.now();

/** Run `task` when the browser is idle, or after a second where it cannot say (Safari). */
function whenIdle(task: () => void): () => void {
  if (typeof window.requestIdleCallback === "function") {
    const handle = window.requestIdleCallback(task, { timeout: 3_000 });
    return () => window.cancelIdleCallback(handle);
  }
  const timer = setTimeout(task, 1_000);
  return () => clearTimeout(timer);
}

/**
 * The scene behind every page (index.css `.scene`), fixed so the content scrolls over it. It is
 * decorative, so assistive technology skips it. Inner pages show the observatory still; the home
 * page runs the slideshow (src/slideshow.ts) unless the visitor prefers reduced motion, has paused
 * it, or has the tab in the background.
 */
export function Scene({
  home,
  paused,
  reducedMotion,
}: {
  home: boolean;
  paused: boolean;
  reducedMotion: boolean;
}) {
  const hidden = usePageHidden();
  const [state, setState] = useState(() => startSlideshow(now()));
  const [othersRequested, setOthersRequested] = useState(false);
  const conditions = { home, reducedMotion, paused, hidden };
  const turning = rotating(conditions);
  const wantOthers = wantsOtherScenes(state, conditions);

  // A page that does not take turns rests on its scene.
  useEffect(() => {
    const rest = restingScene({ home, reducedMotion });
    if (rest !== null) {
      setState((current) => show(current, rest, now()));
    }
  }, [home, reducedMotion]);

  // At the end of each turn, fade to the next ready scene. When the scenes start taking turns
  // (again), the one showing gets a full turn first.
  const wasTurning = useRef(false);
  const { since } = state;
  useEffect(() => {
    if (!turning) {
      wasTurning.current = false;
      return undefined;
    }
    let wait = timeLeft(since, now());
    if (!wasTurning.current) {
      wasTurning.current = true;
      setState((current) => resume(current, now()));
      wait = SHOW_MS;
    }
    const timer = setTimeout(() => setState((current) => advance(current, now())), wait);
    return () => clearTimeout(timer);
  }, [turning, since]);

  // Once a fade has ended, the scene under it is hidden.
  const fading = state.under !== null;
  const { current } = state;
  useEffect(() => {
    if (!fading) {
      return undefined;
    }
    const timer = setTimeout(() => setState(settle), FADE_MS);
    return () => clearTimeout(timer);
  }, [fading, current]);

  // The other scenes are fetched once the first is decoded, while the browser is idle.
  useEffect(() => {
    if (!wantOthers || othersRequested) {
      return undefined;
    }
    return whenIdle(() => setOthersRequested(true));
  }, [wantOthers, othersRequested]);

  const onReady = useCallback(
    (scene: number) => setState((slideshow) => markReady(slideshow, scene)),
    [],
  );

  return (
    <div className="scene" aria-hidden="true">
      {SCENES.map(
        (scene, index) =>
          (index === 0 || othersRequested) && (
            <SceneImage
              key={scene.id}
              scene={scene}
              index={index}
              place={layer(state, index)}
              onReady={onReady}
            />
          ),
      )}
    </div>
  );
}

/** One scene, at the width the screen needs. It can take a turn once it is decoded. */
function SceneImage({
  scene,
  index,
  place,
  onReady,
}: {
  scene: SceneFiles;
  index: number;
  place: Layer;
  onReady: (scene: number) => void;
}) {
  const image = useRef<HTMLImageElement>(null);
  useEffect(() => {
    let live = true;
    image.current?.decode().then(
      () => {
        if (live) {
          onReady(index);
        }
      },
      () => {
        // Not decodable here (no WebP, or the fetch failed): this scene never takes a turn.
      },
    );
    return () => {
      live = false;
    };
  }, [index, onReady]);

  const first = index === 0;
  return (
    <picture>
      <source type="image/webp" srcSet={scene.srcSet} sizes={SCENE_SIZES} />
      <img
        ref={image}
        src={first ? STILL_FALLBACK : undefined}
        alt=""
        data-layer={place}
        decoding="async"
        fetchPriority={first ? "high" : "low"}
      />
    </picture>
  );
}
