# Shared install layer. `npm ci` rather than `npm install`: it installs exactly
# the lockfile and fails loudly if the lockfile and package.json have drifted.
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# The source is copied per-stage rather than here, so this layer is invalidated
# only by a lockfile change and stays a reusable dependency cache across
# branches and across both downstream stages.

# ---------------------------------------------------------------------------
# Local development (docker-compose targets this stage): the Vite dev server,
# which reads VITE_* from the runtime environment and gives you hot reload.
FROM deps AS dev

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]

# ---------------------------------------------------------------------------
# Production build. Vite inlines import.meta.env at *build* time, so the VITE_*
# values must be present here as build arguments -- supplying them at runtime
# does nothing, because by then they are already baked into the bundle.
FROM deps AS build

COPY . .

ARG VITE_API_BASE_URL=""
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

RUN npm run build

# ---------------------------------------------------------------------------
# Production serve: static files only. No node, no dev server, no source.
FROM nginx:alpine AS serve

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# The packaged default site would otherwise also bind :80 and shadow the
# template above.
RUN rm -f /etc/nginx/conf.d/default.conf

# Falls back to 80 for local runs; the platform overrides it.
ENV PORT=80
EXPOSE 80
