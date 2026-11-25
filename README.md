# SUSA-navet

## Skills

| Skill | Beskrivning |
|---|---|
| [`skills/susa-navet`](skills/susa-navet/SKILL.md) | Hämta, synka och analysera utbildningsutbud från Susa-navet (Skolverkets/UHR:s öppna API). |

## Automatiska flöden

| Flöde | Schema | Resultat |
|---|---|---|
| [`susa-snapshot.yml`](.github/workflows/susa-snapshot.yml) | Måndagar 04:17 UTC + manuellt | Release `susa-hs-<datum>` med hela HS-utbudet, tidsserien [`snapshots/sammanstallning.csv`](snapshots/sammanstallning.csv) och veckovisa ändringsrapporter i [`snapshots/andringar/`](snapshots/andringar/) |

Den ursprungliga ögonblicksbilden från [24 november 2026](https://github.com/dr-ajson/Privat/releases/tag/susa-hs-2026-11-24) ligger i Privat. Tidsserien och ändringsrapporten för det datumet finns här i `snapshots/`.
