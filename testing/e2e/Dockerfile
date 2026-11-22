FROM node:22-bookworm-slim

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOME=/tmp

WORKDIR /e2e
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund \
    && npx playwright install-deps chromium \
    && mkdir -p /ms-playwright /e2e/results \
    && chown -R node:node /ms-playwright /e2e

COPY --chown=node:node playwright.config.ts ./
COPY --chown=node:node specs ./specs

USER node

CMD ["sh", "-c", "npx playwright install --only-shell chromium && npx playwright test"]
