/**
 * A topic's address. Kept apart from the router, which imports React, so the build's prerender
 * (scripts/prerender) can run it under plain Node and the page and the build always agree.
 */

const APOSTROPHES = new Set(["'", String.fromCharCode(0x2019)]);

/** Accents are split off by NFKD normalisation as combining marks (U+0300 to U+036F). */
function isCombiningMark(char: string): boolean {
  const code = char.charCodeAt(0);
  return code >= 0x300 && code <= 0x36f;
}

function isSlugChar(char: string): boolean {
  return (char >= "a" && char <= "z") || (char >= "0" && char <= "9");
}

/**
 * A topic's address: lower case, accents dropped, apostrophes removed, and every other run of
 * characters a single hyphen. "Europa's hidden ocean" is "europas-hidden-ocean".
 */
export function topicSlug(name: string): string {
  let slug = "";
  for (const char of name.normalize("NFKD").toLowerCase()) {
    if (isCombiningMark(char) || APOSTROPHES.has(char)) {
      continue;
    }
    if (isSlugChar(char)) {
      slug += char;
    } else if (slug && !slug.endsWith("-")) {
      slug += "-";
    }
  }
  return slug.endsWith("-") ? slug.slice(0, -1) : slug;
}
