import type { LearnItem } from "../types";
import { CardFrame } from "./CardFrame";
import { CardActions } from "./CardActions";
import { LearnSourceCheck } from "./SourceCheckPanel";
import { SourcesList } from "./SourcesList";

/** A LEARN explanation with the pages it is based on. */
export function LearnCard({ item, onNext }: { item: LearnItem; onNext: () => void }) {
  const paragraphs = item.explanation.split(/\n+/).filter((text) => text.trim());
  return (
    <CardFrame mode="learn" difficulty={item.difficulty} topic={item.topic}>
      <div className="mt-5 space-y-4 text-lg leading-relaxed text-ink/90">
        {paragraphs.map((text, index) => (
          <p key={index}>{text}</p>
        ))}
      </div>
      <LearnSourceCheck check={item.source_check} />
      <SourcesList sources={item.sources} />
      <CardActions itemId={item.id} nextLabel="Another topic" onNext={onNext} />
    </CardFrame>
  );
}
