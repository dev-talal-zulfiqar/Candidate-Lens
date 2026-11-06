# Dev-oriented image: runs the Vite dev server, matching the local
# (non-Docker) workflow in the README rather than a production build.
# Source is bind-mounted over this in compose.yaml; node_modules is kept
# out of that mount (see compose.yaml) so the container's own install —
# built for its platform — isn't shadowed by the host's.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
