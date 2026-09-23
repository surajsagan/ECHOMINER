/** @type {import('next').NextConfig} */

// Two build targets:
//  * default ("standalone"): a Node server behind nginx (VM / docker-compose);
//  * NEXT_OUTPUT=export: plain static files served by the API itself
//    (single-service hosting, e.g. Render's free tier). Every page is static,
//    so nothing is lost; security headers then come from the API.
const staticExport = process.env.NEXT_OUTPUT === "export";

// Local development only: set API_PROXY=http://localhost:8000 so the browser
// talks to one origin (cookies are __Host- and same-site). In production nginx
// or the API itself serves /api, and this is unset.
const apiProxy = process.env.API_PROXY;

const nextConfig = staticExport
  ? {
      output: "export",
      trailingSlash: true,
      images: { unoptimized: true },
      reactStrictMode: true,
      poweredByHeader: false,
    }
  : {
      output: "standalone",
      reactStrictMode: true,
      poweredByHeader: false,
      async headers() {
        return [{
          source: "/:path*",
          headers: [
            { key: "X-Content-Type-Options", value: "nosniff" },
            { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          ],
        }];
      },
      async rewrites() {
        return apiProxy
          ? [
              { source: "/api/:path*", destination: `${apiProxy}/api/:path*` },
              { source: "/healthz", destination: `${apiProxy}/healthz` },
            ]
          : [];
      },
    };
export default nextConfig;
