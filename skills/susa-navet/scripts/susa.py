#!/usr/bin/env python3
"""Susa-navet (Skolverket/UHR) – hämta, synka och platta till utbildningsutbud.

API: https://api.skolverket.se/susa-navet/emil3  (version 3.x, öppet, ingen nyckel)
Endast Pythons standardbibliotek krävs. Parquet skrivs om pandas + pyarrow finns.

Kommandon
---------
  fetch     Hämta resurser till en lokal cache (JSONL.gz + meta.json)
  sync      Uppdatera en befintlig cache med ändringar sedan senaste hämtning
  flatten   Platta till cachen till en tabell, en rad per utbildningstillfälle
  providers Lista anordnare (id och namn) för en skolform
  get       Hämta en enskild post via id

Exempel
-------
  python susa.py fetch --cache data/hs --school-type HS
  python susa.py sync  --cache data/hs
  python susa.py flatten --cache data/hs --out kth.csv --provider p.uoh.kth
  python susa.py flatten --cache data/hs --out hs.parquet --with-text
  python susa.py providers --school-type HS
  python susa.py get educationInfos i.uoh.kth.sf1625.10077.20262

Som bibliotek:  import susa;  rows = susa.flatten_cache("data/hs", provider="p.uoh.kth")
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable, Iterator

BASE = os.environ.get("SUSA_BASE", "https://api.skolverket.se/susa-navet/emil3")
RESOURCES = {
    "events": "educationEvents",
    "infos": "educationInfos",
    "providers": "educationProviders",
}
PAGE_SIZE = 2000  # API:ets maximum
USER_AGENT = "susa-navet-skill/1.0 (+https://github.com/dr-ajson/SUSA)"


# --------------------------------------------------------------------------- HTTP

def _get_json(url: str, retries: int = 5, timeout: int = 180) -> Any:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504):
                last = e
            else:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(min(60, 2 ** attempt * 2))
    raise RuntimeError(f"Misslyckades efter {retries} försök: {url} ({last})")


def iter_resource(resource: str, school_types: list[str] | None = None, provider: str | None = None,
                  updated_since: str | None = None, page_size: int = PAGE_SIZE,
                  progress: bool = True) -> Iterator[dict]:
    """Iterera över alla poster i en resurs. resource = events|infos|providers (eller API-namnet).

    OBS: providerId stöds bara av educationEvents. För infos och providers ignoreras det av
    API:et, så filtrera i efterhand (se flatten_cache).
    """
    name = RESOURCES.get(resource, resource)
    params: list[tuple[str, str]] = [("size", str(page_size))]
    for s in school_types or []:
        params.append(("schoolType", s))
    if provider and name == "educationEvents":
        params.append(("providerId", provider))
    if updated_since:
        params.append(("updatedSince", updated_since))
    page = 0
    while True:
        q = urllib.parse.urlencode(params + [("page", str(page))])
        d = _get_json(f"{BASE}/{name}?{q}")
        if not isinstance(d, dict) or not isinstance(d.get(name), list) or not isinstance(d.get("page"), dict):
            raise RuntimeError(f"Ogiltigt listsvar för {name}, sida {page}, skolform {school_types}.")
        items = d[name]
        meta = d["page"]
        if progress:
            tp = meta.get("totalPages", "?")
            print(f"  {name}: sida {page + 1}/{tp} ({meta.get('totalElements', '?')} poster)", file=sys.stderr)
        yield from items
        if not any(link.get("rel") == "next" for link in d.get("links", [])) or not items:
            return
        page += 1


def get_one(resource: str, ident: str) -> dict | None:
    name = RESOURCES.get(resource, resource)
    return _get_json(f"{BASE}/{name}/{urllib.parse.quote(ident, safe='')}")


def api_info() -> dict:
    return _get_json(f"{BASE}/api-info")


# --------------------------------------------------------------------------- Cache

def _cache_file(cache: str, name: str) -> str:
    return os.path.join(cache, f"{name}.jsonl.gz")


def _write_jsonl(path: str, items: Iterable[dict]) -> int:
    n = 0
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
            n += 1
    os.replace(tmp, path)
    return n


def read_jsonl(path: str) -> Iterator[dict]:
    if not os.path.exists(path):
        return
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch(cache: str, school_types: list[str], resources: list[str], provider: str | None = None) -> dict:
    """Fullständig hämtning till cache. Skriver meta.json med tidpunkt och parametrar."""
    os.makedirs(cache, exist_ok=True)
    started = _now_iso()
    counts = {}
    for r in resources:
        name = RESOURCES[r]
        items = (x for x in iter_resource(r, school_types, provider) if x.get("status") != "DELETED")
        counts[name] = _write_jsonl(_cache_file(cache, name), items)
    meta = {"fetched_at": started, "last_sync": started, "school_types": school_types,
            "provider": provider, "resources": resources, "counts": counts,
            "api": api_info()}
    with open(os.path.join(cache, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def sync(cache: str, since: str | None = None) -> dict:
    """Hämta poster ändrade sedan senaste synk och slå ihop med cachen.

    Raderade poster (status DELETED, content null) tas bort ur cachen.
    En liten överlappning (1 dygn) används för att inte missa något.
    """
    mpath = os.path.join(cache, "meta.json")
    with open(mpath, encoding="utf-8") as f:
        meta = json.load(f)
    if since is None:
        last = dt.datetime.fromisoformat(meta["last_sync"].replace("Z", "+00:00"))
        since = (last - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    started = _now_iso()
    changes = {}
    for r in meta["resources"]:
        name = RESOURCES[r]
        current = {x["id"]: x for x in read_jsonl(_cache_file(cache, name))}
        upd = dele = 0
        for x in iter_resource(r, meta["school_types"], meta.get("provider"), updated_since=since):
            if x.get("status") == "DELETED" or x.get("content") is None:
                if current.pop(x["id"], None) is not None:
                    dele += 1
            else:
                current[x["id"]] = x
                upd += 1
        meta["counts"][name] = _write_jsonl(_cache_file(cache, name), current.values())
        changes[name] = {"nya_eller_ändrade": upd, "borttagna": dele}
    meta["last_sync"] = started
    meta.setdefault("sync_log", []).append({"at": started, "since": since, "changes": changes})
    meta["sync_log"] = meta["sync_log"][-50:]
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return {"since": since, "changes": changes, "counts": meta["counts"]}


# --------------------------------------------------------------------------- Tillplattning

def lang(node: Any, pref: str = "swe") -> str | None:
    """Plocka text på önskat språk ur LangString/LangUrl-noder (faller tillbaka på första)."""
    if not node:
        return None
    arr = node.get("strings") or node.get("urls") if isinstance(node, dict) else node
    if not arr:
        return None
    for s in arr:
        if s.get("lang") == pref:
            return s.get("value")
    return None if pref == "eng" else arr[0].get("value")


def _ext(content: dict, typ: str | None = None) -> dict:
    for e in content.get("extensions") or []:
        if typ is None or e.get("type") == typ:
            return e
    return {}


def _join(vals: Iterable[Any], sep: str = "; ") -> str | None:
    out = [str(v) for v in vals if v not in (None, "")]
    return sep.join(dict.fromkeys(out)) or None


def flatten_event(ev: dict, infos: dict[str, dict], providers: dict[str, dict], with_text: bool = False) -> dict:
    c = ev.get("content") or {}
    x = _ext(c, "UHEventExtension") or _ext(c)
    info = (infos.get(c.get("education")) or {}).get("content") or {}
    pids = c.get("providers") or []
    pnames = [lang((providers.get(p, {}).get("content") or {}).get("name")) for p in pids]
    sp = (x.get("startPeriod") or {}).get("period") or {}
    adm = x.get("admissionDetails") or {}
    appd = x.get("applicationDetails") or {}
    fee = x.get("tuitionFee") or {}
    locs = c.get("locations") or []
    cred = info.get("credits") or {}
    row = {
        "event_id": ev.get("id"),
        "provider_id": _join(pids),
        "provider_name": _join(pnames),
        "education_id": c.get("education"),
        "kod": info.get("code"),
        "titel_sv": lang(info.get("title"), "swe"),
        "titel_en": lang(info.get("title"), "eng"),
        "typ": (info.get("configuration") or {}).get("code"),
        "niva": _join(l.get("code") for l in info.get("educationLevels") or []),
        "poang": cred.get("credits"),
        "poangsystem": (cred.get("system") or {}).get("code"),
        "leder_till_examen": info.get("resultIsDegree"),
        "examen": _join(lang(d) for d in info.get("degrees") or []),
        "amnen_uh": _join(s.get("code") for s in info.get("subjects") or [] if s.get("type") == "UH_Subject"),
        "start": (c.get("execution") or {}).get("start"),
        "slut": (c.get("execution") or {}).get("end"),
        "starttermin": f"{sp.get('semester', '')}{sp.get('year', '')}" or None,
        "startperiod": sp.get("periodNumber"),
        "startvecka": (x.get("startPeriod") or {}).get("week"),
        "studietakt_pct": (c.get("paceOfStudy") or {}).get("percentage"),
        "studietid": (c.get("timeOfStudy") or {}).get("code"),
        "undervisningssprak": _join(c.get("languageOfInstructions") or []),
        "studieort": _join(lang(l.get("studyLocation")) or l.get("town") for l in locs),
        "kommunkod": _join(l.get("areaCode") for l in locs),
        "distans": "distance" in c,
        "obligatoriska_traffar": (c.get("distance") or {}).get("noOfMandatorySessions"),
        "it_distans": x.get("itdistance"),
        "anmalningskod": (c.get("application") or {}).get("code"),
        "sista_anmalan": (c.get("application") or {}).get("last") or appd.get("closeDate"),
        "antagningsomgang": adm.get("admissionRoundId"),
        "urvalsmodell": adm.get("selectionModel"),
        "antal_platser": _join(a.get("value") for a in adm.get("admissionNumbers") or []),
        "institution": x.get("department"),
        "finansieringsform": x.get("formOfFunding"),
        "studieavgift": fee.get("value"),
        "avgift_forsta": fee.get("first"),
        "avgift_total": fee.get("total"),
        "synlig_internationellt": appd.get("visibleToInternationalApplicants"),
        "endast_inom_program": appd.get("onlyAsPartOfProgram"),
        "installd": c.get("isCancelled"),
        "url_sv": lang(c.get("url"), "swe"),
        "url_en": lang(c.get("url"), "eng"),
        "ansokningsurl_sv": lang((c.get("application") or {}).get("url"), "swe"),
        "nyckelord": _join(s.get("value") for k in c.get("keywords") or [] for s in k.get("strings") or []),
        "senast_andrad_tillfalle": c.get("lastEdited"),
        "senast_andrad_utbildning": info.get("lastEdited"),
    }
    if with_text:
        row["beskrivning_sv"] = lang(info.get("description"), "swe")
        row["behorighet_sv"] = lang(info.get("eligibility"), "swe")
        row["forkunskaper_sv"] = lang(info.get("recommendedPriorKnowledge"), "swe")
    return row


def flatten_cache(cache: str, provider: str | list[str] | None = None, with_text: bool = False,
                  include_cancelled: bool = True) -> list[dict]:
    """Läs cachen och returnera en lista med rader (en per utbildningstillfälle)."""
    wanted = {provider} if isinstance(provider, str) else set(provider or [])
    events = [e for e in read_jsonl(_cache_file(cache, "educationEvents"))
              if not wanted or wanted & set((e.get("content") or {}).get("providers") or [])]
    needed = {(e.get("content") or {}).get("education") for e in events}
    infos = {i["id"]: i for i in read_jsonl(_cache_file(cache, "educationInfos")) if i["id"] in needed}
    providers = {p["id"]: p for p in read_jsonl(_cache_file(cache, "educationProviders"))}
    rows = [flatten_event(e, infos, providers, with_text) for e in events]
    if not include_cancelled:
        rows = [r for r in rows if not r["installd"]]
    return rows


def write_table(rows: list[dict], out: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if out.endswith(".parquet"):
        try:
            import pandas as pd  # noqa: WPS433
        except ImportError:
            sys.exit("Parquet kräver pandas och pyarrow. Använd .csv eller installera dem.")
        pd.DataFrame(rows).to_parquet(out, index=False)
        return
    if not rows:
        open(out, "w").close()
        return
    with open(out, "w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel läser åäö rätt
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="Full hämtning till cache")
    f.add_argument("--cache", required=True)
    f.add_argument("--school-type", nargs="+", default=["HS"], help="T.ex. HS, YH, FHS (se references/kodlistor.md)")
    f.add_argument("--resources", nargs="+", default=["events", "infos", "providers"], choices=list(RESOURCES))
    f.add_argument("--provider", help="Begränsa tillfällen till en anordnare, t.ex. p.uoh.kth "
                                        "(infos hämtas ändå för hela skolformen)")

    s = sub.add_parser("sync", help="Inkrementell uppdatering av cache")
    s.add_argument("--cache", required=True)
    s.add_argument("--since", help="Datum/tid att hämta ändringar från (standard: senaste synk minus 1 dygn)")

    fl = sub.add_parser("flatten", help="Platta till cache till CSV/Parquet")
    fl.add_argument("--cache", required=True)
    fl.add_argument("--out", required=True)
    fl.add_argument("--provider", nargs="+", help="Ett eller flera anordnar-id")
    fl.add_argument("--with-text", action="store_true", help="Ta med beskrivning, behörighet och förkunskaper")
    fl.add_argument("--exclude-cancelled", action="store_true")

    p = sub.add_parser("providers", help="Lista anordnare")
    p.add_argument("--school-type", nargs="+", default=["HS"])

    g = sub.add_parser("get", help="Hämta en post via id")
    g.add_argument("resource", choices=list(RESOURCES) + list(RESOURCES.values()))
    g.add_argument("id")

    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        print(json.dumps(fetch(a.cache, a.school_type, a.resources, a.provider), ensure_ascii=False, indent=2))
    elif a.cmd == "sync":
        print(json.dumps(sync(a.cache, a.since), ensure_ascii=False, indent=2))
    elif a.cmd == "flatten":
        rows = flatten_cache(a.cache, a.provider, a.with_text, not a.exclude_cancelled)
        write_table(rows, a.out)
        print(f"{len(rows)} rader -> {a.out}", file=sys.stderr)
    elif a.cmd == "providers":
        for x in sorted(iter_resource("providers", a.school_type, progress=False), key=lambda y: y["id"]):
            print(f"{x['id']}\t{lang((x.get('content') or {}).get('name'))}")
    elif a.cmd == "get":
        print(json.dumps(get_one(a.resource, a.id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
