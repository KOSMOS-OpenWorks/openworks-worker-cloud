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
    libxfixes3 libx11-xcb1 libxext6 libxss1 libxtst6 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# mermaid-cli + chrome-headless-shell for correct SVG rendering
ENV PUPPETEER_SKIP_DOWNLOAD=true
RUN npm install -g @mermaid-js/mermaid-cli
RUN npx @puppeteer/browsers install chrome-headless-shell@stable --path /opt/chrome
RUN ln -s $(find /opt/chrome -name chrome-headless-shell -type f) /usr/local/bin/chrome-headless-shell
ENV PUPPETEER_EXECUTABLE_PATH=/usr/local/bin/chrome-headless-shell

# Puppeteer config for running as root in container
COPY puppeteer.json /opt/puppeteer.json

WORKDIR /app

# SDK (control client, worker daemon, JobFS)
RUN pip install --no-cache-dir git+https://codeberg.org/kosmos-openworks/openworks-sdk.git

COPY worker/ /app/
RUN pip install --no-cache-dir -e .

COPY pipelines/ /app/pipelines/

ENTRYPOINT ["openworks-worker"]
