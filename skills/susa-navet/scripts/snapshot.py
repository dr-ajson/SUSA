#!/usr/bin/env python3
"""Daterad ögonblicksbild av Susa-navet + tidsserie + ändringsrapport.

Används av GitHub Actions (.github/workflows/susa-snapshot.yml) men går att köra lokalt:

  python snapshot.py --cache data/hs --out-dir out --repo-dir . [--previous prev/hs_2026-11-23.csv.gz]

Skapar:
  out/<skolform>_<datum>.csv.gz                 utbildningstillfällen med utbildningstext
  out/release_notes.md                           kort sammanfattning för releasen
  <repo-dir>/snapshots/sammanstallning.csv       tidsserie: ett mått-set per anordnare och datum
  <repo-dir>/snapshots/andringar/<datum>.md      nya och försvunna utbildningar jämfört med föregående bild

Endast standardbiblioteket.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import susa  # noqa: E402

METRICS = [
    "tillfallen", "installda", "utbildningar", "kurser", "program", "kurspaket",
    "distans", "deltid", "kvall_helg_blandad", "engelska", "ej_ord_finansiering", "ll_kth",
]
SUMMARY_FIELDS = ["datum", "api_version", "provider_id", "provider_name"] + METRICS
MAX_LIST = 40  # max antal listade utbildningar per lärosäte och riktning i ändringsrapporten


def _truthy(v) -> bool:
    return v in (True, "True", "true", 1, "1")


def write_csv_gz(rows: list[dict], path: str) -> None:
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else list(susa.flatten_event({}, {}, {}, with_text=True)))
        w.writeheader()
        w.writerows(rows)


def read_csv_gz(path: str) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def active(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not _truthy(r.get("installd"))]


def summarize(rows: list[dict], datum: str, api_version: str) -> list[dict]:
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["provider_id"], (r["provider_name"] or "").strip())].append(r)
    out = []
    for (pid, name), rs in sorted(by.items()):
        act = active(rs)
        uniq = {(r["kod"] or r["education_id"] or r["event_id"], r["typ"]) for r in act}
        def pace(r):
            try:
                return float(r["studietakt_pct"]) < 100
            except (TypeError, ValueError):
                return False
        out.append({
            "datum": datum, "api_version": api_version, "provider_id": pid, "provider_name": name,
            "tillfallen": len(act),
            "installda": len(rs) - len(act),
            "utbildningar": len(uniq),
            "kurser": sum(1 for _, t in uniq if t == "kurs"),
            "program": sum(1 for _, t in uniq if t == "program"),
            "kurspaket": sum(1 for _, t in uniq if t == "kurspaket"),
            "distans": sum(1 for r in act if _truthy(r["distans"])),
            "deltid": sum(1 for r in act if pace(r)),
            "kvall_helg_blandad": sum(1 for r in act if r["studietid"] in ("kväll", "veckoslut", "blandad")),
            "engelska": sum(1 for r in act if "eng" in (r["undervisningssprak"] or "")),
            "ej_ord_finansiering": sum(1 for r in act if r["finansieringsform"] not in ("ORD", "", None)),
            "ll_kth": sum(1 for r in act if pid == "p.uoh.kth" and r["finansieringsform"] == "LL"),
        })
    return out


def append_summary(summary: list[dict], path: str, datum: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = [r for r in csv.DictReader(f) if r["datum"] != datum]  # idempotent per datum
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        w.writerows(existing + summary)


def _edu_index(rows: list[dict]) -> dict[tuple, dict]:
    idx = {}
    for r in active(rows):
        key = tuple(str(v or "") for v in (r["provider_id"], r["kod"] or r["education_id"] or r["event_id"], r["typ"]))
        idx.setdefault(key, r)
    return idx


def diff_report(cur: list[dict], prev: list[dict] | None, datum: str, prev_datum: str | None, school_type: str = "HS") -> tuple[str, dict]:
    lines = [f"# Ändringar i Susa-navet ({school_type}) {datum}", ""]
    if prev is None:
        lines += ["Första ögonblicksbilden – ingen jämförelse.", ""]
        return "\n".join(lines), {"nya": 0, "borta": 0}
    a, b = _edu_index(prev), _edu_index(cur)
    new = [b[k] for k in sorted(set(b) - set(a))]
    gone = [a[k] for k in sorted(set(a) - set(b))]
    lines += [
        f"Jämfört med {prev_datum}. Enhet: unik utbildning (anordnare + kod eller id + typ) med minst ett ej inställt tillfälle.",
        "En utbildning som ”försvinner” kan ha avslutats, bytt kod eller bara saknar kommande tillfällen.", "",
        f"**Nya: {len(new)} · Försvunna: {len(gone)}**", "",
    ]
    per = collections.defaultdict(lambda: {"nya": [], "borta": []})
    for r in new:
        per[(r["provider_name"] or r["provider_id"] or "Okänd anordnare").strip()]["nya"].append(r)
    for r in gone:
        per[(r["provider_name"] or r["provider_id"] or "Okänd anordnare").strip()]["borta"].append(r)
    if per:
        lines += ["| Anordnare | Nya | Försvunna |", "|---|---:|---:|"]
        for name, d in sorted(per.items(), key=lambda x: -(len(x[1]["nya"]) + len(x[1]["borta"]))):
            lines.append(f"| {name} | {len(d['nya'])} | {len(d['borta'])} |")
        lines.append("")
    for name, d in sorted(per.items()):
        lines.append(f"## {name}")
        for label, key in (("Nya", "nya"), ("Försvunna", "borta")):
            rs = d[key]
            if not rs:
                continue
            lines.append(f"**{label} ({len(rs)})**")
            for r in rs[:MAX_LIST]:
                extra = ", ".join(str(x) for x in [r["typ"], f"{r['poang']} {r['poangsystem']}".strip(),
                                               r["finansieringsform"], r["starttermin"]] if x)
                lines.append(f"- {r['kod'] or r['education_id']} – {r['titel_sv'] or r['titel_en'] or 'Utan titel'} ({extra})")
            if len(rs) > MAX_LIST:
                lines.append(f"- … och {len(rs) - MAX_LIST} till (se release-filen)")
            lines.append("")
    return "\n".join(lines), {"nya": len(new), "borta": len(gone)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--repo-dir", default=".")
    ap.add_argument("--school-type", choices=["HS", "YH", "FHS", "KKU", "AU", "AUB"], default="HS")
    ap.add_argument("--previous", help="Föregående CSV-fil för samma skolform, komprimerad med gzip")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    a = ap.parse_args()

    with open(os.path.join(a.cache, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    api_version = (meta.get("api") or {}).get("apiVersion", "")
    if meta.get("school_types") != [a.school_type] or meta.get("provider"):
        ap.error("Cachen måste omfatta precis den valda skolformen och alla anordnare.")
    for resource in susa.RESOURCES.values():
        if resource not in meta.get("counts", {}) or not Path(a.cache, f"{resource}.jsonl.gz").is_file():
            ap.error(f"Cachen saknar {resource}.")
    rows = susa.flatten_cache(a.cache, with_text=True)
    if len(rows) != meta["counts"]["educationEvents"]:
        ap.error("Antalet exporterade tillfällen stämmer inte med cachen.")
    if a.school_type == "HS" and not rows:
        ap.error("HS-hämtningen gav inga tillfällen.")
    os.makedirs(a.out_dir, exist_ok=True)
    prefix = a.school_type.lower()
    snap = os.path.join(a.out_dir, f"{prefix}_{a.date}.csv.gz")
    write_csv_gz(rows, snap)

    summary = summarize(rows, a.date, api_version)
    history_dir = Path(a.repo_dir, "snapshots")
    if a.school_type != "HS":
        history_dir /= prefix
    append_summary(summary, str(history_dir / "sammanstallning.csv"), a.date)

    prev = prev_datum = None
    if a.previous and os.path.exists(a.previous):
        previous_name = Path(a.previous).name
        previous_prefix, separator, previous_date = previous_name.removesuffix(".csv.gz").partition("_")
        if previous_prefix != prefix or not separator:
            ap.error("Föregående ögonblicksbild måste gälla samma skolform.")
        prev_datum = dt.date.fromisoformat(previous_date).isoformat()
        prev = read_csv_gz(a.previous)
        if prev_datum == a.date:  # samma dag körd två gånger – jämför inte med sig själv
            prev = prev_datum = None
    report, counts = diff_report(rows, prev, a.date, prev_datum, a.school_type)
    rdir = history_dir / "andringar"
    os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, f"{a.date}.md"), "w", encoding="utf-8") as f:
        f.write(report + "\n")

    tot = {m: sum(s[m] for s in summary) for m in ("tillfallen", "utbildningar")}
    kth = next((s for s in summary if s["provider_id"] == "p.uoh.kth"), None)
    notes = [
        f"Ögonblicksbild av Susa-navet, skolform {a.school_type}, hämtad {meta.get('fetched_at')} (API {api_version}).",
        "",
        f"- Tillfällen (ej inställda): {tot['tillfallen']}",
        f"- Unika utbildningar: {tot['utbildningar']}",
        (f"- Jämfört med {prev_datum}: {counts['nya']} nya, {counts['borta']} försvunna utbildningar"
         if prev_datum else "- Första ögonblicksbilden – ingen jämförelse"),
    ]
    if kth:
        notes.append(f"- KTH: {kth['tillfallen']} tillfällen, {kth['utbildningar']} utbildningar, LL-finansierade tillfällen: {kth['ll_kth']}")
    if a.school_type in {"FHS", "AUB"}:
        notes.append("- Skolformen innehåller flera utbildningsnivåer. Använd uppgifterna om nivå och behörighet per tillfälle.")
    report_path = (rdir / f"{a.date}.md").relative_to(a.repo_dir).as_posix()
    notes += ["", f"Ändringsrapport: `{report_path}`. Licens för Susa-data: CC0 (Skolverket)."]
    with open(os.path.join(a.out_dir, "release_notes.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(notes) + "\n")
    print("\n".join(notes))


if __name__ == "__main__":
    main()
