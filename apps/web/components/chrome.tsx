"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { SITE } from "@/lib/site";

const NAV = [
  { href: "#about", label: "About" },
  { href: "#workflow", label: "How it works" },
  { href: "#project", label: "DBT Project" },
  { href: "#cite", label: "Cite" },
  { href: "#faq", label: "FAQ" },
  { href: "#contact", label: "Contact" },
];

function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem("em-theme");
    const prefers = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const next = stored ? stored === "dark" : prefers;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    window.localStorage.setItem("em-theme", next ? "dark" : "light");
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded border border-line px-2 py-1 font-mono text-xs text-muted hover:text-deep"
      aria-pressed={dark}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
    >
      {dark ? "LIGHT" : "DARK"}
    </button>
  );
}

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-content items-center gap-6 px-6">
        <a href="#top" className="font-display text-lg font-semibold tracking-tight text-deep">
          {SITE.name}
        </a>
        <nav aria-label="Primary" className="hidden flex-1 items-center gap-6 md:flex">
          {NAV.map((item) => (
            <a key={item.href} href={item.href} className="text-sm text-muted hover:text-deep">
              {item.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <ThemeToggle />
          <a
            href="#tool"
            className="rounded bg-deep px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            Launch EchoMiner
          </a>
        </div>
      </div>
    </header>
  );
}

/** Institutional marks. Files ship in /public/brand; usage follows institutional
 *  branding guidelines. */
export function BrandLockup({ height = 44 }: { height?: number }) {
  return (
    <div className="flex items-center gap-8">
      <Image
        src="/brand/jss-aher-480w.png"
        alt="JSS Academy of Higher Education and Research"
        width={480}
        height={204}
        style={{ height, width: "auto" }}
        className="dark:brightness-0 dark:invert"
      />
      <Image
        src="/brand/dbt-240w.png"
        alt="Department of Biotechnology, Government of India"
        width={240}
        height={238}
        style={{ height, width: "auto" }}
        className="dark:brightness-0 dark:invert"
      />
    </div>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-mist py-14">
      <div className="mx-auto w-full max-w-content px-6">
        <BrandLockup height={52} />
        <div className="mt-8 grid gap-8 sm:grid-cols-3">
          <div>
            <p className="font-display text-lg font-semibold text-deep">{SITE.name}</p>
            <p className="mt-2 text-sm text-muted">{SITE.tagline}</p>
          </div>
          <div className="text-sm text-muted">
            <p className="font-medium text-ink">Department of Community Medicine</p>
            <p className="mt-1">JSS Medical College, JSS AHER</p>
            <p>Mysore, Karnataka, India</p>
          </div>
          <div className="text-sm text-muted">
            <a href="#cite" className="block hover:text-deep">How to cite</a>
            <a href="#privacy" className="block hover:text-deep">Privacy notice</a>
            <a href="#faq" className="block hover:text-deep">FAQ</a>
          </div>
        </div>
        <p className="mt-10 border-t border-line pt-6 font-mono text-xs text-muted">
          © {new Date().getFullYear()} JSS Academy of Higher Education and Research, Mysore.
          Developed under the DBT-BUILDER Project, Group 3 — Spatial Health Informatics and Management.
        </p>
      </div>
    </footer>
  );
}
