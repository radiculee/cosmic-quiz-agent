// Runs after `vite build` (package.json "build"): writes a static page for the home page, Learn,
// each Learn topic, Quiz and the web page, plus sitemap.xml, into dist/. The page shell is kept
// as dist/spa.html, which vercel.json serves for every other address. With no bank access in
// the environment (CI has no secrets) only the fixed pages are made. The work is in
// scripts/prerender/ and is type-checked and tested there; this file only reads and writes files.
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

import { fetchTopics } from "./prerender/bank.ts";
import { fileFor, pagesFor, renderPage, sitemap } from "./prerender/render.ts";

const DIST = "dist";
const url = (process.env.SUPABASE_URL ?? "").trim();
const key = (process.env.SUPABASE_PUBLISHABLE_KEY ?? "").trim();

const shell = await readFile(join(DIST, "index.html"), "utf8");
await copyFile(join(DIST, "index.html"), join(DIST, "spa.html"));

let topics = [];
if (url && key) {
  topics = await fetchTopics({ url, key });
  console.log(`prerender: ${topics.length} topics from the bank`);
} else {
  console.log("prerender: no SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY, so no topic pages");
}

const pages = pagesFor(topics);
for (const page of pages) {
  const file = join(DIST, fileFor(page.path));
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, renderPage(shell, page));
}
await writeFile(join(DIST, "sitemap.xml"), sitemap(pages));
console.log(`prerender: ${pages.length} pages and sitemap.xml`);
