"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { api, ApiError, type JobState, type PreviewPage } from "@/lib/api";
import { AGREEMENT_TEXT, LIMITS, PRIVACY_NOTICE } from "@/lib/site";
import { captchaToken, preloadCaptcha } from "@/lib/captcha";
import { Card, Section } from "./primitives";

const MAX_FILES = LIMITS.maxFiles;
const MAX_BYTES = LIMITS.maxMb * 1024 * 1024;

type Stage = "form" | "signin" | "otp" | "unlocked";

/* ------------------------------------------------------------------ form -- */

const FIELDS = [
  { name: "full_name", label: "Name", required: true },
  { name: "designation", label: "Designation", required: true },
  { name: "affiliation", label: "Affiliation", required: true },
  { name: "institute", label: "Institute", required: true },
  { name: "taluk", label: "Taluk", required: false },
  { name: "district", label: "District", required: false },
  { name: "state", label: "State", required: false },
  { name: "country_iso2", label: "Country code (ISO-2)", required: true, maxLength: 2 },
  { name: "email", label: "Email", required: true, type: "email" },
  { name: "phone_e164", label: "Phone (optional)", required: false, type: "tel" },
  { name: "project_title", label: "Project title", required: true },
] as const;

function Field({
  name, label, required, type = "text", maxLength, value, onChange,
}: {
  name: string; label: string; required: boolean; type?: string; maxLength?: number;
  value: string; onChange: (name: string, value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink">
        {label} {required && <span className="text-alert" aria-hidden>*</span>}
      </span>
      <input
        name={name}
        type={type}
        required={required}
        maxLength={maxLength}
        value={value}
        onChange={(event) => onChange(name, event.target.value)}
        className="mt-1.5 w-full rounded border border-line bg-paper px-3 py-2 text-sm text-ink"
      />
    </label>
  );
}

function AgreementModal({ onAccept, onClose }: { onAccept: () => void; onClose: () => void }) {
  const [reachedEnd, setReachedEnd] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  function handleScroll() {
    const el = bodyRef.current;
    if (el && el.scrollTop + el.clientHeight >= el.scrollHeight - 8) setReachedEnd(true);
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="agreement-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="max-h-[85vh] w-full max-w-2xl overflow-hidden rounded-lg border border-line bg-paper">
        <div className="border-b border-line p-6">
          <h3 id="agreement-title" className="font-display text-lg font-semibold text-deep">
            Copyright and usage agreement
          </h3>
        </div>
        <div
          ref={bodyRef}
          onScroll={handleScroll}
          className="max-h-[45vh] overflow-y-auto p-6 text-sm leading-relaxed text-muted"
        >
          <pre className="whitespace-pre-wrap font-body">{AGREEMENT_TEXT}</pre>
          <p className="mt-6 border-t border-line pt-4">{PRIVACY_NOTICE}</p>
        </div>
        <div className="flex items-center justify-between gap-4 border-t border-line p-6">
          <p className="text-xs text-muted">
            {reachedEnd ? "You have read the full agreement." : "Scroll to the end to continue."}
          </p>
          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="rounded border border-line px-4 py-2 text-sm text-muted">
              Cancel
            </button>
            <button
              type="button"
              disabled={!reachedEnd}
              onClick={onAccept}
              className="rounded bg-deep px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            >
              I accept
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- workspace -- */

function useJobPolling(jobId: string | null) {
  const [job, setJob] = useState<JobState | null>(null);

  useEffect(() => {
    if (!jobId) return;
    const TERMINAL = ["completed", "partial", "failed", "purged"];
    let cancelled = false;
    let timer: number | undefined;
    const source = new EventSource(`/api/v1/jobs/${jobId}/events`, { withCredentials: true });

    source.onmessage = (event) => {
      if (cancelled) return;
      const state = JSON.parse(event.data) as JobState;
      setJob(state);
      if (TERMINAL.includes(state.status)) {
        cancelled = true;
        source.close();
      }
    };

    // If the stream cannot be held open (proxy, laptop sleep, flaky link), fall
    // back to polling rather than leaving the user watching a frozen bar.
    source.onerror = () => {
      source.close();
      if (cancelled || timer !== undefined) return;
      timer = window.setInterval(async () => {
        try {
          const state = await api.job(jobId);
          if (cancelled) return;
          setJob(state);
          if (TERMINAL.includes(state.status)) window.clearInterval(timer);
        } catch {
          window.clearInterval(timer);
        }
      }, 2000);
    };

    return () => {
      cancelled = true;
      source.close();
      if (timer !== undefined) window.clearInterval(timer);
    };
  }, [jobId]);

  return [job, setJob] as const;
}

function PreviewTable({ page }: { page: PreviewPage }) {
  return (
    <div className="mt-6 overflow-x-auto rounded border border-line">
      <table className="min-w-full border-collapse text-left">
        <caption className="sr-only">Preview of extracted echocardiography records</caption>
        <thead>
          <tr className="bg-deep text-white">
            {page.columns.map((column) => (
              <th key={column} scope="col" className="whitespace-nowrap px-3 py-2 font-mono text-[11px] uppercase tracking-wider">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {page.rows.map((row, index) => (
            <tr key={index} className="border-t border-line odd:bg-mist">
              {page.columns.map((column) => (
                <td key={column} className="whitespace-nowrap px-3 py-2 font-mono text-xs text-ink">
                  {row[column] || <span className="text-muted">—</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Workspace({ onSignOut }: { onSignOut: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useJobPolling(jobId);
  const [page, setPage] = useState<PreviewPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  const terminal = job && ["completed", "partial"].includes(job.status);

  useEffect(() => {
    if (!jobId || !terminal || page) return;
    api.preview(jobId, 25).then(setPage).catch(() => undefined);
  }, [jobId, terminal, page]);

  const accept = useCallback((incoming: FileList | null) => {
    if (!incoming) return;
    const chosen = Array.from(incoming).filter((file) => file.name.toLowerCase().endsWith(".pdf"));
    if (chosen.length !== incoming.length) setError("Only PDF files are accepted.");
    const combined = [...files, ...chosen].slice(0, MAX_FILES);
    if (files.length + chosen.length > MAX_FILES) {
      setError(`A maximum of ${MAX_FILES} files can be uploaded at once.`);
    }
    if (combined.reduce((sum, f) => sum + f.size, 0) > MAX_BYTES) {
      setError(`Total upload exceeds ${LIMITS.maxMb} MB.`);
      return;
    }
    setFiles(combined);
  }, [files]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const created = await api.submitJob(files);
      setJobId(created.id);
      setPage(null);
      setDownloaded(false);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    if (jobId && !downloaded) await api.discard(jobId).catch(() => undefined);
    setFiles([]); setJobId(null); setJob(null); setPage(null); setDownloaded(false);
  }

  const progress = job
    ? Math.round((job.files.filter((f) => f.status !== "queued").length / Math.max(job.file_count, 1)) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-xl font-semibold text-deep">Extract from reports</h3>
        <button type="button" onClick={onSignOut} className="font-mono text-xs text-muted underline underline-offset-4">
          Sign out
        </button>
      </div>

      <Card>
        <h4 className="font-display text-base font-medium text-ink">Before you upload</h4>
        <ul className="mt-3 space-y-1.5 text-sm text-muted">
          <li>PDF reports only, up to {MAX_FILES} files and {LIMITS.maxMb} MB per submission.</li>
          <li>The PDF must contain a text layer. Scanned images without OCR cannot be read.</li>
          <li>Your files are deleted from the server as soon as your download completes.</li>
        </ul>
      </Card>

      {!jobId && (
        <div>
          <label
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); accept(e.dataTransfer.files); }}
            className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-line bg-mist p-10 text-center hover:border-teal"
          >
            <span className="font-display text-base font-medium text-deep">
              Drop PDF reports here, or choose files
            </span>
            <span className="mt-1 text-sm text-muted">Up to {MAX_FILES} files</span>
            <input
              type="file"
              accept="application/pdf,.pdf"
              multiple
              className="sr-only"
              onChange={(event) => accept(event.target.files)}
            />
          </label>

          {files.length > 0 && (
            <ul className="mt-4 divide-y divide-line rounded border border-line">
              {files.map((file, index) => (
                <li key={`${file.name}-${index}`} className="flex items-center justify-between gap-4 px-4 py-2">
                  <span className="truncate font-mono text-xs text-ink">{file.name}</span>
                  <span className="shrink-0 font-mono text-[11px] text-muted">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </span>
                </li>
              ))}
            </ul>
          )}

          <button
            type="button"
            disabled={!files.length || busy}
            onClick={submit}
            className="mt-4 rounded bg-deep px-6 py-3 text-sm font-medium text-white disabled:opacity-40"
          >
            {busy ? "Uploading…" : `Extract ${files.length || ""} file${files.length === 1 ? "" : "s"}`}
          </button>
        </div>
      )}

      {job && (
        <Card>
          <div className="flex items-center justify-between gap-4">
            <p className="font-mono text-xs uppercase tracking-wider text-teal">{job.status}</p>
            <p className="font-mono text-xs text-muted">
              {job.record_count} record{job.record_count === 1 ? "" : "s"}
            </p>
          </div>
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded bg-mist" role="progressbar"
               aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}
               aria-label="Extraction progress">
            <div className="h-full bg-teal transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p aria-live="polite" className="sr-only">
            Extraction {job.status}, {job.record_count} records.
          </p>

          <ul className="mt-4 divide-y divide-line text-sm">
            {job.files.map((file) => (
              <li key={file.filename} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2">
                <span className="truncate font-mono text-xs text-ink">{file.filename}</span>
                <span className="font-mono text-[11px] text-muted">{file.status}</span>
                {file.record_count > 0 && (
                  <span className="font-mono text-[11px] text-muted">{file.record_count} rows</span>
                )}
                {file.warnings && <span className="w-full text-xs text-alert">{file.warnings}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {page && page.rows.length > 0 && (
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-teal">
            Preview · {page.rows.length} of {page.total} rows
          </p>
          <PreviewTable page={page} />
        </div>
      )}

      {terminal && jobId && (
        <div className="flex flex-wrap items-center gap-4">
          <a
            href={api.exportUrl(jobId)}
            onClick={() => setDownloaded(true)}
            className="rounded bg-teal px-6 py-3 text-sm font-medium text-white hover:opacity-90"
          >
            Download Excel workbook
          </a>
          <button type="button" onClick={reset} className="text-sm text-muted underline underline-offset-4">
            Start another batch
          </button>
          {downloaded && (
            <span className="font-mono text-xs text-muted">
              Files removed from the server.
            </span>
          )}
        </div>
      )}

      {error && <p role="alert" className="text-sm text-alert">{error}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ gate -- */

export function ToolSection() {
  const reduced = useReducedMotion();
  const [stage, setStage] = useState<Stage>("form");
  const [values, setValues] = useState<Record<string, string>>({
    country_iso2: "IN", project_description: "", purpose: "",
  });
  const [accepted, setAccepted] = useState(false);
  const [showAgreement, setShowAgreement] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resendIn, setResendIn] = useState(60);

  // A returning visitor on a known device is restored silently: no OTP.
  useEffect(() => {
    api.restore().then(() => setStage("unlocked")).catch(() => undefined);
  }, []);

  function set(name: string, value: string) {
    setValues((previous) => ({ ...previous, [name]: value }));
  }

  async function submitRegistration(event: React.FormEvent) {
    event.preventDefault();
    if (!accepted) {
      setError("You must accept the copyright and usage agreement.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.register({
        full_name: values.full_name ?? "", designation: values.designation ?? "",
        affiliation: values.affiliation ?? "", institute: values.institute ?? "",
        taluk: values.taluk, district: values.district, state: values.state,
        country_iso2: (values.country_iso2 ?? "IN").toUpperCase(),
        email: values.email ?? "", phone_e164: values.phone_e164 || undefined,
        project_title: values.project_title ?? "",
        project_description: values.project_description ?? "",
        purpose: values.purpose ?? "",
        agreement_accepted: true, agreement_text: AGREEMENT_TEXT,
        captcha_token: await captchaToken("register"),
      });
      setStage("otp");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Registration failed.");
    } finally {
      setBusy(false);
    }
  }

  async function resendCode() {
    setBusy(true);
    setError(null);
    try {
      await api.resendOtp(values.email ?? "", await captchaToken("resend"));
      setResendIn(60);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not resend the code.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = setTimeout(() => setResendIn((n) => n - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendIn]);

  async function submitSignIn(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.resendOtp(values.email ?? "", await captchaToken("resend"));
      setResendIn(60);
      setStage("otp");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Could not send a sign-in code.");
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.verifyOtp(values.email ?? "", code);
      setStage("unlocked");
    } catch {
      setError("That code is not valid or has expired.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section
      id="tool"
      tone="mist"
      eyebrow="Access"
      title="Launch EchoMiner"
      lead="Register once, verify your email, and the tool opens right here on this page."
    >
      {showAgreement && (
        <AgreementModal
          onAccept={() => { setAccepted(true); setShowAgreement(false); }}
          onClose={() => setShowAgreement(false)}
        />
      )}

      <AnimatePresence mode="wait">
        {stage === "form" && (
          <motion.div
            key="form"
            initial={reduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduced ? undefined : { opacity: 0 }}
          >
            <p className="mb-4 text-sm text-muted">
              Already registered?{" "}
              <button
                type="button"
                onClick={() => { setError(null); setStage("signin"); }}
                className="font-medium text-deep underline underline-offset-4"
              >
                Sign in with your email
              </button>
            </p>
            <Card>
              <form onSubmit={submitRegistration} onFocus={preloadCaptcha} className="space-y-6">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {FIELDS.map((field) => (
                    <Field
                      key={field.name}
                      {...field}
                      value={values[field.name] ?? ""}
                      onChange={set}
                    />
                  ))}
                </div>

                {(["project_description", "purpose"] as const).map((name) => (
                  <label key={name} className="block">
                    <span className="text-sm font-medium text-ink">
                      {name === "purpose" ? "Purpose of using EchoMiner" : "Project description"}{" "}
                      <span className="text-alert" aria-hidden>*</span>
                    </span>
                    <textarea
                      name={name}
                      required
                      rows={3}
                      value={values[name] ?? ""}
                      onChange={(event) => set(name, event.target.value)}
                      className="mt-1.5 w-full rounded border border-line bg-paper px-3 py-2 text-sm text-ink"
                    />
                  </label>
                ))}

                <div className="rounded border border-line bg-mist p-4">
                  <label className="flex items-start gap-3 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={accepted}
                      onChange={(event) => {
                        if (event.target.checked) setShowAgreement(true);
                        else setAccepted(false);
                      }}
                      className="mt-1"
                    />
                    <span>
                      I accept the{" "}
                      <button
                        type="button"
                        onClick={() => setShowAgreement(true)}
                        className="text-deep underline underline-offset-4"
                      >
                        copyright and usage agreement
                      </button>{" "}
                      and will acknowledge EchoMiner in any resulting publication.
                    </span>
                  </label>
                  <p className="mt-3 text-xs leading-relaxed text-muted">{PRIVACY_NOTICE}</p>
                </div>

                <p className="text-xs text-muted">
                  This form is protected by reCAPTCHA; the Google{" "}
                  <a className="underline" href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">Privacy Policy</a> and{" "}
                  <a className="underline" href="https://policies.google.com/terms" target="_blank" rel="noreferrer">Terms of Service</a> apply.
                </p>

                <button
                  type="submit"
                  disabled={busy}
                  className="rounded bg-deep px-6 py-3 text-sm font-medium text-white disabled:opacity-40"
                >
                  {busy ? "Sending code…" : "Register and send verification code"}
                </button>
                {error && <p role="alert" className="text-sm text-alert">{error}</p>}
              </form>
            </Card>
          </motion.div>
        )}

        {stage === "signin" && (
          <motion.div key="signin" initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }}>
            <Card className="max-w-lg">
              <h3 className="font-display text-lg font-semibold text-deep">Sign in</h3>
              <p className="mt-2 text-sm text-muted">
                Enter the email you registered with. If it is registered, a six-digit code will be sent to it.
              </p>
              <form onSubmit={submitSignIn} onFocus={preloadCaptcha} className="mt-5 space-y-4">
                <label className="block">
                  <span className="text-sm font-medium text-ink">Email</span>
                  <input
                    type="email"
                    required
                    autoComplete="email"
                    value={values.email ?? ""}
                    onChange={(event) => set("email", event.target.value)}
                    className="mt-1.5 w-full rounded border border-line bg-paper px-3 py-2 text-sm text-ink"
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded bg-deep px-6 py-3 text-sm font-medium text-white disabled:opacity-40"
                >
                  {busy ? "Sending…" : "Send sign-in code"}
                </button>
                <button
                  type="button"
                  onClick={() => { setError(null); setStage("form"); }}
                  className="ml-4 text-sm text-deep underline underline-offset-4"
                >
                  New user? Register
                </button>
                {error && <p role="alert" className="text-sm text-alert">{error}</p>}
              </form>
            </Card>
          </motion.div>
        )}

        {stage === "otp" && (
          <motion.div key="otp" initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }}>
            <Card className="max-w-lg">
              <h3 className="font-display text-lg font-semibold text-deep">Check your email</h3>
              <p className="mt-2 text-sm text-muted">
                A six-digit verification code was sent to{" "}
                <span className="font-mono text-ink">{values.email}</span>. It expires in 10 minutes.
              </p>
              <form onSubmit={submitCode} className="mt-5 space-y-4">
                <label className="block">
                  <span className="text-sm font-medium text-ink">Verification code</span>
                  <input
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    required
                    value={code}
                    onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
                    className="mt-1.5 w-40 rounded border border-line bg-paper px-3 py-2 text-center font-mono text-lg tracking-[0.4em] text-ink"
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy || code.length < 6}
                  className="rounded bg-deep px-6 py-3 text-sm font-medium text-white disabled:opacity-40"
                >
                  {busy ? "Verifying…" : "Verify and open EchoMiner"}
                </button>
                <button
                  type="button"
                  onClick={resendCode}
                  disabled={busy || resendIn > 0}
                  className="ml-4 text-sm text-deep underline underline-offset-4 disabled:no-underline disabled:opacity-50"
                >
                  {resendIn > 0 ? `Resend code in ${resendIn}s` : "Resend code"}
                </button>
                {error && <p role="alert" className="text-sm text-alert">{error}</p>}
              </form>
            </Card>
          </motion.div>
        )}

        {stage === "unlocked" && (
          <motion.div
            key="tool"
            initial={reduced ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <Workspace
              onSignOut={async () => {
                await api.signOut().catch(() => undefined);
                setStage("form");
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </Section>
  );
}
