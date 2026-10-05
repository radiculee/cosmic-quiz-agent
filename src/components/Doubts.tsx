/** Why the publish gate held a live item back, in the checks' own words. */
export function Doubts({ doubts }: { doubts: string[] }) {
  if (doubts.length === 0) {
    return null;
  }
  return (
    <section aria-labelledby="doubts-heading" className="mt-8 rounded-sm border border-gold/30 bg-gold/5 px-4 py-4">
      <h3 id="doubts-heading" className="font-pixel text-[9px] uppercase text-gold">
        Why it is not fully verified
      </h3>
      <p className="mt-2 text-xs text-slate">
        The automatic checks had doubts, so a person looks at it before it joins the bank.
      </p>
      <ul className="mt-3 space-y-2 text-sm leading-relaxed text-ink/85">
        {doubts.map((doubt) => (
          <li key={doubt} className="pixel-bullet">
            {doubt}
          </li>
        ))}
      </ul>
    </section>
  );
}
