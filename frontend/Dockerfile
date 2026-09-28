# ─────────────────────────────────────────────────────────────────────────────
# Worknoon Refund System — Frontend Image
# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Node — build the Vite/React app
# Stage 2: nginx — serve the compiled static assets
#
# VITE_API_BASE_URL must be set at build time so Vite can inline the correct
# backend URL into the bundle.  docker-compose passes it via build args.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Accept the API base URL as a build argument; default to the docker-compose
# service name so the browser can reach the backend container.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Install dependencies (layer-cached unless package*.json changes).
COPY package*.json ./
RUN npm ci --prefer-offline

# Copy source and build.
COPY . .
RUN npm run build

# ── Stage 2: serve ───────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS serve

# Remove the default nginx site.
RUN rm /etc/nginx/conf.d/default.conf

# Copy the custom nginx config.
COPY nginx.conf /etc/nginx/conf.d/app.conf

# Copy built assets from stage 1.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
