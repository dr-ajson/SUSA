# Susa-navet – datamodell och fallgropar

Verifierat mot API version 3.0.4 (EMIL 3.00.04) den 2026-11-24.

## Resurser och filter

Bas-URL: `https://api.skolverket.se/susa-navet/emil3`
OpenAPI-spec: `https://api.skolverket.se/susa-navet/susa-navet-emil3.yaml`
Swagger: `https://api.skolverket.se/susa-navet/swagger-ui/index.html`
Dokumentation: https://www.skolverket.se/om-skolverket/oppna-data/api-for-utbildningstillfallen-susa-navet

| Endpoint | Filter som fungerar | Innehåll |
|---|---|---|
| `/educationInfos` | schoolType, updatedSince, page, size | Utbildningen: titel, kod, poäng, nivå, examen, ämnen, beskrivning, behörighet |
| `/educationEvents` | schoolType, **providerId**, updatedSince, page, size | Tillfället: datum, termin, takt, ort, anmälningskod, antagning, avgift, institution, finansieringsform |
| `/educationProviders` | schoolType, updatedSince, page, size | Anordnare: namn, adress, huvudman |
| `/{resurs}/{id}` | – | En post. Okänt id ger 404 (skriptet returnerar `null`). |
| `/api-info` | – | Version och status |

- **`providerId` fungerar bara på `educationEvents`.** På infos och providers ignoreras det tyst och
  hela skolformen returneras. Hämta därför infos för hela skolformen och filtrera via tillfällenas
  `content.education`.
- `size` max 2000. Svaret har `page.totalElements`/`totalPages` och `links` med `rel` = first/self/next/last.
- `schoolType` kan upprepas (`?schoolType=HS&schoolType=YH`).
- `updatedSince` tar datum (`2026-11-20`, tolkas som midnatt) eller datum-tid. Med det ingår också
  raderade poster: `{"id": ..., "status": "DELETED", "content": null}`. Utan det returneras bara `ACTIVE`.

## Storlek (HS, 2026-11-24)

- 64 127 tillfällen, 64 114 utbildningar, 50 anordnare. Hela HS-hämtningen tar ca 4 min.
- Infos är tunga (ca 140 MB okomprimerad JSON för HS, ca 13 MB som jsonl.gz) – hämta en gång, synka sedan.
- KTH: 1 100 tillfällen.

## Kopplingar

```
educationEvent.content.education  ──>  educationInfo.id
educationEvent.content.providers[] ──>  educationProvider.id
```

Utbildningar saknar egen anordnarreferens; anordnaren syns bara i tillfällena (och i id-prefixet,
t.ex. `i.uoh.kth.…`, men lita inte på prefixet). För HS har varje tillfälle exakt en anordnare.

## Id-mönster (HS)

- Anordnare: `p.uoh.<kortnamn>` (lärosäten), `p.pu.e3.<ort>` (polisutbildningen, huvudman Polismyndigheten).
- Utbildning: `i.uoh.<kortnamn>.<kurskod>.<anmälningskod>.<termin>` – t.ex. `i.uoh.kth.cinek.32106.20262`.
  Termin: `<år><1=VT|2=HT>`.
- Tillfälle: samma mönster med prefix `e.`.
- Samma kurs med flera tillfällen/terminer får flera utbildningsposter (en per tillfälle). Gruppera på
  `kod` + anordnare för att räkna unika kurser.

## Viktiga fält (sökväg i `content`)

