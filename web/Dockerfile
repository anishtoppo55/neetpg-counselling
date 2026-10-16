# Development image: Next.js dev server with hot reload (Phase 1 runs locally only).
FROM node:20.18-slim

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# Deliberately `npm install` and an optional lockfile here, unlike Dockerfile.prod: the development
# image should still build while you are adding or bumping a dependency.
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
