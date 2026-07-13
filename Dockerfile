FROM docker.io/library/python:3.12-slim

# pandoc + texlive for md-to-pdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    lmodern \
    zip \
    unzip \
    git \
    nodejs \
    npm \
    # libs needed by chrome-headless-shell
    libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libxcomposite1 libxdamage1 libxrandr2 libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# mermaid-cli + chrome-headless-shell (~260MB, offline mmd-to-pdf)
ENV PUPPETEER_SKIP_DOWNLOAD=true
RUN npm install -g @mermaid-js/mermaid-cli
RUN npx @puppeteer/browsers install chrome-headless-shell@stable --path /opt/chrome
ENV PUPPETEER_EXECUTABLE_PATH=/opt/chrome/chrome-headless-shell/linux-*/chrome-headless-shell-linux64/chrome-headless-shell

# cairosvg for SVG-to-PDF conversion
RUN pip install --no-cache-dir cairosvg

WORKDIR /app

# SDK (control client, worker daemon, JobFS)
RUN pip install --no-cache-dir git+https://codeberg.org/kosmos-openworks/openworks-sdk.git

COPY worker/ /app/
RUN pip install --no-cache-dir -e .

COPY pipelines/ /app/pipelines/

ENTRYPOINT ["openworks-worker"]
