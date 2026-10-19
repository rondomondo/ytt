# ytt

Fetch a YouTube transcript and print it as clean text, markdown or JSON. Single file, no install: `uv` resolves the dependencies on first run.

## Quick start

```bash
chmod +x ytt.py
./ytt.py 'https://www.youtube.com/watch?v=fYOQ97gyGCA'
```

Or without making it executable:

```bash
uv run ytt.py 'https://www.youtube.com/watch?v=fYOQ97gyGCA'
```

Quote URLs containing `?` (zsh otherwise errors).

Requires [uv](https://docs.astral.sh/uv/) (Python 3.12+ is fetched automatically).

## Usage

```bash
./ytt.py [-h] [-l LANG] [-f {text,md,json}] [-o OUTPUT] [-b {auto,api,ytdlp}] [-c BROWSER] url
```

| Option | Default | Description |
| --- | --- | --- |
| `url` | required | Video URL (`watch`, `youtu.be`, `shorts`, `embed`, `live`) or bare 11 character ID |
| `-l`, `--lang` | `en` | Comma separated language codes in priority order, e.g. `en,de` |
| `-f`, `--format` | `text` | `text`: paragraphs; `md`: paragraphs with timestamp links; `json`: raw snippets (`text`, `start`, `duration`) |
| `-o`, `--output` | stdout | Write to a file instead of stdout |
| `-b`, `--backend` | `auto` | `api`: youtube-transcript-api; `ytdlp`: yt-dlp; `auto`: API first, then yt-dlp on failure |
| `-c`, `--cookies-from-browser` | none | yt-dlp only: read cookies from a browser (`chrome`, `firefox`, `safari`, ...). Not valid with `-b api` |
| `-h`, `--help` | | Show help |

## Examples

```bash
./ytt.py fYOQ97gyGCA -f md -o transcript.md
./ytt.py https://youtu.be/fYOQ97gyGCA -l en,de -f json
./ytt.py fYOQ97gyGCA -b ytdlp -c chrome    # when YouTube blocks the API
./ytt.py fYOQ97gyGCA | pbcopy
```

## Development

```bash
make install   # uv sync --extra dev, enable the Conventional Commits hook
make check     # ruff lint, ruff format check, mypy
```

There are no tests.

## Notes

- Paragraphs break roughly every 60 seconds; whitespace and consecutive duplicate lines are removed.
- Data goes to stdout, warnings and errors to stderr. Exit code is 0 on success, 1 on failure.
