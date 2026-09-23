# Builds for the host architecture (ARM64 on Oracle Ampere A1).
FROM python:3.12-slim AS builder
WORKDIR /build
COPY apps/api/pyproject.toml ./
COPY apps/api/echominer ./echominer
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --system --uid 10001 --create-home echominer \
 && mkdir -p /var/echominer/spool && chown echominer:echominer /var/echominer/spool
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=echominer:echominer apps/api/echominer ./echominer
COPY --chown=echominer:echominer apps/api/alembic ./alembic
COPY --chown=echominer:echominer apps/web/public/brand/*-240w.png ./echominer/brand/
COPY --chown=echominer:echominer apps/api/alembic.ini ./alembic.ini
USER echominer
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz')"
CMD ["uvicorn", "echominer.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
