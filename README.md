# SUSA-navet

## Skills

| Skill | Beskrivning |
|---|---|
| [`skills/susa-navet`](skills/susa-navet/SKILL.md) | Hämta, synka och analysera utbildningsutbud från Susa-navet (Skolverkets/UHR:s öppna API). |

## Automatiska flöden

| Flöde | Schema | Resultat |
|---|---|---|
| [`susa-snapshot.yml`](.github/workflows/susa-snapshot.yml) | Måndagar 04:17 UTC + manuellt | Release `susa-hs-<datum>` med hela HS-utbudet, tidsserien [`snapshots/sammanstallning.csv`](snapshots/sammanstallning.csv) och veckovisa ändringsrapporter i [`snapshots/andringar/`](snapshots/andringar/) |
