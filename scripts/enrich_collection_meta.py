#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Optional, List

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "vinyl-collection.json"

# Known canonical metadata for current collection.
KNOWN_META = {
    "SOB ROCK": {"author": "JOHN MAYER", "year": "2021"},
    "RUBBER SOUL": {"author": "THE BEATLES", "year": "1965"},
    "MORRISON HOTEL": {"author": "THE DOORS", "year": "1970"},
}


def parse_folder_meta(folder: str):
    name = Path(folder).name
    m = re.match(r"^\s*(.*?)\s*-\s*(.*)$", name)
    if not m:
        return None, None, None
    artist = m.group(1).strip().upper()
    album_raw = m.group(2).strip()
    year_match = re.search(r"(19|20)\d{2}", album_raw)
    year = year_match.group(0) if year_match else None
    album = re.sub(r"\[[^\]]+\]", "", album_raw)
    album = re.sub(r"\((19|20)\d{2}\)", "", album)
    album = re.sub(r"\s+\d+\s*$", "", album)
    album = re.sub(r"\s+", " ", album).strip().upper()
    return artist, album, year


def clean_track_name(value: str, author: str):
    s = str(value or "").strip()
    s = re.sub(r"\.(mp3|flac|wav|m4a|aac|ogg)$", "", s, flags=re.I)
    s = re.sub(r"^\s*\d+\s*[\.\-\)]\s*", "", s)
    if author:
        s = re.sub(rf"^\s*{re.escape(author)}\s*-\s*", "", s, flags=re.I)
    s = re.sub(r"^\s*[^-]+-\s*", "", s)  # generic "Artist - Track"
    s = re.sub(r"\s+", " ", s).strip()
    return s


def seconds_to_mmss(total_seconds: int):
    total_seconds = max(0, int(total_seconds))
    m, s = divmod(total_seconds, 60)
    return f"{m:02d}:{s:02d}"


def try_read_total_duration_seconds(folder: str, tracks: List[str]) -> Optional[int]:
    # Optional: only if mutagen exists in env.
    try:
        from mutagen import File as MutagenFile  # type: ignore
    except Exception:
        return None

    total = 0.0
    for track in tracks:
        path = ROOT / folder / track
        if not path.exists():
            continue
        try:
            audio = MutagenFile(str(path))
            if audio and getattr(audio, "info", None) and getattr(audio.info, "length", None):
                total += float(audio.info.length)
        except Exception:
            continue
    if total <= 0:
        return None
    return int(round(total))


def main():
    if not MANIFEST.exists():
        raise SystemExit(f"Missing manifest: {MANIFEST}")

    with MANIFEST.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise SystemExit("Manifest must be an array")

    changed = 0
    for item in data:
        if not isinstance(item, dict):
            continue
        folder = str(item.get("folder", "")).strip()
        old_name = str(item.get("name", "")).strip().upper()
        artist_guess, album_guess, year_guess = parse_folder_meta(folder)

        # Author / album / year
        known = KNOWN_META.get(old_name) or KNOWN_META.get((album_guess or "").upper())
        if known:
            item["author"] = known["author"]
            item["year"] = known["year"]
            if album_guess:
                item["name"] = album_guess
        else:
            if artist_guess:
                item["author"] = artist_guess
            if album_guess:
                item["name"] = album_guess
            if year_guess:
                item["year"] = year_guess

        # Tracks: remove numbering/prefix/author/extensions from displayed track names.
        tracks = item.get("tracks")
        if isinstance(tracks, list):
            author = str(item.get("author", "")).strip()
            cleaned = [clean_track_name(t, author) for t in tracks if str(t).strip()]
            item["tracks"] = cleaned

            # Fill duration if available and currently missing.
            if not str(item.get("duration", "")).strip():
                seconds = try_read_total_duration_seconds(folder, tracks)
                if seconds is not None:
                    item["duration"] = seconds_to_mmss(seconds)

        changed += 1

    with MANIFEST.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Updated {changed} albums in {MANIFEST.name}")


if __name__ == "__main__":
    main()
