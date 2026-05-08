# ── build ──────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

# ── runtime ───────────────────────────────────────────────────────────────
FROM node:20-alpine
RUN addgroup -g 1001 trader && adduser -u 1001 -G trader -D trader
WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER trader
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
