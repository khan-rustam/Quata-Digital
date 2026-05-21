# syntax=docker/dockerfile:1.7
# ---- deps -------------------------------------------------------------------
# Installs node_modules in a dedicated layer so unchanged package files
# reuse the layer cache between builds.
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci


# ---- builder ----------------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Produces .next/standalone/ when `output: 'standalone'` is set in
# next.config.ts. We copy only the trimmed bundle into the runtime
# image — no full node_modules, no source.
RUN npm run build


# ---- runtime ----------------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Run as the bundled non-root `node` user.
RUN apk add --no-cache curl tini \
    && addgroup -g 1001 -S nodejs \
    && adduser -S nextjs -u 1001 -G nodejs

# Static assets + the trimmed standalone server.
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:3000/ || exit 1

ENTRYPOINT ["tini", "--"]
CMD ["node", "server.js"]
