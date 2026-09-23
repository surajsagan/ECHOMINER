/**
 * reCAPTCHA v3 (invisible, score-based). The site key is inlined at build time.
 * Without a key (local development) a placeholder token is returned, which the
 * backend's null captcha adapter accepts; production runs the real verifier.
 */
const SITE_KEY = process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY ?? "";

type Grecaptcha = {
  ready: (cb: () => void) => void;
  execute: (key: string, opts: { action: string }) => Promise<string>;
};

let loader: Promise<Grecaptcha> | null = null;

function load(): Promise<Grecaptcha> {
  if (loader) return loader;
  loader = new Promise<Grecaptcha>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(SITE_KEY)}`;
    script.async = true;
    script.onload = () => {
      const g = (window as unknown as { grecaptcha?: Grecaptcha }).grecaptcha;
      if (!g) return reject(new Error("reCAPTCHA failed to initialise"));
      g.ready(() => resolve(g));
    };
    script.onerror = () => {
      loader = null;
      reject(new Error("reCAPTCHA could not be loaded. Check your connection or disable content blockers."));
    };
    document.head.appendChild(script);
  });
  return loader;
}

/** Preload on first interaction so the token call is fast at submit time. */
export function preloadCaptcha(): void {
  if (SITE_KEY && typeof window !== "undefined") load().catch(() => undefined);
}

export async function captchaToken(action: "register" | "resend"): Promise<string> {
  if (!SITE_KEY) return "dev-no-captcha";
  const g = await load();
  return g.execute(SITE_KEY, { action });
}
