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
    # cairo libs for cairosvg (SVG→PDF)
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# mermaid renderer: jsdom + @napi-rs/canvas (headless, no browser needed)
WORKDIR /opt/mermaid
RUN npm init -y && npm install mermaid@11 jsdom@26 @napi-rs/canvas@0.1

# cairosvg for SVG-to-PDF conversion
RUN pip install --no-cache-dir cairosvg

WORKDIR /app

# SDK (control client, worker daemon, JobFS)
RUN pip install --no-cache-dir git+https://codeberg.org/kosmos-openworks/openworks-sdk.git

COPY worker/ /app/
RUN pip install --no-cache-dir -e .

# Mermaid render script (lives with its node_modules)
COPY mermaid-render.mjs /opt/mermaid/mermaid-render.mjs

COPY pipelines/ /app/pipelines/

ENTRYPOINT ["openworks-worker"]
