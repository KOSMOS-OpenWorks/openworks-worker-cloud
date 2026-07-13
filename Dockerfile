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
    chromium \
    && rm -rf /var/lib/apt/lists/*

# mermaid-cli (mmdc) for diagram-to-PDF conversion
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
RUN npm install -g @mermaid-js/mermaid-cli

WORKDIR /app

# SDK (control client, worker daemon, JobFS)
RUN pip install --no-cache-dir git+https://codeberg.org/kosmos-openworks/openworks-sdk.git

COPY worker/ /app/
RUN pip install --no-cache-dir -e .

COPY pipelines/ /app/pipelines/

ENTRYPOINT ["openworks-worker"]
