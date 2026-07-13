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
    && rm -rf /var/lib/apt/lists/*

# cairosvg for SVG-to-PDF conversion (used by mmd-to-pdf)
RUN pip install --no-cache-dir cairosvg

WORKDIR /app

# SDK (control client, worker daemon, JobFS)
RUN pip install --no-cache-dir git+https://codeberg.org/kosmos-openworks/openworks-sdk.git

COPY worker/ /app/
RUN pip install --no-cache-dir -e .

COPY pipelines/ /app/pipelines/

ENTRYPOINT ["openworks-worker"]
