# Next.js standalone output keeps the runtime image small.
FROM node:22-alpine AS builder
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web ./
# NEXT_PUBLIC_* values are inlined into the browser bundle at build time.
ARG NEXT_PUBLIC_RECAPTCHA_SITE_KEY=""
ARG NEXT_PUBLIC_GA_MEASUREMENT_ID=""
ENV NEXT_PUBLIC_RECAPTCHA_SITE_KEY=$NEXT_PUBLIC_RECAPTCHA_SITE_KEY \
    NEXT_PUBLIC_GA_MEASUREMENT_ID=$NEXT_PUBLIC_GA_MEASUREMENT_ID \
    NEXT_PUBLIC_API_BASE="" \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -g 10002 -S web && adduser -u 10002 -S web -G web
COPY --from=builder --chown=web:web /app/.next/standalone ./
COPY --from=builder --chown=web:web /app/.next/static ./.next/static
COPY --from=builder --chown=web:web /app/public ./public
USER web
EXPOSE 3000
CMD ["node", "server.js"]
