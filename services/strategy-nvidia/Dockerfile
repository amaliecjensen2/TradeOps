# byg
FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml .
COPY src/ src/
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

# runtime
FROM python:3.12-slim
RUN addgroup --gid 1001 trader \
    && adduser  --uid 1001 --gid 1001 --no-create-home --disabled-password trader
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels strategy-nvidia \
    && rm -rf /wheels
USER trader
EXPOSE 8080
ENTRYPOINT ["strategy-nvidia"]
