FROM node:22-bookworm-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 make g++ \
  && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts \
  && npm rebuild sharp

COPY . .
RUN if [ -f .env.local.example ] && [ ! -f .env.local ]; then cp .env.local.example .env.local; fi

ENV NEXT_TELEMETRY_DISABLED=1 \
    COGNILANCE_ORCHESTRATOR_URL=http://orchestrator:8200

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
