import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TopicGrid } from "./components/TopicGrid";
import type { BankTopic, TopicImage } from "./types";

const IMAGE: TopicImage = {
  src: "/media/jupiter.jpg",
  width: 640,
  height: 360,
  credit: "Photo: Jane Q. Astronomer",
  licence: "CC BY-SA 4.0",
  licence_url: "https://creativecommons.org/licenses/by-sa/4.0/",
  page_url: "https://commons.wikimedia.org/wiki/File:Jupiter.jpg",
  source: "wikipedia",
};

/** A picture as the Curator writes it: the credit already names the licence. */
const CURATOR_IMAGE: TopicImage = {
  ...IMAGE,
  credit: "ESO, CC BY 4.0, via Wikimedia Commons",
  licence: "CC BY 4.0",
  licence_url: "https://creativecommons.org/licenses/by/4.0",
};

function visibleText(html: string): string {
  return html.replace(/<[^>]*>/g, "");
}

function topic(name: string, extra: Partial<BankTopic> = {}): BankTopic {
  return { name, kind: "evergreen", learn: ["easy"], quiz: ["easy"], ...extra };
}

function render(topics: BankTopic[], learned: string[] = []): string {
  return renderToStaticMarkup(<TopicGrid topics={topics} learned={new Set(learned)} />);
}

function anchors(html: string): string[] {
  return [...html.matchAll(/<a [^>]*href="([^"]+)"/g)].map((match) => match[1] ?? "");
}

describe("TopicGrid", () => {
  it("shows the picture with its credit, the licence and the file page linked", () => {
    const html = render([topic("Jupiter", { image: IMAGE })]);
    expect(html).toContain('src="/media/jupiter.jpg"');
    expect(html).toContain("Photo: Jane Q. Astronomer");
    expect(anchors(html)).toEqual([
      "/learn/jupiter",
      "https://creativecommons.org/licenses/by-sa/4.0/",
      "https://commons.wikimedia.org/wiki/File:Jupiter.jpg",
    ]);
  });

  it("names the topic in the picture's alt text and leaves the credit to the line below", () => {
    const html = render([topic("Jupiter", { image: IMAGE })]);
    expect(html).toContain('alt="Jupiter"');
  });

  it("keeps the topic link first, so the tab order is title, licence, file page", () => {
    const html = render([topic("Jupiter", { image: IMAGE })]);
    expect(html.indexOf("data-title")).toBeLessThan(html.indexOf("creativecommons.org"));
  });

  it("names the licence without a link when it has no address", () => {
    const { licence_url: _unused, ...bare } = IMAGE;
    const html = render([topic("Mars", { image: bare })]);
    expect(html).toContain("CC BY-SA 4.0");
    expect(anchors(html)).toEqual(["/learn/mars", IMAGE.page_url]);
  });

  it("names the licence once, linked in its place, when the credit already names it", () => {
    const html = render([topic("Jupiter", { image: CURATOR_IMAGE })]);
    expect(html).toContain("ESO, <a ");
    expect(html).toContain("CC BY 4.0<span");
    expect(html).toContain("</a>, via Wikimedia Commons · ");
    expect(anchors(html)).toEqual([
      "/learn/jupiter",
      "https://creativecommons.org/licenses/by/4.0",
      IMAGE.page_url,
    ]);
    expect(visibleText(html).match(/CC BY 4\.0/g) ?? []).toHaveLength(1);
  });

  it("names the licence once, with no link, when the credit names it and it has no address", () => {
    const image: TopicImage = {
      src: "/media/moon.jpg",
      width: 640,
      height: 360,
      credit: "NASA, Public domain, via Wikimedia Commons",
      licence: "Public domain",
      page_url: "https://commons.wikimedia.org/wiki/File:Moon.jpg",
      source: "wikipedia",
    };
    const html = render([topic("Moon", { image })]);
    expect(html).toContain("NASA, Public domain, via Wikimedia Commons · ");
    expect(visibleText(html).match(/Public domain/g) ?? []).toHaveLength(1);
    expect(anchors(html)).toEqual(["/learn/moon", image.page_url]);
  });

  it("adds the licence after a hand-written credit that does not name it", () => {
    const html = render([topic("Jupiter", { image: IMAGE })]);
    expect(html).toContain("Photo: Jane Q. Astronomer, <a ");
    expect(visibleText(html).match(/CC BY-SA 4\.0/g) ?? []).toHaveLength(1);
  });

  it("shows the fact and a glyph, and no credit, where there is no picture", () => {
    const html = render([
      topic("Quasar", { fact: { category: "galaxy", text: "Quasars outshine whole galaxies." } }),
    ]);
    expect(html).toContain("Quasars outshine whole galaxies.");
    expect(html).toContain("<svg");
    expect(anchors(html)).toEqual(["/learn/quasar"]);
  });

  it("shows the whole fact, with no line limit that could cut it", () => {
    const text = `${"Quasars outshine whole galaxies across the observable universe. ".repeat(3)}End.`;
    const html = render([topic("Quasar", { fact: { category: "galaxy", text } })]);
    expect(html).toContain(text);
    expect(html).not.toContain("line-clamp");
  });

  it("shows only the name for a topic with neither", () => {
    const html = render([topic("Comet")]);
    expect(html).toContain("Comet");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<svg");
  });

  it("marks a topic already read, and only that one", () => {
    const html = render([topic("Jupiter"), topic("Mars")], ["Mars"]);
    expect(html.match(/>Read</g) ?? []).toHaveLength(1);
    expect(html.indexOf(">Read<")).toBeGreaterThan(html.indexOf("Jupiter"));
  });

  it("labels news and web topics", () => {
    const html = render([topic("Eclipse", { kind: "news" }), topic("Pulsar", { kind: "custom" })]);
    expect(html).toContain(">News<");
    expect(html).toContain(">Web<");
  });
});
