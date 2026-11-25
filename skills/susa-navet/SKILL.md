---
name: susa-navet
description: Hämta och analysera svenskt utbildningsutbud från Susa-navet (Skolverkets/UHR:s öppna API) – kurser, program och utbildningstillfällen vid universitet och högskolor, YH, folkhögskolor och Komvux. Använd för frågor om ett lärosätes utbud, jämförelser av utbud mellan lärosäten, fristående kurser, distans, studietakt, livslångt lärande, Lärarlyftet, studieavgifter eller anmälningskoder, och för att bygga eller uppdatera en lokal kopia av utbudet. Använd också för vägledande matchning mot utbildningar utifrån yrkeserfarenhet, vidareutbildning och karriärmål. Use for any question about current Swedish course/programme offerings, even if Susa-navet is not named.
---

# Susa-navet

Öppet REST-API utan nyckel: `https://api.skolverket.se/susa-navet/emil3` (v3, data uppdateras dagligen).
Nätverket måste tillåta `api.skolverket.se`; om anropet nekas av proxyn, be användaren lägga till
domänen som tillåten (Inställningar > Capabilities på claude.ai) i stället för att prova andra vägar.

Läs `references/datamodell.md` innan du tolkar fält. Den beskriver kopplingar, filter som
inte fungerar och hur finansieringsform ska tolkas.

## Arbetsgång

1. **Hämta till cache en gång** (HS tar ca 4 min, ca 20 MB komprimerat):
   ```bash
   python scripts/susa.py fetch --cache data/hs --school-type HS
   ```
   Andra skolformer: `--school-type YH FHS` m.fl. (se `references/kodlistor.md`).
   Bara tillfällen för ett lärosäte går snabbare med `--provider p.uoh.kth`, men infos hämtas
   ändå för hela skolformen (API:et kan inte filtrera dem på anordnare).
2. **Uppdatera** befintlig cache (sekunder):
   ```bash
   python scripts/susa.py sync --cache data/hs
   ```
   Hämtar ändringar sedan senaste synk (minus ett dygns marginal) och tar bort raderade poster.
3. **Platta till** – en rad per utbildningstillfälle med utbildning och anordnare inkopplade:
   ```bash
   python scripts/susa.py flatten --cache data/hs --out kth.csv --provider p.uoh.kth
   python scripts/susa.py flatten --cache data/hs --out hs.parquet --with-text   # med beskrivning/behörighet
   ```
   CSV skrivs med BOM så att Excel visar åäö rätt. Parquet kräver pandas + pyarrow.
4. **Analysera** tabellen med pandas eller importera `susa` som modul:
   ```python
   import sys; sys.path.insert(0, "scripts"); import susa
   rows = susa.flatten_cache("data/hs", provider=["p.uoh.kth", "p.uoh.cth"])
   ```

Övrigt: `susa.py providers --school-type HS` listar anordnar-id; `susa.py get infos <id>` hämtar en post.
Anordnar-id för alla lärosäten finns i `references/anordnare_hs.csv` (KTH = `p.uoh.kth`).

## Vägledande matchning av utbildningar

Använd detta arbetssätt när en person söker utbildning utifrån sin kompetens eller vill utforska nästa steg i arbetslivet. Börja med uppgifterna personen redan har lämnat. För en vanlig fråga om utbildningsutbud, använd arbetsgången ovan.

1. **Utforska riktningen.** Utgå från det mål personen har angett. Om riktningen behöver förtydligas, fråga vad personen vill kunna göra efter utbildningen och vilka delar av arbetet hen vill bygga vidare på. Om målet är öppet, formulera två eller tre möjliga riktningar utifrån personens berättelse och be personen reagera på dem. Ställ en eller två frågor åt gången där svaren kan ändra sökningen. Fråga om studietakt, distans, ort eller tidpunkt när sådana villkor styr urvalet.
2. **Fånga vad personen kan i dag.** Be vid behov om ett konkret exempel på ett projekt, ett problem eller ett ansvar och vad personen själv gjorde. Ta med även tidigare roller och branschbyten, senare kurser, fortbildning, certifieringar och lärande i arbetet. Väg kunskaper efter hur de kan användas i den tänkta riktningen, på vilken nivå personen har tillämpat dem och hur nyligen. Ge grundexamen den vikt dess innehåll och roll för behörigheten motiverar. Hämta aldrig kompetenser ur enbart en examen, titel eller ett antal yrkesår. Spegla kort vilka styrkor och överförbara kunskaper du uppfattat. Markera antaganden och låt personen korrigera dem.
3. **Sök på kompetenser och lärandemål.** Översätt profilen till ämnen, arbetsuppgifter och närliggande söktermer. Pröva fördjupning i nuvarande riktning och närliggande områden där kunskaperna går att använda. Om personen överväger ett byte, sök efter utbildningar som överbryggar konkreta kunskapsluckor. Använd `--with-text` för att söka i beskrivningar och läsa behörighetskrav och rekommenderade förkunskaper. Sök över relevanta anordnare och utbildningsformer utifrån personens mål. Kontrollera aktuellt utbildningstillfälle, ansökningsuppgifter och eventuella obligatoriska träffar när de påverkar valet. Kontrollera att en kurs är sökbar fristående om det är ett krav. Om uppgifterna saknas i Susa-navet, använd anordnarens publicerade information när den är tillgänglig.
4. **Motivera träffarna och håll isär relevans och behörighet.** Beskriv för varje förslag vilken konkret erfarenhet kursen bygger på, vad personen kan lära sig och vilka krav eller praktiska frågor som behöver kontrolleras. Ange anordnare, aktuellt tillfälle och direktlänk när uppgifterna finns. Redovisa ansökningsstatus som okänd om den saknar stöd i källorna. Vid oklar behörighet, peka ut vilket krav som behöver kontrolleras. Nämn möjligheten att fråga lärosätet om bedömning av reell kompetens där det är relevant. Låt goda ämnesmässiga träffar stå kvar med den osäkerheten synlig. Vid tunt underlag, ge preliminära sökspår och en riktad följdfråga. Presentera en verifierad kortlista när underlaget räcker.

