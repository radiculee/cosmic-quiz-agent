import { useCallback, useEffect, useRef, useState } from "react";

import { SiteHeader } from "./components/SiteHeader";
import { TrophyPopup } from "./components/TrophyPopup";
import type { PageProps } from "./pages/common";
import { ExplorePage } from "./pages/ExplorePage";
import { HomePage } from "./pages/HomePage";
import { LearnPage } from "./pages/LearnPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { QuizPage } from "./pages/QuizPage";
import { TrophiesPage } from "./pages/TrophiesPage";
import { matchRoute, type Route, useLocation } from "./router";
import type { Award } from "./trophies";
import type { Difficulty } from "./types";
import { useProfile } from "./useProfile";
import { useTopics } from "./useTopics";

function page(route: Route, props: PageProps) {
  switch (route.page) {
    case "home":
      return <HomePage topicsState={props.topicsState} profile={props.profile} />;
    case "learn":
      return <LearnPage {...props} />;
    case "learn-topic":
      return <LearnPage key={route.slug} slug={route.slug} {...props} />;
    case "quiz":
      return <QuizPage {...props} />;
    case "explore":
      return <ExplorePage {...props} />;
    case "trophies":
      return <TrophiesPage topicsState={props.topicsState} profile={props.profile} />;
    case "not-found":
      return <NotFoundPage />;
  }
}

/**
 * The shell around every page: the header, the current page for the address, and what the
 * pages share (the bank's topics, the saved profile, the chosen difficulty, and the queue of
 * trophy pop-ups, which stays put while the player moves between pages).
 */
export function App() {
  const { pathname } = useLocation();
  const route = matchRoute(pathname);
  const [topicsState, retryTopics] = useTopics();
  const [profile, updateProfile] = useProfile();
  const [difficulty, setDifficulty] = useState<Difficulty>("easy");
  const [popups, setPopups] = useState<(readonly Award[])[]>([]);
  const main = useRef<HTMLElement>(null);
  const firstPath = useRef(pathname);

  const celebrate = useCallback((awards: readonly Award[]) => {
    if (awards.length > 0) {
      setPopups((queue) => [...queue, awards]);
    }
  }, []);
  const closePopup = useCallback(() => setPopups((queue) => queue.slice(1)), []);

  // After moving to another page, start keyboard and screen-reader users at its content.
  useEffect(() => {
    if (pathname !== firstPath.current) {
      firstPath.current = "";
      main.current?.focus({ preventScroll: true });
    }
  }, [pathname]);

  const props: PageProps = {
    topicsState,
    retryTopics,
    profile,
    updateProfile,
    celebrate,
    difficulty,
    setDifficulty,
  };

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader showHomeLink={route.page !== "home"} />
      <main
        ref={main}
        tabIndex={-1}
        className="mx-auto w-full max-w-3xl flex-1 px-4 pb-20 focus:outline-none"
      >
        {page(route, props)}
      </main>
      <TrophyPopup awards={popups[0]} onClose={closePopup} />
    </div>
  );
}
