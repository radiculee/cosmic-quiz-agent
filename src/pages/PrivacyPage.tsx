import type { ReactNode } from "react";

import { usePageTitle } from "../router";
import { PageHeading } from "./common";

const CONTACT_URL = "https://www.vedantgaikwad.ie/#contact";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8 first:mt-0">
      <h2 className="font-heading text-xl font-bold">{title}</h2>
      <div className="mt-3 space-y-3 leading-relaxed text-ink/90">{children}</div>
    </section>
  );
}

function Points({ children }: { children: ReactNode }) {
  return <ul className="space-y-2">{children}</ul>;
}

function Point({ children }: { children: ReactNode }) {
  return <li className="pixel-bullet">{children}</li>;
}

/**
 * What the site keeps, why and for how long, in plain words (docs/PLAN.md, Session 10b). The same text
 * is in the README. tests/test_packaging.py checks the retention times it states against the
 * database's clean-up.
 */
export function PrivacyPage() {
  usePageTitle("Privacy");
  return (
    <div>
      <PageHeading title="Privacy">
        What this site keeps, why, and for how long. Last updated 10 October 2026.
      </PageHeading>

      <article className="pixel-border mt-10 rounded-sm bg-surface px-5 py-7 sm:px-8">
        <Section title="In short">
          <Points>
            <Point>No accounts, no cookies, no ads and no tracking.</Point>
            <Point>Your progress stays in your browser.</Point>
            <Point>
              The server never stores your IP address. It keeps a salted hash of it, a visitor
              code, to apply limits per visitor: removed after a day, or after 30 days for a
              report.
            </Point>
            <Point>
              The fonts and images come from this site, so a visit reaches no other company
              besides the host.
            </Point>
            <Point>
              Analytics for nerds shows totals about the agent&rsquo;s own work, never about
              visitors.
            </Point>
          </Points>
        </Section>

        <Section title="In your browser">
          <p>
            Your rank, points, trophies, the topics you have read and the questions you have seen
            are saved in this browser&rsquo;s local storage, not on the server. The numbers of the
            questions you have seen are sent with each request for a new one, so you are not shown
            them again; the server does not keep them. Clearing this site&rsquo;s data in your
            browser deletes it all.
          </p>
        </Section>

        <Section title="On the server">
          <p>
            When your browser calls the site&rsquo;s API, the server turns your IP address into a
            visitor code: a salted hash (for an IPv6 address, of its first half). The address
            itself is never stored, and the code cannot be turned back into it without a secret
            that only the server holds. The code is kept with:
          </p>
          <Points>
            <Point>
              Request counts: how many requests a visitor made in an hour, so no one can flood the
              site. Deleted after a day.
            </Point>
            <Point>
              Live searches on the web page: the topic you type, the level, when it ran, what it
              cost and how it ended. The visitor code is removed after a day; the rest is kept.
              What the agent writes is checked like everything else and may join the question
              bank, for everyone to play.
            </Point>
            <Point>
              Reports: which question, the reason you give, and when. The visitor code is removed
              after 30 days; the report is kept. Please keep personal details out of a reason.
            </Point>
          </Points>
          <p>
            A daily clean-up removes the codes, so one can last up to a day longer than these
            times.
          </p>
        </Section>

        <Section title="Who else handles data">
          <Points>
            <Point>
              Vercel hosts the site and runs its functions in Dublin. It handles your IP address to
              serve each request and keeps short-lived logs under its own privacy policy.
            </Point>
            <Point>Supabase holds the database, in Ireland.</Point>
            <Point>
              A live search sends the topic you type, and nothing else about you, to Anthropic
              (Claude researches and writes) and TypeSafe (it checks that the topic is about
              astronomy, and checks the answers against their sources). The topic is also used to
              search Wikipedia, NASA, ESA and arXiv.
            </Point>
          </Points>
        </Section>

        <Section title="Your rights">
          <p>
            Cosmic Quiz is run by Vedant Gaikwad, in Dublin, Ireland. Under the GDPR you can ask
            what is kept about you, and ask for it to be corrected or deleted. As the server keeps
            only visitor codes, finding your records needs the IP address you used and roughly
            when. Send a request through the{" "}
            <a
              href={CONTACT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal underline underline-offset-4 hover:text-ink"
            >
              contact form on vedantgaikwad.ie
            </a>
            .
          </p>
        </Section>
      </article>
    </div>
  );
}
