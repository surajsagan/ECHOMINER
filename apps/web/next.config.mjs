/** @type {import('next').NextConfig} */

// Local development only: set API_PROXY=http://localhost:8000 so the browser
// talks to one origin (cookies are __Host- and same-site). In production nginx
// routes /api to the API container and this is unset.
const apiProxy = process.env.API_PROXY;

const nextConfig = {
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
