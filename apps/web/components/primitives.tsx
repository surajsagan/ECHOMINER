"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

export function Section({
  id,
  eyebrow,
  title,
  lead,
  children,
  tone = "paper",
}: {
  id: string;
  eyebrow?: string;
  title?: string;
  lead?: string;
  children?: ReactNode;
  tone?: "paper" | "mist";
}) {
  return (
    <section
      id={id}
      className={`section py-20 sm:py-24 ${tone === "mist" ? "bg-mist" : "bg-paper"}`}
      aria-labelledby={title ? `${id}-heading` : undefined}
    >
      <div className="mx-auto w-full max-w-content px-6">
        {eyebrow && (
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-teal">{eyebrow}</p>
        )}
        {title && (
          <h2
            id={`${id}-heading`}
            className="mt-3 font-display text-3xl font-semibold tracking-tight text-deep sm:text-4xl"
          >
            {title}
          </h2>
        )}
        {lead && <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted">{lead}</p>}
        {children && <div className="mt-10">{children}</div>}
      </div>
    </section>
  );
}

/** The signature motif, quietened: a Doppler envelope used as the section rule. */
export function TraceDivider({ label }: { label?: string }) {
  return (
    <div className="mx-auto w-full max-w-content px-6" aria-hidden="true">
      <div className="flex items-center gap-4">
        <svg viewBox="0 0 600 24" className="h-6 flex-1" role="presentation">
          <path
            d="M0 20 L60 20 C80 20 86 4 100 4 C114 4 120 20 140 20 L200 20 C220 20 226 8 240 8 C254 8 260 20 280 20 L340 20 C360 20 366 2 380 2 C394 2 400 20 420 20 L600 20"
            fill="none"
            stroke="var(--em-teal)"
            strokeWidth="1.25"
            opacity="0.55"
          />
        </svg>
        {label && (
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted">{label}</span>
        )}
      </div>
    </div>
  );
}

export function Reveal({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  const reduced = useReducedMotion();
  if (reduced) return <>{children}</>;
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-line bg-paper p-6 ${className}`}>{children}</div>
  );
}

export function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-mono text-2xl font-medium text-deep">{value}</div>
      <div className="mt-1 text-sm text-muted">{label}</div>
    </div>
  );
}
