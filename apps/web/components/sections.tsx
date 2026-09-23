"use client";

import { useEffect, useState } from "react";
import { Card, Reveal, Section, TraceDivider } from "./primitives";
import { BrandLockup } from "./chrome";
import {
  CITATION, CONTACT, DBT_PROGRAMME, FAQS, FEATURES, LEADERSHIP, PRIVACY_NOTICE, TEAM, WORKFLOW,
} from "@/lib/site";

export function About() {
  return (
    <Section
      id="about"
      eyebrow="About"
      title="What EchoMiner does"
      lead="Echocardiography reports are written for clinicians to read, not for software to analyse. EchoMiner reads them the way a research assistant would, and returns a table."
    >
      <div className="grid gap-8 md:grid-cols-2">
        <p className="text-base leading-relaxed text-muted">
          A departmental echo archive holds thousands of PDF reports. Each one contains the same
          measurements in roughly the same places, but as prose and layout rather than as data.
          Extracting them by hand is the step that stops most retrospective studies before they start.
        </p>
        <p className="text-base leading-relaxed text-muted">
          EchoMiner applies a validated rule-based pipeline to those reports and returns one row per
          study, with the measurement fields, the narrative findings and the impression lines in
          separate columns — plus a quality summary of what it read from each file.
        </p>
      </div>
    </Section>
  );
}

