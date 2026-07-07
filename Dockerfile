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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/ /app/
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["openworks-worker"]
