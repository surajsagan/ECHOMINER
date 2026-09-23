"use client";

import { motion, useReducedMotion } from "framer-motion";
import { SITE } from "@/lib/site";

/**
 * The hero thesis is the artefact itself: a Doppler spectral envelope that draws
 * once, with the measurements it yields appearing as mono readouts beneath it.
 * That is what the tool does, stated visually rather than described.
 */
export function Hero() {
  const reduced = useReducedMotion();

  return (
    <section id="top" className="section relative overflow-hidden border-b border-line bg-paper">
      <div className="mx-auto grid w-full max-w-content gap-12 px-6 py-20 lg:grid-cols-[1.05fr_1fr] lg:py-28">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-teal">
            DBT-BUILDER · Group 3 · JSS AHER
          </p>
          <h1 className="mt-5 font-display text-4xl font-semibold leading-[1.08] tracking-tight text-ink sm:text-5xl lg:text-6xl">
            Echo reports go in as PDFs.
            <span className="block text-deep">Data comes out as a table.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
            {SITE.description}
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-4">
            <a
              href="#tool"
              className="rounded bg-deep px-6 py-3 text-base font-medium text-white hover:opacity-90"
            >
              Launch EchoMiner
            </a>
            <a href="#workflow" className="text-base text-muted underline underline-offset-4 hover:text-deep">
              See how it works
            </a>
          </div>
          <dl className="mt-12 grid max-w-lg grid-cols-3 gap-6 border-t border-line pt-6">
            {[
              ["20", "PDFs per batch"],
              ["47", "fields per report"],
              ["0", "files kept after download"],
            ].map(([value, label]) => (
              <div key={label}>
                <dt className="sr-only">{label}</dt>
                <dd className="font-mono text-2xl font-medium text-deep">{value}</dd>
                <p className="mt-1 text-sm text-muted">{label}</p>
              </div>
            ))}
          </dl>
        </div>

        <div className="relative flex items-center">
          <div className="w-full rounded-lg border border-line bg-mist p-6">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
              Doppler study · spectral envelope
            </p>
            <svg viewBox="0 0 520 200" className="mt-4 w-full" role="img"
                 aria-label="Illustration of a Doppler waveform and the measurements extracted from it">
              <defs>
                <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--em-teal)" stopOpacity="0.28" />
                  <stop offset="100%" stopColor="var(--em-teal)" stopOpacity="0" />
                </linearGradient>
              </defs>
              <g stroke="var(--em-line)" strokeWidth="0.75">
                {[40, 80, 120, 160].map((y) => <line key={y} x1="0" y1={y} x2="520" y2={y} />)}
              </g>
              <path
                d="M0 168 L40 168 C70 168 74 40 104 40 C134 40 138 168 168 168 L200 168 C230 168 234 62 264 62 C294 62 298 168 328 168 L360 168 C390 168 394 28 424 28 C454 28 458 168 488 168 L520 168 Z"
                fill="url(#fade)"
              />
              <path
                d="M0 168 L40 168 C70 168 74 40 104 40 C134 40 138 168 168 168 L200 168 C230 168 234 62 264 62 C294 62 298 168 328 168 L360 168 C390 168 394 28 424 28 C454 28 458 168 488 168 L520 168"
                fill="none"
                stroke="var(--em-teal)"
                strokeWidth="2"
                className={reduced ? undefined : "trace-draw"}
              />
            </svg>
            <div className="mt-6 grid grid-cols-2 gap-x-8 gap-y-2 border-t border-line pt-4 sm:grid-cols-3">
              {[
                ["EF", "61 %"], ["FS", "34 %"], ["LVIDd", "48 mm"],
                ["LA", "38 mm"], ["EDV", "108 ml"], ["MV", "E0.8 A0.6"],
              ].map(([key, value], index) => (
                <motion.div
                  key={key}
                  initial={reduced ? false : { opacity: 0 }}
                  animate={reduced ? undefined : { opacity: 1 }}
                  transition={{ delay: 1.6 + index * 0.09, duration: 0.35 }}
                  className="flex items-baseline justify-between gap-3"
                >
                  <span className="font-mono text-[11px] uppercase tracking-wider text-muted">{key}</span>
                  <span className="font-mono text-sm text-ink">{value}</span>
                </motion.div>
              ))}
            </div>
            <p className="mt-4 font-mono text-[10px] text-muted">
              Illustrative values. Not from a patient record.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