export function WhyStructured() {
  return (
    <Section id="why" tone="mist" eyebrow="Rationale" title="Why structured echocardiography reports matter">
      <div className="grid gap-6 md:grid-cols-3">
        {[
          {
            title: "Free text cannot be counted",
            body: "A cohort described in paragraphs cannot be summarised, stratified or modelled without first being turned into variables.",
          },
          {
            title: "Manual entry does not scale",
            body: "Transcribing an archive by hand is slow, and every pass introduces variation that is invisible in the final dataset.",
          },
          {
            title: "Reproducibility needs provenance",
            body: "A deterministic pipeline with a recorded version lets a reviewer regenerate the same dataset from the same reports.",
          },
        ].map((item, index) => (
          <Reveal key={item.title} delay={index * 0.06}>
            <Card className="h-full">
              <h3 className="font-display text-lg font-semibold text-deep">{item.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-muted">{item.body}</p>
            </Card>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

export function Features() {
  return (
    <Section id="features" eyebrow="Features" title="What you get">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature, index) => (
          <Reveal key={feature.title} delay={index * 0.05}>
            <Card className="h-full">
              <h3 className="font-display text-base font-semibold text-deep">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{feature.body}</p>
            </Card>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

export function Workflow() {
  return (
    <Section id="workflow" tone="mist" eyebrow="Workflow" title="Five steps, one page"
             lead="Registration and the tool live on this page. Nothing redirects you elsewhere.">
      <ol className="grid gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-5">
        {WORKFLOW.map((step, index) => (
          <li key={step.n} className="bg-paper p-6">
            <Reveal delay={index * 0.07}>
              <span className="font-mono text-xs tracking-[0.2em] text-teal">{step.n}</span>
              <h3 className="mt-3 font-display text-base font-semibold text-deep">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{step.body}</p>
            </Reveal>
          </li>
        ))}
      </ol>
    </Section>
  );
}

export function DbtProject() {
  return (
    <Section id="project" eyebrow="Funding" title={DBT_PROGRAMME.heading}>
      <div className="grid gap-10 lg:grid-cols-[1.2fr_1fr]">
        <div>
          {DBT_PROGRAMME.body.map((paragraph) => (
            <p key={paragraph.slice(0, 24)} className="mt-4 text-base leading-relaxed text-muted first:mt-0">
              {paragraph}
            </p>
          ))}
          <p className="mt-6 text-base text-ink">
            The project targets the prevention and management of cardiovascular diseases across three
            emerging research domains:
          </p>
          <ol className="mt-4 space-y-3">
            {DBT_PROGRAMME.domains.map((domain) => (
              <li key={domain.n} className="flex gap-4 border-l-2 border-teal pl-4">
                <span className="font-mono text-sm text-teal">{domain.n}</span>
                <span>
                  <span className="font-medium text-ink">{domain.title}</span>
                  <span className="block text-sm text-muted">{domain.note}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
        <Card>
          <h3 className="font-display text-lg font-semibold text-deep">
            Spatial Health Informatics &amp; Management (Group 3)
          </h3>
          <p className="mt-3 text-sm leading-relaxed text-muted">{DBT_PROGRAMME.groupThree}</p>
          <div className="mt-6 border-t border-line pt-6">
            <BrandLockup height={40} />
          </div>
        </Card>
      </div>
    </Section>
  );
}

function PersonList({ heading, people }: {
  heading: string;
  people: readonly { name: string; role: string; email: string }[];
}) {
  return (
    <div>
      <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-teal">{heading}</h3>
      <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {people.map((person) => (
          <li key={person.email}>
            <Card className="h-full">
              <p className="font-display text-base font-semibold text-ink">{person.name}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted">{person.role}</p>
              <a
                href={`mailto:${person.email}`}
                className="mt-3 inline-block break-all font-mono text-xs text-deep underline underline-offset-4"
              >
                {person.email}
              </a>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Team() {
  return (
    <Section id="team" tone="mist" eyebrow="People" title="Project leadership and development team">
      <div className="space-y-10">
        <PersonList heading="Project leadership" people={LEADERSHIP} />
        <PersonList heading="Group 3 research & development team" people={TEAM} />
      </div>
    </Section>
  );
}

export function ResearchImpact() {
  return (
    <Section
      id="impact"
      eyebrow="Impact"
      title="Research impact"
      lead="EchoMiner exists to make retrospective echocardiography research feasible at archive scale within the DBT-BUILDER cardiovascular programme."
    >
      <Card>
        <p className="text-sm leading-relaxed text-muted">
          Usage and output metrics are published here once verified by the project team. Figures are
          drawn from platform records rather than estimates, and this section stays empty until they
          are confirmed.
        </p>
      </Card>
    </Section>
  );
}

type ContentItem = {
  id: string; slug: string; title: string; body_md: string;
  link_url: string | null; published_at: string | null;
};

/** Published CMS entries, with an empty state rather than invented filler. */
function usePublished(kind: "news" | "publications" | "faqs") {
  const [items, setItems] = useState<ContentItem[] | null>(null);
  useEffect(() => {
    let live = true;
    fetch(`/api/v1/content/${kind}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => live && setItems(data as ContentItem[]))
      .catch(() => live && setItems([]));
    return () => { live = false; };
  }, [kind]);
  return items;
}

export function Publications() {
  const items = usePublished("publications");
  return (
    <Section id="publications" eyebrow="Output" title="Publications">
      {items && items.length > 0 ? (
        <ul className="space-y-4">
          {items.map((item) => (
            <li key={item.id}>
              <Card>
                <p className="font-display text-base font-semibold text-ink">{item.title}</p>
                {item.body_md && <p className="mt-2 text-sm leading-relaxed text-muted">{item.body_md}</p>}
                {item.link_url && (
                  <a href={item.link_url} className="mt-3 inline-block break-all font-mono text-xs text-deep underline underline-offset-4">
                    {item.link_url}
                  </a>
                )}
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <Card>
          <p className="text-sm leading-relaxed text-muted">
            Publications arising from EchoMiner will be listed here as they appear. The software
            itself is archived and citable:
          </p>
          <p className="mt-4 text-sm leading-relaxed text-ink">{CITATION.apa}</p>
          <a href={CITATION.url} className="mt-3 inline-block font-mono text-xs text-deep underline underline-offset-4">
            {CITATION.url}
          </a>
        </Card>
      )}
    </Section>
  );
}

export function News() {
  const items = usePublished("news");
  return (
    <Section id="news" tone="mist" eyebrow="Updates" title="News and updates">
      {items && items.length > 0 ? (
        <ul className="space-y-4">
          {items.map((item) => (
            <li key={item.id}>
              <Card>
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <p className="font-display text-base font-semibold text-ink">{item.title}</p>
                  {item.published_at && (
                    <time className="font-mono text-[11px] text-muted" dateTime={item.published_at}>
                      {item.published_at.slice(0, 10)}
                    </time>
                  )}
                </div>
                {item.body_md && <p className="mt-2 text-sm leading-relaxed text-muted">{item.body_md}</p>}
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <Card>
          <p className="text-sm text-muted">
            No updates have been posted yet. Project announcements, releases and new report-layout
            support will appear here.
          </p>
        </Card>
      )}
    </Section>
  );
}

const CITATION_TABS = [
  { key: "apa", label: "APA", text: CITATION.apa },
  { key: "vancouver", label: "Vancouver", text: CITATION.vancouver },
  { key: "ieee", label: "IEEE", text: CITATION.ieee },
  { key: "bibtex", label: "BibTeX", text: CITATION.bibtex },
  { key: "ris", label: "RIS", text: CITATION.ris },
] as const;

export function Cite() {
  const [active, setActive] = useState<(typeof CITATION_TABS)[number]["key"]>("apa");
  const [copied, setCopied] = useState(false);
  const current = CITATION_TABS.find((tab) => tab.key === active)!;

  async function copy() {
    await navigator.clipboard.writeText(current.text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Section
      id="cite"
      eyebrow="Attribution"
      title="How to cite EchoMiner"
      lead="Acknowledge EchoMiner in any publication, thesis, conference paper, report or scientific communication that uses data generated through this tool."
    >
      <Card>
        <div role="tablist" aria-label="Citation formats" className="flex flex-wrap gap-2">
          {CITATION_TABS.map((tab) => (
            <button
              key={tab.key}
              role="tab"
              type="button"
              aria-selected={active === tab.key}
              onClick={() => setActive(tab.key)}
              className={`rounded px-3 py-1.5 font-mono text-xs uppercase tracking-wider ${
                active === tab.key
                  ? "bg-deep text-white"
                  : "border border-line text-muted hover:text-deep"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <pre className="mt-5 overflow-x-auto whitespace-pre-wrap rounded bg-mist p-4 font-mono text-xs leading-relaxed text-ink">
          {current.text}
        </pre>
        <button
          type="button"
          onClick={copy}
          className="mt-4 rounded border border-line px-4 py-2 text-sm text-deep hover:bg-mist"
        >
          {copied ? "Copied" : "Copy citation"}
        </button>
      </Card>
    </Section>
  );
}

export function Faq() {
  const managed = usePublished("faqs");
  // Managed entries replace the built-in set once any are published.
  const entries = managed && managed.length > 0
    ? managed.map((item) => ({ q: item.title, a: item.body_md }))
    : FAQS.map((item) => ({ q: item.q, a: item.a }));

  return (
    <Section id="faq" tone="mist" eyebrow="Questions" title="Frequently asked questions">
      <div className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-paper">
        {entries.map((item) => (
          <details key={item.q} className="group p-6">
            <summary className="cursor-pointer list-none font-display text-base font-medium text-ink marker:hidden">
              <span className="flex items-start justify-between gap-4">
                {item.q}
                <span aria-hidden className="font-mono text-teal transition group-open:rotate-45">
                  +
                </span>
              </span>
            </summary>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">{item.a}</p>
          </details>
        ))}
      </div>
    </Section>
  );
}

export function Contact() {
  return (
    <>
      <Section id="contact" eyebrow="Contact" title="Get in touch">
        <div className="grid gap-8 md:grid-cols-2">
          <Card>
            <p className="font-display text-lg font-semibold text-ink">{CONTACT.name}</p>
            {CONTACT.lines.map((line) => (
              <p key={line} className="text-sm text-muted">{line}</p>
            ))}
            <a
              href={`mailto:${CONTACT.email}`}
              className="mt-4 inline-block font-mono text-sm text-deep underline underline-offset-4"
            >
              {CONTACT.email}
            </a>
          </Card>
          <Card>
            <h3 id="privacy" className="section font-display text-base font-semibold text-deep">
              Data privacy
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-muted">{PRIVACY_NOTICE}</p>
          </Card>
        </div>
      </Section>
      <TraceDivider label="EchoMiner" />
    </>
  );
}
