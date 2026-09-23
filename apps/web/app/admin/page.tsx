"use client";

import { useCallback, useEffect, useState } from "react";
import {
  adminApi, type ContentRow, type GeoPayload, type HealthPayload, type OtpEntry,
  type UsagePayload, type UserRow,
} from "@/lib/admin";
import { BarList, TimeseriesChart } from "@/components/charts";

type Tab = "overview" | "users" | "otp" | "content";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "users", label: "Registered users" },
  { key: "otp", label: "Verification log" },
  { key: "content", label: "News, publications & FAQ" },
];

function Panel({ title, children, actions }: {
  title: string; children: React.ReactNode; actions?: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-line bg-paper p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-base font-semibold text-deep">{title}</h2>
        {actions}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function LoginCard({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adminApi.login(email, password, totp);
      onSignedIn();
    } catch {
      // Deliberately uniform: never reveal which factor failed.
      setError("Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-24 w-full max-w-sm rounded-lg border border-line bg-paper p-8">
      <h1 className="font-display text-xl font-semibold text-deep">EchoMiner administration</h1>
      <form onSubmit={submit} className="mt-6 space-y-4">
        {[
          { label: "Email", value: email, set: setEmail, type: "email", autoComplete: "username" },
          { label: "Password", value: password, set: setPassword, type: "password", autoComplete: "current-password" },
          { label: "Authenticator code", value: totp, set: setTotp, type: "text", autoComplete: "one-time-code" },
        ].map((field) => (
          <label key={field.label} className="block">
            <span className="text-sm font-medium text-ink">{field.label}</span>
            <input
              type={field.type}
              autoComplete={field.autoComplete}
              required={field.label !== "Authenticator code"}
              value={field.value}
              onChange={(event) => field.set(event.target.value)}
              className="mt-1.5 w-full rounded border border-line bg-paper px-3 py-2 text-sm text-ink"
            />
          </label>
        ))}
        <button type="submit" disabled={busy}
                className="w-full rounded bg-deep px-4 py-2.5 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "Checking…" : "Sign in"}
        </button>
        {error && <p role="alert" className="text-sm text-alert">{error}</p>}
      </form>
    </div>
  );
}

function Overview() {
  const [usage, setUsage] = useState<UsagePayload | null>(null);
  const [geo, setGeo] = useState<GeoPayload | null>(null);
  const [projects, setProjects] = useState<{ project: string; count: number }[]>([]);
  const [health, setHealth] = useState<HealthPayload | null>(null);

  useEffect(() => {
    adminApi.usage().then(setUsage).catch(() => undefined);
    adminApi.geo().then(setGeo).catch(() => undefined);
    adminApi.projects().then(setProjects).catch(() => undefined);
    adminApi.health().then(setHealth).catch(() => undefined);
  }, []);

  return (
    <div className="space-y-6">
      <Panel title="Platform health">
        {health ? (
          <div className="grid gap-4 sm:grid-cols-4">
            {[
              ["Queue depth", health.queue_depth],
              ["Running", health.running],
              ["Purge backlog", health.purge_backlog],
              ["Failed jobs", health.failed_jobs],
            ].map(([label, value]) => (
              <div key={String(label)}>
                <div className="font-mono text-2xl text-deep">{String(value)}</div>
                <div className="mt-1 text-sm text-muted">{label}</div>
              </div>
            ))}
            {health.purge_backlog > 0 && (
              <p role="alert" className="sm:col-span-4 text-sm text-alert">
                Artefacts are past their retention window. Check that the worker is running —
                uploaded reports should not outlive their job.
              </p>
            )}
          </div>
        ) : <p className="text-sm text-muted">Loading…</p>}
      </Panel>

      <Panel title="Usage">
        {usage ? (
          <>
            <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {[
                ["Users", usage.summary.users_total], ["Verified", usage.summary.users_active],
                ["Jobs", usage.summary.jobs_total], ["Files", usage.summary.files_total],
                ["Records", usage.summary.records_total], ["Downloads", usage.summary.downloads_total],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <div className="font-mono text-2xl text-deep">{String(value)}</div>
                  <div className="mt-1 text-sm text-muted">{label}</div>
                </div>
              ))}
            </div>
            <div className="mt-8">
              <TimeseriesChart
                data={usage.timeseries}
                series={[
                  { key: "registrations", label: "Registrations", colour: "var(--em-deep)" },
                  { key: "jobs", label: "Jobs", colour: "var(--em-teal)" },
                  { key: "downloads", label: "Downloads", colour: "var(--em-alert)" },
                ]}
              />
            </div>
          </>
        ) : <p className="text-sm text-muted">Loading…</p>}
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Users by state">
          <BarList data={geo?.states ?? []} labelKey="state" />
        </Panel>
        <Panel title="Users by country">
          <BarList data={geo?.countries ?? []} labelKey="country" />
        </Panel>
      </div>

      <Panel title="Projects">
        <BarList data={projects} labelKey="project" max={15} />
      </Panel>
    </div>
  );
}

function Users() {
  const [rows, setRows] = useState<UserRow[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<UserRow | null>(null);

  const load = useCallback(async () => {
    const page = await adminApi.users(search ? { search } : {});
    setRows(page.items);
    setTotal(page.total);
  }, [search]);

  useEffect(() => {
    const timer = window.setTimeout(load, 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function toggle(user: UserRow) {
    await adminApi.setStatus(user.id, user.status === "disabled" ? "active" : "disabled");
    load();
  }

  return (
    <Panel
      title={`Registered users (${total})`}
      actions={
        <a href="/api/v1/admin/users.csv"
           className="rounded border border-line px-3 py-1.5 text-sm text-deep hover:bg-mist">
          Export CSV
        </a>
      }
    >
      <label className="block max-w-sm">
        <span className="sr-only">Search users</span>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search name, email, institute…"
          className="w-full rounded border border-line bg-paper px-3 py-2 text-sm text-ink"
        />
      </label>

      <div className="mt-5 overflow-x-auto rounded border border-line">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-deep text-white">
            <tr>
              {["Name", "Email", "Institute", "State", "Country", "Status", ""].map((head) => (
                <th key={head} scope="col" className="px-3 py-2 font-mono text-[11px] uppercase tracking-wider">
                  {head}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((user) => (
              <tr key={user.id} className="border-t border-line odd:bg-mist">
                <td className="px-3 py-2">
                  <button type="button" onClick={() => setSelected(user)}
                          className="text-deep underline underline-offset-4">
                    {user.full_name}
                  </button>
                </td>
                <td className="px-3 py-2 font-mono text-xs">{user.email}</td>
                <td className="px-3 py-2">{user.institute}</td>
                <td className="px-3 py-2">{user.state ?? "—"}</td>
                <td className="px-3 py-2 font-mono text-xs">{user.country_iso2}</td>
                <td className="px-3 py-2 font-mono text-xs">{user.status}</td>
                <td className="px-3 py-2 text-right">
                  <button type="button" onClick={() => toggle(user)}
                          className="text-xs text-muted underline underline-offset-4">
                    {user.status === "disabled" ? "Enable" : "Disable"}
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-muted">No users match.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="mt-5 rounded border border-line bg-mist p-5">
          <div className="flex items-start justify-between gap-4">
            <h3 className="font-display text-base font-semibold text-deep">{selected.full_name}</h3>
            <button type="button" onClick={() => setSelected(null)} className="text-sm text-muted">Close</button>
          </div>
          <dl className="mt-4 grid gap-x-8 gap-y-2 sm:grid-cols-2">
            {[
              ["Designation", selected.designation], ["Affiliation", selected.affiliation],
              ["Institute", selected.institute], ["Taluk", selected.taluk],
              ["District", selected.district], ["State", selected.state],
              ["Country", selected.country_iso2], ["Phone", selected.phone_e164],
              ["Project", selected.project_title], ["Registered", selected.created_at],
              ["Verified", selected.email_verified_at],
            ].map(([label, value]) => (
              <div key={String(label)} className="flex gap-3 text-sm">
                <dt className="w-28 shrink-0 text-muted">{label}</dt>
                <dd className="text-ink">{value || "—"}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-sm"><span className="text-muted">Description: </span>{selected.project_description}</p>
          <p className="mt-2 text-sm"><span className="text-muted">Purpose: </span>{selected.purpose}</p>
        </div>
      )}
    </Panel>
  );
}

function OtpLog() {
  const [rows, setRows] = useState<OtpEntry[]>([]);
  useEffect(() => { adminApi.otpLogs().then(setRows).catch(() => undefined); }, []);
  return (
    <Panel title="Verification log">
      <p className="mb-4 text-sm text-muted">
        Delivery and verification outcomes. Codes are stored only as hashes and are never displayed.
      </p>
      <div className="overflow-x-auto rounded border border-line">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-deep text-white">
            <tr>
              {["Email", "Purpose", "Attempts", "Verified", "Locked", "Issued"].map((head) => (
                <th key={head} scope="col" className="px-3 py-2 font-mono text-[11px] uppercase tracking-wider">{head}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.email}-${index}`} className="border-t border-line odd:bg-mist">
                <td className="px-3 py-2 font-mono text-xs">{row.email}</td>
                <td className="px-3 py-2">{row.purpose}</td>
                <td className="px-3 py-2 font-mono text-xs">{row.attempts}</td>
                <td className="px-3 py-2">{row.verified ? "yes" : "no"}</td>
                <td className={`px-3 py-2 ${row.locked ? "text-alert" : ""}`}>{row.locked ? "locked" : "—"}</td>
                <td className="px-3 py-2 font-mono text-xs">{row.created_at?.slice(0, 19) ?? "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-6 text-center text-muted">Nothing logged yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

const KINDS = [
  { key: "news", label: "News" },
  { key: "publication", label: "Publications" },
  { key: "faq", label: "FAQ" },
];

function Content() {
  const [kind, setKind] = useState("news");
  const [rows, setRows] = useState<ContentRow[]>([]);
  const [draft, setDraft] = useState({ slug: "", title: "", body_md: "", link_url: "", published: false });

  const load = useCallback(() => {
    adminApi.content(kind).then(setRows).catch(() => setRows([]));
  }, [kind]);
  useEffect(load, [load]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    await adminApi.saveContent({ kind, ...draft, link_url: draft.link_url || null });
    setDraft({ slug: "", title: "", body_md: "", link_url: "", published: false });
    load();
  }

  return (
    <Panel title="Site content">
      <div className="flex gap-2">
        {KINDS.map((option) => (
          <button
            key={option.key}
            type="button"
            onClick={() => setKind(option.key)}
            className={`rounded px-3 py-1.5 font-mono text-xs uppercase tracking-wider ${
              kind === option.key ? "bg-deep text-white" : "border border-line text-muted"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <ul className="mt-5 divide-y divide-line rounded border border-line">
        {rows.map((row) => (
          <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 p-3">
            <div>
              <p className="text-sm font-medium text-ink">{row.title}</p>
              <p className="font-mono text-[11px] text-muted">
                {row.slug} · {row.published_at ? "published" : "draft"}
              </p>
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={async () => {
                  await adminApi.saveContent({
                    kind, item_id: row.id, slug: row.slug, title: row.title,
                    body_md: row.body_md, link_url: row.link_url,
                    published: !row.published_at, sort_order: row.sort_order,
                  });
                  load();
                }}
                className="text-xs text-deep underline underline-offset-4"
              >
                {row.published_at ? "Unpublish" : "Publish"}
              </button>
              <button
                type="button"
                onClick={async () => { await adminApi.deleteContent(row.id); load(); }}
                className="text-xs text-alert underline underline-offset-4"
              >
                Delete
              </button>
            </div>
          </li>
        ))}
        {rows.length === 0 && <li className="p-4 text-sm text-muted">Nothing here yet.</li>}
      </ul>

      <form onSubmit={save} className="mt-6 space-y-3 rounded border border-line bg-mist p-4">
        <h3 className="font-display text-sm font-semibold text-deep">Add an entry</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <input required placeholder="slug" value={draft.slug}
                 onChange={(e) => setDraft({ ...draft, slug: e.target.value })}
                 className="rounded border border-line bg-paper px-3 py-2 text-sm" />
          <input required placeholder="title" value={draft.title}
                 onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                 className="rounded border border-line bg-paper px-3 py-2 text-sm" />
        </div>
        <textarea rows={3} placeholder={kind === "faq" ? "answer" : "body (markdown)"}
                  value={draft.body_md}
                  onChange={(e) => setDraft({ ...draft, body_md: e.target.value })}
                  className="w-full rounded border border-line bg-paper px-3 py-2 text-sm" />
        <input placeholder="link (optional)" value={draft.link_url}
               onChange={(e) => setDraft({ ...draft, link_url: e.target.value })}
               className="w-full rounded border border-line bg-paper px-3 py-2 text-sm" />
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" checked={draft.published}
                 onChange={(e) => setDraft({ ...draft, published: e.target.checked })} />
          Publish immediately
        </label>
        <button type="submit" className="rounded bg-deep px-4 py-2 text-sm font-medium text-white">
          Save
        </button>
      </form>
    </Panel>
  );
}

export default function AdminPage() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    adminApi.me().then(() => setAuthed(true)).catch(() => setAuthed(false));
  }, []);

  if (authed === null) return <p className="p-10 text-sm text-muted">Loading…</p>;
  if (!authed) return <LoginCard onSignedIn={() => setAuthed(true)} />;

  return (
    <div className="mx-auto w-full max-w-content px-6 py-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-display text-2xl font-semibold text-deep">EchoMiner administration</h1>
        <button
          type="button"
          onClick={async () => { await adminApi.signOut().catch(() => undefined); setAuthed(false); }}
          className="font-mono text-xs text-muted underline underline-offset-4"
        >
          Sign out
        </button>
      </header>

      <nav aria-label="Admin sections" className="mt-6 flex flex-wrap gap-2">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            aria-current={tab === item.key ? "page" : undefined}
            className={`rounded px-3 py-1.5 text-sm ${
              tab === item.key ? "bg-deep text-white" : "border border-line text-muted hover:text-deep"
            }`}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="mt-8">
        {tab === "overview" && <Overview />}
        {tab === "users" && <Users />}
        {tab === "otp" && <OtpLog />}
        {tab === "content" && <Content />}
      </div>
    </div>
  );
}