Tillfälle (`educationEvents`):
- `execution.start` / `execution.end`, `paceOfStudy.percentage`, `timeOfStudy.code`
- `languageOfInstructions[]` (ISO 639-2: swe, eng …), `locations[].studyLocation`, `locations[].areaCode` (kommunkod)
- `distance` finns bara på distanstillfällen (antal obligatoriska/valfria träffar; −1 = okänt)
- `application.code` (anmälningskod), `application.last` (sista anmälningsdag)
- `isCancelled` – inställda tillfällen finns kvar i datan
- `extensions[type=UHEventExtension]`:
  - `formOfFunding` – **lokal Ladok-kod per lärosäte**, se nedan
  - `department` – institution/skola (lokal kod; KTH: t.ex. `A`, `M`, `ALF`)
  - `startPeriod.period` (år, VT/HT, läsperiod), `startPeriod.week`, `stopWeek.week` (ÅÅÅÅVV)
  - `tuitionFee.value` (om avgiftsskyldiga betalar), `first`, `total` (SEK)
  - `admissionDetails`: `admissionRoundId`, `selectionModel`, `admissionNumbers[].value` (999 förekommer ofta – troligen platshållare, inte verkligt platsantal),
    `distributionOfCredits` (poäng per termin)
  - `applicationDetails`: `onlyAsPartOfProgram`, `visibleToInternationalApplicants`

Utbildning (`educationInfos`):
- `code`, `title`, `configuration.code` (kurs/program/kurspaket), `educationLevels[].code`
  (grund/avancerad/grundavancerad/förutbildning), `credits.credits` + `credits.system.code` (hp, fup = förutbildningspoäng)
- `resultIsDegree`, `degrees[]`, `subjects[type=UH_Subject].code` (lärosätenas ämneskoder, inte avkodade här)
- `description`, `eligibility`, `recommendedPriorKnowledge` – text på swe/eng; kan vara Markdown
  (`content: "MARKDOWN"`) eller HTML (`content: "HTML"`, från v3.0.4)

Textfält är `LangString`: `{"strings": [{"lang": "swe", "value": "..."}, {"lang": "eng", ...}]}`.

## Finansieringsform (`formOfFunding`) – läs detta innan du tolkar

Koden är lärosätets lokala finansieringsform i Ladok. Bara **`ORD` (ordinarie)** är gemensam
(ca 93 % av HS-tillfällena). Övriga koder är lokala och kodlistorna publiceras inte i API:et.
Tolkningarna nedan är härledda ur titlarna, inte bekräftade av lärosätena:
- KTH: `LL` (211 tillfällen, fortbildningskurser – sannolikt livslångt lärande), `B` (tekniskt basår),
  `KPL` (KPU), `UPS` (”Teknik för lärare i åk 7-9” – sannolikt Lärarlyftet).
- Andra lärosäten: `U`, `UL`, `LF`, `LLY`, `US`, `UU`, `SKV` m.fl. bär titlar med ”Ingår i Lärarlyftet”
  eller ”Uppdrag av Skolverket”; `UP` (SU) har ”uppdragsutbildning” i titeln; `UKU`, `ULV`, `TA2`
  gäller kompletterande utbildning för personer med utländsk examen.

Se `finansieringsformer_hs.csv` (kod, antal och exempeltitlar per lärosäte) och tolka alltid koden
per lärosäte. För sektorsövergripande frågor om uppdragsutbildning/Lärarlyftet: kombinera kod
≠ ORD med nyckelord i titeln (”uppdragsutbildning”, ”Lärarlyftet”, ”Uppdrag av Skolverket”) och
redovisa metoden. Uppdragsutbildning som inte söks via antagning finns i regel inte i Susa-navet.

## Övrigt att känna till

- Datan är en ögonblicksbild av *aktuellt* utbud (uppdateras dagligen). Tidsserier kräver egna sparade
  ögonblicksbilder.
- Äldre starttermin (t.ex. HT2022) kan förekomma för pågående program och långa tillfällen.
- `p.pu.e3.*` är polisutbildningen, med lärosätesnamn men huvudman Polismyndigheten – exkludera eller
  redovisa separat vid lärosätesjämförelser (Högskolan i Borås finns både som `p.uoh.hb` och `p.pu.e3.boras`).
- Licens: Skolverkets källicens / CC0 1.0. Gamla API:et (v2, `susanavet2.skolverket.se`) tas ur bruk 2026-05-04
  och innehåller inte längre högskoleutbildning.
