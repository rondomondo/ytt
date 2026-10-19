#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["youtube-transcript-api>=1.0", "yt-dlp"]
# ///
"""Fetch a YouTube transcript and print it as clean text, markdown or JSON"""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from youtube_transcript_api import CouldNotRetrieveTranscript, YouTubeTranscriptApi
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

VIDEO_ID_PATTERN = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")
BARE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
PARAGRAPH_SECONDS = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
MS_PER_SECOND = 1000
JSON_INDENT = 2
FORMATS = ("text", "md", "json")
BACKENDS = ("auto", "api", "ytdlp")


def extract_video_id(url: str) -> str | None:
    """Extract the 11 character video ID from a URL or bare ID"""
    if BARE_ID_PATTERN.match(url):
        return url
    match = VIDEO_ID_PATTERN.search(url)
    return match.group(1) if match else None


def fetch_api(video_id: str, languages: list[str]) -> list[dict[str, Any]]:
    """Fetch caption snippets with youtube-transcript-api

    Args:
        video_id: 11 character YouTube video ID
        languages: language codes in priority order

    Raises:
        CouldNotRetrieveTranscript: captions disabled, missing or request blocked
    """
    transcript = YouTubeTranscriptApi().fetch(video_id, languages=languages)
    return [{"text": s.text, "start": s.start, "duration": s.duration} for s in transcript]


def parse_json3(raw: str) -> list[dict[str, Any]]:
    """Convert a YouTube json3 caption file into snippets"""
    snippets: list[dict[str, Any]] = []
    for event in json.loads(raw).get("events", []):
        segments = event.get("segs")
        if not segments:
            continue
        snippets.append(
            {
                "text": "".join(segment.get("utf8", "") for segment in segments),
                "start": event.get("tStartMs", 0) / MS_PER_SECOND,
                "duration": event.get("dDurationMs", 0) / MS_PER_SECOND,
            }
        )
    return snippets


def find_caption_file(directory: Path, video_id: str, languages: list[str]) -> Path | None:
    """Find the best downloaded json3 file, honouring language priority"""
    for lang in languages:
        exact = directory / f"{video_id}.{lang}.json3"
        if exact.exists():
            return exact
        variants = sorted(directory.glob(f"{video_id}.{lang}*.json3"))
        if variants:
            return variants[0]
    return None


def fetch_ytdlp(video_id: str, languages: list[str], browser: str | None) -> list[dict[str, Any]]:
    """Fetch caption snippets with yt-dlp, optionally using browser cookies

    Uses json3 captions rather than VTT, which avoids the rolling duplicate lines of auto-generated subtitles.

    Args:
        video_id: 11 character YouTube video ID
        languages: language codes in priority order
        browser: browser to read cookies from (chrome, firefox, safari, ...) or None

    Raises:
        DownloadError: yt-dlp could not reach or parse the video
        LookupError: video has no captions in the requested languages
    """
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        options: dict[str, Any] = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": languages,
            "subtitlesformat": "json3",
            "outtmpl": str(directory / "%(id)s"),
            "quiet": True,
            "no_warnings": True,
        }
        if browser:
            options["cookiesfrombrowser"] = (browser,)
        with YoutubeDL(options) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        caption_file = find_caption_file(directory, video_id, languages)
        if caption_file is None:
            raise LookupError(f"no captions found for languages: {', '.join(languages)}")
        return parse_json3(caption_file.read_text(encoding="utf-8"))


def fetch_transcript(video_id: str, languages: list[str], backend: str, browser: str | None) -> list[dict[str, Any]]:
    """Fetch snippets using the chosen backend, falling back to yt-dlp in auto mode"""
    if backend in ("auto", "api"):
        try:
            return fetch_api(video_id, languages)
        except CouldNotRetrieveTranscript as exc:
            if backend == "api":
                raise
            print(f"warning: API backend failed ({type(exc).__name__}), trying yt-dlp", file=sys.stderr)
    return fetch_ytdlp(video_id, languages, browser)


def clean_snippets(snippets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise whitespace, drop empty snippets and consecutive duplicates"""
    cleaned: list[dict[str, Any]] = []
    for snippet in snippets:
        text = re.sub(r"\s+", " ", snippet["text"]).strip()
        if not text or (cleaned and cleaned[-1]["text"] == text):
            continue
        cleaned.append({**snippet, "text": text})
    return cleaned


def format_timestamp(seconds: float) -> str:
    """Format seconds as h:mm:ss or m:ss"""
    total = int(seconds)
    hours, remainder = divmod(total, SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, SECONDS_PER_MINUTE)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def build_paragraphs(snippets: list[dict[str, Any]]) -> list[tuple[float, str]]:
    """Group snippets into paragraphs of roughly PARAGRAPH_SECONDS each"""
    paragraphs: list[tuple[float, list[str]]] = []
    for snippet in snippets:
        if not paragraphs or snippet["start"] - paragraphs[-1][0] >= PARAGRAPH_SECONDS:
            paragraphs.append((snippet["start"], []))
        paragraphs[-1][1].append(snippet["text"])
    return [(start, " ".join(parts)) for start, parts in paragraphs]


def render(snippets: list[dict[str, Any]], fmt: str, video_id: str) -> str:
    """Render snippets in the requested format"""
    if fmt == "json":
        return json.dumps(snippets, indent=JSON_INDENT, ensure_ascii=False)
    paragraphs = build_paragraphs(snippets)
    if fmt == "md":
        return "\n\n".join(
            f"[{format_timestamp(start)}](https://youtu.be/{video_id}?t={int(start)}) {text}"
            for start, text in paragraphs
        )
    return "\n\n".join(text for _, text in paragraphs)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Download a YouTube transcript as clean text, markdown or JSON",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=True,
    )
    parser.add_argument("url", help="video URL or 11 character video ID")
    parser.add_argument("-l", "--lang", default="en", help="comma separated language codes in priority order")
    parser.add_argument("-f", "--format", choices=FORMATS, default="text", help="output format")
    parser.add_argument("-o", "--output", type=Path, help="write to this file instead of stdout")
    backend = parser.add_argument_group("backend")
    backend.add_argument(
        "-b", "--backend", choices=BACKENDS, default="auto", help="auto tries the API first, then yt-dlp"
    )
    backend.add_argument(
        "-c", "--cookies-from-browser", metavar="BROWSER", help="yt-dlp only: read cookies from chrome, firefox, etc."
    )
    return parser.parse_args()


def main() -> None:
    """Validate arguments, fetch the transcript and write it to stdout or a file"""
    args = parse_args()

    video_id = extract_video_id(args.url)
    if video_id is None:
        print(f"error: could not find a video ID in {args.url!r}", file=sys.stderr)
        sys.exit(1)

    languages = [code.strip() for code in args.lang.split(",") if code.strip()]
    if not languages:
        print("error: --lang must contain at least one language code", file=sys.stderr)
        sys.exit(1)

    if args.cookies_from_browser and args.backend == "api":
        print("error: --cookies-from-browser needs the ytdlp or auto backend", file=sys.stderr)
        sys.exit(1)

    try:
        snippets = clean_snippets(fetch_transcript(video_id, languages, args.backend, args.cookies_from_browser))
    except (CouldNotRetrieveTranscript, DownloadError, LookupError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    output = render(snippets, args.format, video_id)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
