#!/usr/bin/env python3
"""Sök i senast publicerade Susa-utbud med en daterad reserv i skillpaketet."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import heapq
import json
import lzma
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "https://github.com/dr-ajson/SUSA"
MANIFEST_URL = "https://raw.githubusercontent.com/dr-ajson/SUSA/main/snapshots/latest.json"
SCHOOL_TYPES = ("HS", "YH", "FHS", "KKU", "AU", "AUB")
FIELDS = (
    "event_id", "education_id", "provider_id", "provider_name", "kod", "typ", "titel_sv", "titel_en",
    "niva", "poang", "poangsystem", "start", "starttermin", "studietakt_pct", "studieort", "distans",
    "obligatoriska_traffar", "sista_anmalan", "endast_inom_program", "url_sv", "url_en",
    "ansokningsurl_sv", "beskrivning_sv", "behorighet_sv", "forkunskaper_sv",
)
REQUIRED_FIELDS = set(FIELDS) | {"installd"}


def download_url(code: str, date: str) -> str:
    prefix = code.lower()
    return f"{REPOSITORY}/releases/download/susa-{prefix}-{date}/{prefix}_{date}.csv.gz"


def manifest(date: str) -> dict:
    return {"datum": dt.date.fromisoformat(date).isoformat(), "skolformer": list(SCHOOL_TYPES)}


def read_manifest(stream) -> dict:
    data = json.load(stream)
    validated = manifest(data["datum"])
    if data["skolformer"] != validated["skolformer"]:
        raise ValueError("Manifestet har ofullständig eller oväntad skolformstäckning.")
    return validated


def write_manifest(date: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest(date), indent=2) + "\n", encoding="utf-8")


def build_bundle(date: str, inputs: Path, output: Path) -> None:
    data = manifest(date)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        folder = Path(temp)
        archive = folder / output.name
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(ROOT.rglob("*")):
                rel = path.relative_to(ROOT)
                if path.is_file() and rel.parts[0] in {"scripts", "references", "SKILL.md"} and "__pycache__" not in rel.parts:
                    bundle.write(path, f"susa-navet/{rel.as_posix()}")
            bundle.writestr("susa-navet/assets/snapshots.json", json.dumps(data, indent=2) + "\n")
            for code in SCHOOL_TYPES:
                prefix = code.lower()
                source = inputs / f"{prefix}_{data['datum']}.csv.gz"
                if not source.exists():
                    source = inputs / prefix / source.name
                with gzip.open(source, "rt", encoding="utf-8-sig", newline="") as stream:
                    if not REQUIRED_FIELDS <= set(csv.DictReader(stream).fieldnames or ()):
                        raise ValueError(f"Ögonblicksbilden för {code} saknar erforderliga kolumner.")
                compressed = folder / f"{prefix}.csv.xz"
                with gzip.open(source, "rb") as reader, lzma.open(compressed, "wb") as writer:
                    shutil.copyfileobj(reader, writer)
                bundle.write(compressed, f"susa-navet/assets/{compressed.name}", compress_type=zipfile.ZIP_STORED)
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip() is not None:
                raise ValueError("ZIP-kontrollen misslyckades.")
        archive.replace(output)


def normal(text: str | None) -> str:
    return unicodedata.normalize("NFKC", text or "").casefold()


def compile_queries(queries: list[str]) -> list[list[re.Pattern]]:
    return [
        [re.compile(rf"\b{re.escape(word)}\b" if len(word) <= 2 else re.escape(word))
         for word in re.findall(r"[\w-]+", normal(query))]
        for query in queries
    ]


def read_catalog(path: Path, code: str, queries: list[list[re.Pattern]], provider: str,
                 limit: int) -> tuple[int, list[tuple[int, dict]]]:
    open_data = lzma.open if path.suffix == ".xz" else gzip.open
    matches = []
    count = 0
    with open_data(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED_FIELDS <= set(reader.fieldnames or ()):
            raise ValueError(f"Katalogen för {code} saknar erforderliga kolumner.")
        for index, row in enumerate(reader):
            if normal(row["installd"]) in {"true", "1"}:
                continue
            if provider and provider not in normal(row["provider_name"]) and provider not in normal(row["provider_id"]):
                continue
            title = normal(f"{row['titel_sv']} {row['titel_en']} {row['kod']}")
            description = normal(row["beskrivning_sv"])
            text = f"{title} {description} {normal(row.get('nyckelord'))}"
            scores = [sum(2 if term.search(title) else 1 for term in group)
                      for group in queries if group and all(term.search(text) for term in group)]
            if queries and not scores:
                continue
            count += 1
            entry = (max(scores, default=0), -index, row)
            if len(matches) < limit:
                heapq.heappush(matches, entry)
            else:
                heapq.heappushpop(matches, entry)
    return count, [(score, {"skolform": code, **{field: row[field] for field in FIELDS}})
                   for score, _, row in sorted(matches, reverse=True)]


def search(args) -> dict:
    bundled = None
    bundle_path = ROOT / "assets" / "snapshots.json"
    if bundle_path.is_file():
        with bundle_path.open(encoding="utf-8") as stream:
            bundled = read_manifest(stream)
    latest = None
    if not args.bundled:
        try:
            with urllib.request.urlopen(MANIFEST_URL, timeout=8) as stream:
                latest = read_manifest(stream)
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if bundled and latest and latest["datum"] < bundled["datum"]:
        latest = None
    results = []
    sources = {}
    missing = []
    queries = compile_queries(args.query)
    if any(not group for group in queries):
        raise ValueError("Varje sökfras måste innehålla minst ett ord.")
    with tempfile.TemporaryDirectory() as temp:
        for code in dict.fromkeys(args.school_type or SCHOOL_TYPES):
            found = None
            if latest:
                url = download_url(code, latest["datum"])
                path = Path(temp, f"{code}.csv.gz")
                try:
                    with urllib.request.urlopen(url, timeout=20) as stream, path.open("wb") as target:
                        shutil.copyfileobj(stream, target)
                    found = read_catalog(path, code, queries, normal(args.provider), args.limit)
                    sources[code] = {"datum": latest["datum"], "kalla": "Senast publicerade ögonblicksbild", "url": url}
                except (OSError, EOFError, ValueError, csv.Error):
                    pass
            if found is None and bundled:
                path = ROOT / "assets" / f"{code.lower()}.csv.xz"
                if path.is_file():
                    found = read_catalog(path, code, queries, normal(args.provider), args.limit)
                    sources[code] = {
                        "datum": bundled["datum"],
                        "kalla": "Medföljande ögonblicksbild",
                        "url": download_url(code, bundled["datum"]),
                    }
            if found is None:
                missing.append(code)
                continue
            sources[code]["matchande_tillfallen"] = found[0]
            results.extend(found[1])
    results.sort(key=lambda match: match[0], reverse=True)
    return {"kallor": sources, "otillgangliga_skolformer": missing, "traffar": [row for _, row in results[:args.limit]]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    lookup = commands.add_parser("search", help="Sök efter utbildningstillfällen")
    lookup.add_argument("--school-type", nargs="+", choices=SCHOOL_TYPES)
    lookup.add_argument("--query", action="append", default=[], help="Alla ord i en fras. Upprepa för alternativa fraser.")
    lookup.add_argument("--provider", default="", help="Del av anordnarens namn eller id")
    lookup.add_argument("--limit", type=int, default=12)
    lookup.add_argument("--bundled", action="store_true", help="Använd den medföljande bilden utan nätanrop")
    for command in ("manifest", "bundle"):
        build = commands.add_parser(command)
        build.add_argument("--date", required=True)
        build.add_argument("--out", type=Path, required=True)
        if command == "bundle":
            build.add_argument("--inputs", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "manifest":
        write_manifest(args.date, args.out)
    elif args.command == "bundle":
        build_bundle(args.date, args.inputs, args.out)
    else:
        if not 1 <= args.limit <= 50:
            parser.error("--limit måste vara 1–50.")
        try:
            result = search(args)
        except (OSError, EOFError, ValueError, csv.Error) as exc:
            parser.error(str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["kallor"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
