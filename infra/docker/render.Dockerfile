# Single-service image for hosts without a VM (Render free tier):
# the API serves the statically exported website and runs the extraction
# worker in-process. The VM deployment (docker-compose) is unaffected.

FROM node:22-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web ./
# Render passes service environment variables to the build as build args.
ARG NEXT_PUBLIC_RECAPTCHA_SITE_KEY=""
ARG NEXT_PUBLIC_GA_MEASUREMENT_ID=""
ARG NEXT_PUBLIC_MAX_FILES="5"
ARG NEXT_PUBLIC_MAX_UPLOAD_MB="50"
ARG NEXT_PUBLIC_MAX_PAGES="10000"
ENV NEXT_OUTPUT=export NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_BASE="" \
    NEXT_PUBLIC_RECAPTCHA_SITE_KEY=$NEXT_PUBLIC_RECAPTCHA_SITE_KEY \
    NEXT_PUBLIC_GA_MEASUREMENT_ID=$NEXT_PUBLIC_GA_MEASUREMENT_ID \
    NEXT_PUBLIC_MAX_FILES=$NEXT_PUBLIC_MAX_FILES \
    NEXT_PUBLIC_MAX_UPLOAD_MB=$NEXT_PUBLIC_MAX_UPLOAD_MB \
    NEXT_PUBLIC_MAX_PAGES=$NEXT_PUBLIC_MAX_PAGES
RUN npm run build

FROM python:3.12-slim AS builder
WORKDIR /build
COPY apps/api/pyproject.toml ./
COPY apps/api/echominer ./echominer
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    EMBEDDED_WORKER=true STATIC_DIR=/app/static SPOOL_DIR=/tmp/echominer-spool \
    APP_RATE_LIMIT=true
RUN useradd --system --uid 10001 --create-home echominer
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=echominer:echominer apps/api/echominer ./echominer
COPY --chown=echominer:echominer apps/api/alembic ./alembic
COPY --chown=echominer:echominer apps/api/alembic.ini ./alembic.ini
COPY --chown=echominer:echominer apps/web/public/brand/*-240w.png ./echominer/brand/
COPY --from=web --chown=echominer:echominer /web/out ./static
USER echominer
EXPOSE 10000
# Migrate, create the first admin if requested, then serve. One process: the
# rate limiter and the embedded worker are per-process by design.
CMD ["sh", "-c", "alembic upgrade head && python -m echominer.cli bootstrap-admin && exec uvicorn echominer.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers --forwarded-allow-ips '*'"]
