"use client";

import { useState } from "react";

/**
 * Hand-drawn SVG charts rather than a charting library: the admin panel needs
 * three shapes, and a dependency would add more bundle than the whole page.
 * Each has a hover readout and a text alternative for screen readers.
 */

export function BarList({ data, labelKey, max }: {
  data: Record<string, string | number>[];
  labelKey: string;
  max?: number;
}) {
  const rows = data.slice(0, max ?? 10);
  const peak = Math.max(1, ...rows.map((row) => Number(row.count)));
  return (
    <ul className="space-y-2">
      {rows.map((row) => {
        const value = Number(row.count);
        return (
          <li key={String(row[labelKey])} className="grid grid-cols-[10rem_1fr_3rem] items-center gap-3">
            <span className="truncate text-sm text-ink" title={String(row[labelKey])}>
              {String(row[labelKey])}
            </span>
            <span className="h-2 overflow-hidden rounded bg-mist">
              <span
                className="block h-full rounded bg-teal"
                style={{ width: `${(value / peak) * 100}%` }}
              />
            </span>
            <span className="text-right font-mono text-xs text-muted">{value}</span>
          </li>
        );
      })}
      {rows.length === 0 && <li className="text-sm text-muted">No data yet.</li>}
    </ul>
  );
}

type Series = { key: string; label: string; colour: string };

export function TimeseriesChart({ data, series }: {
  data: Record<string, string | number>[];
  series: Series[];
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (data.length === 0) return <p className="text-sm text-muted">No activity in this window.</p>;

  const width = 640;
  const height = 180;
  const pad = { left: 32, right: 12, top: 12, bottom: 24 };
  const peak = Math.max(
    1,
    ...data.flatMap((row) => series.map((s) => Number(row[s.key] ?? 0))),
  );
  const stepX = (width - pad.left - pad.right) / Math.max(1, data.length - 1);
  const scaleY = (value: number) =>
    height - pad.bottom - (value / peak) * (height - pad.top - pad.bottom);

  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img"
           aria-label={`Activity over ${data.length} days`}>
        {[0, 0.5, 1].map((fraction) => {
          const y = scaleY(peak * fraction);
          return (
            <g key={fraction}>
              <line x1={pad.left} y1={y} x2={width - pad.right} y2={y}
                    stroke="var(--em-line)" strokeWidth="1" />
              <text x={4} y={y + 3} className="fill-[var(--em-muted)]" fontSize="9"
                    fontFamily="var(--font-mono)">
                {Math.round(peak * fraction)}
              </text>
            </g>
          );
        })}
        {series.map((s) => (
          <polyline
            key={s.key}
            fill="none"
            stroke={s.colour}
            strokeWidth="2"
            points={data
              .map((row, index) => `${pad.left + index * stepX},${scaleY(Number(row[s.key] ?? 0))}`)
              .join(" ")}
          />
        ))}
        {data.map((row, index) => (
          <rect
            key={String(row.day)}
            x={pad.left + index * stepX - stepX / 2}
            y={pad.top}
            width={Math.max(stepX, 6)}
            height={height - pad.top - pad.bottom}
            fill={hover === index ? "var(--em-mist)" : "transparent"}
            opacity="0.6"
            onMouseEnter={() => setHover(index)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </svg>
      <figcaption className="mt-2 flex flex-wrap items-center gap-4 font-mono text-[11px] text-muted">
        {series.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.colour }} />
            {s.label}
          </span>
        ))}
        {hover !== null && (
          <span className="text-ink">
            {String(data[hover].day)} ·{" "}
            {series.map((s) => `${s.label} ${data[hover][s.key] ?? 0}`).join(" · ")}
          </span>
        )}
      </figcaption>
    </figure>
  );
}
