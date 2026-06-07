#build stage
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tooling
RUN pip install --no-cache-dir hatchling

# Copy project metadata first to leverage layer caching
COPY pyproject.toml .
COPY src/ src/

# Build wheel
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

# runtime stage 
FROM python:3.12-slim

# Non-root user — principle of least privilege
RUN addgroup --gid 1001 trader \
    && adduser  --uid 1001 --gid 1001 --no-create-home --disabled-password trader

WORKDIR /app

# Install wheels (no network access at this step)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels ibkr-adapter \
    && rm -rf /wheels

USER trader

# Health + metrics ports
EXPOSE 8080 9090

ENTRYPOINT ["ibkr-adapter"]
