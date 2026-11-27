# Kodlistor

## schoolType (skolform)

| Kod | Skolform |
|---|---|
| HS | Högskola (inkl. polisutbildning) |
| YH | Yrkeshögskola |
| FHS | Folkhögskola, blandade utbildningsnivåer |
| AUB | Arbetsmarknadsutbildning |
| VUXGR / VUXGY | Komvux grundläggande / gymnasial nivå |
| VUXGRAN / VUXGYAN | Komvux som anpassad utbildning, grundläggande / gymnasial |
| VUXSFI | Komvux i svenska för invandrare |
| NY | Nationell yrkesutbildning på gymnasial nivå |
| GY / GYAN | Gymnasieskola / anpassad gymnasieskola |
| GR / GRAN / SP / SAM | Grundskola / anpassad grundskola / specialskola / sameskola |
| FKLASS, FTH, OPPFTH | Förskoleklass, fritidshem, öppen fritidsverksamhet |
| KKU | Konst- och kulturutbildning |
| AU | Annan undervisning, inklusive utbildningar med endast tillsyn i API:et |
| KU, STF | Kulturskola, studieförbund |

Källa: OpenAPI-specen v3.0.4. Täckningen varierar – Komvux var vid införandet bara delvis inläst.

## Värden i HS-data (observerade 2026-11-24)

- `configuration.code`: kurs (52 301), program (10 751), kurspaket (1 075)
- `educationLevels[].code`: grund, avancerad, grundavancerad, förutbildning
- `credits.system.code`: hp, fup (förutbildningspoäng). Specen tillåter även yh, gy, vp, nyp.
- `timeOfStudy.code`: dag, blandad, kväll, ingen, eftermiddag, veckoslut
- `paceOfStudy.percentage`: 100, 50, 25, 33, 75, 67, 17, 10 …
- `languageOfInstructions`: swe, eng, spa, ger, fre … (ISO 639-2/B)
- `execution.condition.code`: 1 (nästan alla), 3. Specen tillåter 0–3; betydelsen dokumenteras inte i specen.
- `status`: ACTIVE; med `updatedSince` även DELETED.
