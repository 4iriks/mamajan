# Stage 1: build frontend
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty VITE_API_URL → relative paths through Caddy proxy
RUN VITE_API_URL='' npm run build

# Stage 2: serve with Caddy (auto SSL via Let's Encrypt)
FROM caddy:2-alpine

COPY --from=builder /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80 443
