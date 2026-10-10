import { useCallback, useEffect, useRef, useState } from "react";

import { Scene } from "./components/Scene";
import { SiteFooter } from "./components/SiteFooter";
import { SiteHeader } from "./components/SiteHeader";
import { TrophyPopup } from "./components/TrophyPopup";
import type { PageProps } from "./pages/common";
import { ExplorePage } from "./pages/ExplorePage";
import { HomePage, type SlideshowControl } from "./pages/HomePage";
import { LearnPage } from "./pages/LearnPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PrivacyPage } from "./pages/PrivacyPage";
import { QuizPage } from "./pages/QuizPage";
import { TrophiesPage } from "./pages/TrophiesPage";
import { matchRoute, PATHS, type Route, useLocation } from "./router";
import type { Award } from "./trophies";
import type { Difficulty } from "./types";
import { useReducedMotion } from "./useBrowserState";
import { useProfile } from "./useProfile";
import { useTopics } from "./useTopics";

function page(route: Route, props: PageProps, slideshow: SlideshowControl | null) {
  switch (route.page) {
    case "home":
      return (
        <HomePage topicsState={props.topicsState} profile={props.profile} slideshow={slideshow} />
      );
    case "learn":
      return <LearnPage {...props} />;
    case "learn-topic":
      return <LearnPage key={route.slug} slug={route.slug} {...props} />;
    case "quiz":
      return <QuizPage {...props} />;
    case "explore":
    case "explore-stats":
      // One element for both addresses, so the page (and a search it is running) stays mounted
      // while the analytics panel opens over it.
      return <ExplorePage {...props} statsOpen={route.page === "explore-stats"} />;
    case "trophies":
      return <TrophiesPage topicsState={props.topicsState} profile={props.profile} />;
    case "privacy":
      return <PrivacyPage />;
    case "not-found":
      return <NotFoundPage />;
  }
}

/**
 * The shell around every page: the scene behind it, the header, the current page for the address,
 * and what the pages share (the bank's topics, the saved profile, the chosen difficulty, the queue
 * of trophy pop-ups, which stays put while the player moves between pages, and whether the home
 * page's slideshow is paused).
 */
export function App() {
  const { pathname } = useLocation();
  const route = matchRoute(pathname);
  const [topicsState, retryTopics] = useTopics();
  const [profile, updateProfile] = useProfile();
  const [difficulty, setDifficulty] = useState<Difficulty>("easy");
  const [popups, setPopups] = useState<(readonly Award[])[]>([]);
  const reducedMotion = useReducedMotion();
  const [scenesPaused, setScenesPaused] = useState(false);
  const toggleScenes = useCallback(() => setScenesPaused((paused) => !paused), []);
  const main = useRef<HTMLElement>(null);
  // The analytics panel opens over the web page, so moving between the two is not a new page.
  const pagePath = route.page === "explore-stats" ? PATHS.explore : pathname;
  const firstPath = useRef(pagePath);

  const celebrate = useCallback((awards: readonly Award[]) => {
    if (awards.length > 0) {
      setPopups((queue) => [...queue, awards]);
    }
  }, []);
  const closePopup = useCallback(() => setPopups((queue) => queue.slice(1)), []);

  // After moving to another page, start keyboard and screen-reader users at its content.
  useEffect(() => {
    if (pagePath !== firstPath.current) {
      firstPath.current = "";
      main.current?.focus({ preventScroll: true });
    }
  }, [pagePath]);

  const props: PageProps = {
    topicsState,
    retryTopics,
    profile,
    updateProfile,
    celebrate,
    difficulty,
    setDifficulty,
  };

  // The slideshow does not rotate under reduced motion, so it has nothing to pause.
  const slideshow = reducedMotion ? null : { paused: scenesPaused, onToggle: toggleScenes };

  return (
    <>
      <Scene home={route.page === "home"} paused={scenesPaused} reducedMotion={reducedMotion} />
      <div className="flex min-h-dvh flex-col">
        <SiteHeader showHomeLink={route.page !== "home"} />
        <main
          ref={main}
          tabIndex={-1}
          className="mx-auto w-full max-w-3xl flex-1 px-4 pb-20 focus:outline-none"
        >
          {page(route, props, slideshow)}
        </main>
        <SiteFooter />
        <TrophyPopup awards={popups[0]} onClose={closePopup} />
      </div>
    </>
  );
}
