# openworks-worker-cloud

OpenWorks reference worker for cloud-native pipelines.

Picks jobs via HTTP poll, reads/writes via WebDAV shares,
reports progress via stages.

## Pipelines

| Pipeline | Source | Result | Needs |
|----------|--------|--------|-------|
| `md-to-pdf` | Markdown | PDF | pandoc + xelatex |
| `doc-to-pdf` | DOC/DOCX/ODT | PDF | Collabora sidecar |
| `zip-create` | Folder/files | ZIP | zip |
| `unzip` | ZIP | Folder | unzip |
| `tar-extract` | TAR/GZ/BZ2/XZ | Folder | tar |
| `test-echo` | Any text file | .result.json | (none) |

## Usage

```bash
openworks-worker \
  --url https://cloud.example.com \
  --user worker-cloud-01 \
  --token <api-token> \
  --pick md-to-pdf,zip-create,unzip \
  --capacity 2
```

## Part of the Kosmos Initiative

Built for [OpenCloud](https://codeberg.org/kosmos-eu).
