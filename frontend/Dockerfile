# Production image for the React app: build once with Node, serve with nginx.
# (Development doesn't use this file: docker-compose.yml runs the Vite dev server.)

# --- build ----------------------------------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app
# Dependencies first (cached layer), exactly as locked in package-lock.json.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Type-checks and builds; fails the image build on any TypeScript error.
RUN npm run build

# --- serve ----------------------------------------------------------------------------------
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
