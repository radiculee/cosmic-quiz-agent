import { type RefObject, useLayoutEffect, useRef, useState } from "react";

/** The width of an element in whole pixels, kept up to date as it resizes. The charts draw in
 * real pixels rather than scaling a viewBox, so their text and rounded ends never stretch. */
export function useWidth<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    setWidth(Math.floor(element.getBoundingClientRect().width));
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setWidth(Math.floor(entry.contentRect.width));
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}
