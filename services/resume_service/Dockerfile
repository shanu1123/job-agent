FROM python:3.11-slim

# ── Node.js 20 LTS ────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Chromium system dependencies (required by Playwright) ─────────────────────
RUN apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libx11-xcb1 libxcb-dri3-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── npm install + Playwright Chromium (baked into image) ──────────────────────
WORKDIR /job-agent
COPY package.json package-lock.json* ./
RUN npm install
RUN npx playwright install chromium

# ── Python service ────────────────────────────────────────────────────────────
WORKDIR /app
COPY services/resume_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/resume_service/app/ ./app/
RUN mkdir -p /app/output

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