Exempel på en första följdfråga efter flera yrkesbyten: ”Vilken del vill du utveckla vidare: att leda förändringsarbetet, att arbeta närmare tekniken eller något annat? Kan du ge ett exempel på ett projekt där du trivdes med ditt ansvar?”

## Kolumner i den tillplattade tabellen

`event_id, provider_id, provider_name, education_id, kod, titel_sv, titel_en, typ` (kurs/program/kurspaket)`,
niva, poang, poangsystem, leder_till_examen, examen, amnen_uh, start, slut, starttermin` (t.ex. HT2026)`,
startperiod, startvecka, studietakt_pct, studietid, undervisningssprak, studieort, kommunkod, distans,
obligatoriska_traffar, it_distans, anmalningskod, sista_anmalan, antagningsomgang, urvalsmodell,
antal_platser, institution, finansieringsform, studieavgift, avgift_forsta, avgift_total,
synlig_internationellt, endast_inom_program, installd, url_sv, url_en, nyckelord,
senast_andrad_tillfalle, senast_andrad_utbildning` (+ `beskrivning_sv, behorighet_sv, forkunskaper_sv` med `--with-text`).

## Regler för analys

- **Räkna rätt enhet.** En rad = ett tillfälle. Unika kurser = unika (`provider_id`, `kod`). Säg vilken
  enhet du räknar.
- **Inställda tillfällen** (`installd = True`) finns kvar; exkludera dem för utbudsfrågor
  (`--exclude-cancelled`) och säg att du gjort det.
- **Finansieringsform är lokal.** Bara `ORD` betyder samma sak överallt. Tolka andra koder per
  lärosäte med `references/finansieringsformer_hs.csv`, och redovisa tolkningen som härledd.
  KTH:s `LL` (fortbildningskurser) är det närmaste ett mått på LLL-utbudet; för andra lärosäten krävs
  kombination av kod och titel.
- **Polisutbildningen** (`p.pu.e3.*`) har lärosätesnamn men Polismyndigheten som huvudman – exkludera
  eller redovisa separat vid jämförelser mellan lärosäten.
- **Ögonblicksbild.** API:et visar aktuellt utbud, inte historik. Ange hämtdatum (`meta.json`,
  `fetched_at`/`last_sync`) i varje redovisning. För tidsserier: spara daterade kopior av cachen eller
  den tillplattade tabellen.
- **Platsantal** (`antal_platser`) är ofta 999 eller saknas – använd inte som kapacitetsmått utan förbehåll.
- Ange källan som ”Susa-navet (Skolverket/UHR), hämtat ÅÅÅÅ-MM-DD”. Licens: CC0.

## Veckovisa ögonblicksbilder (historik)

GitHub Actions-flödet `.github/workflows/susa-snapshot.yml` i repot dr-ajson/SUSA körs varje måndag
(och manuellt via *Run workflow*). Det gör en full hämtning av HS och sedan:
- **Release `susa-hs-ÅÅÅÅ-MM-DD`** med hela tabellen `hs_<datum>.csv.gz` (alla kolumner ovan utom fritext).
  Hämta en bild: `gh release download susa-hs-2026-11-24 -R dr-ajson/SUSA -p 'hs_*.csv.gz'`.
- **`snapshots/sammanstallning.csv`** – tidsserie per lärosäte och datum: tillfallen, installda,
  utbildningar, kurser, program, kurspaket, distans, deltid, kvall_helg_blandad, engelska,
  ej_ord_finansiering, ll_kth. Räknat på ej inställda tillfällen; utbildningar = unika (kod, typ).
- **`snapshots/andringar/<datum>.md`** – nya och försvunna utbildningar jämfört med föregående vecka.

För frågor om utveckling över tid: börja i `sammanstallning.csv`; gå till release-filerna för detaljer.
Historiken börjar vid första körningen – äldre utbud kan inte återskapas ur API:et.
Lokalt: `python scripts/snapshot.py --cache data/hs --out-dir out --repo-dir . --previous <föregående>.csv.gz`.

## Koppling till sektordatabasen

För att kombinera utbud med ekonomi- och personaldata (skillen `se-uoh-analys`): matcha på
lärosätets namn via `references/anordnare_hs.csv` (Susa-navets namn, t.ex. ”Kungl. Tekniska högskolan”,
kan skilja sig från UKÄ:s). Kontrollera matchningen för varje lärosäte i stället för att anta den.
