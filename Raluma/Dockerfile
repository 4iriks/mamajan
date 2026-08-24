# Stage 1: build frontend
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Production uses relative /api paths through the Caddy reverse proxy. Fail the
# image build if a developer-only backend address leaks into the bundle.
RUN npm run build \
    && ! grep -R -F "http://localhost:8000" dist

# Stage 2: serve with Caddy (auto SSL via Let's Encrypt)
FROM caddy:2-alpine

COPY --from=builder /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80 443
