---
name: susa-navet
description: Hämta och analysera svenskt utbildningsutbud från Susa-navet (Skolverkets/UHR:s öppna API) – kurser, program och utbildningstillfällen vid universitet och högskolor, YH, folkhögskolor och Komvux. Använd för frågor om ett lärosätes utbud, jämförelser av utbud mellan lärosäten, fristående kurser, distans, studietakt, livslångt lärande, Lärarlyftet, studieavgifter eller anmälningskoder, och för att bygga eller uppdatera en lokal kopia av utbudet. Använd också för vägledande matchning mot utbildningar utifrån yrkeserfarenhet, vidareutbildning och karriärmål. Use for any question about current Swedish course/programme offerings, even if Susa-navet is not named.
---

# Susa-navet

Öppet REST-API utan nyckel: `https://api.skolverket.se/susa-navet/emil3` (v3, data uppdateras dagligen).
Läs `references/datamodell.md` när en fråga kräver tolkning av datafält, finansieringsform eller API-filter.

## Hitta utbildningar direkt efter installationen

Använd `python3 scripts/catalog.py search` från den installerade skillens mapp för frågor om utbildningsutbud och vägledande matchning. Skriptet kontrollerar automatiskt det senaste publicerade datumet i det öppna SUSA-repot. Det hämtar bara de skolformer som ska genomsökas och använder den medföljande ögonblicksbilden om hämtningen är otillgänglig. Användaren behöver bara installera skillen och ställa sin fråga. Be inte om en GitHub-koppling, manuell hämtning eller en bifogad datafil innan du prövat den vägen. Om användaren uttryckligen vill arbeta utan nätåtkomst, lägg till `--bundled` för att använda den medföljande kopian direkt.

```bash
python3 scripts/catalog.py search --school-type YH --query "produktionsplanering" --query "projektledning industri"
python3 scripts/catalog.py search --school-type HS YH --query "dataanalys" --provider "Tekniska" --limit 10
```

Inom varje `--query` ska alla ord matcha. Upprepa flaggan för alternativa termer. Träffar söks i titlar, utbildningsbeskrivningar och nyckelord. Utgå från personens mål och använd den vägledande arbetsgången nedan för att pröva och bedöma lämpliga spår. Sök bredare om de första termerna ger få träffar. Använd skolform för att avgränsa sökningen när personen redan har valt utbildningsslag.

Ange datum och källa enligt `kallor` i resultatet. Om en medföljande ögonblicksbild använts, säg att resultatet avser den daterade bilden och att nyare ändringar eller ansökningsstatus kan behöva kontrolleras. Om miljön varken kan köra skript eller läsa den medföljande datan, använd tillgänglig webbsökning för att kontrollera utbildningar hos ansvariga anordnare. Redovisa de skolformer som inte kunde sökas. För fullständig export, egna tidsserier eller kontroll i realtid, använd arbetsgången nedan när den fungerar.

## Direkt API-hämtning och egna analyser

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

Använd detta arbetssätt när en person söker utbildning utifrån sin kompetens eller vill utforska nästa steg i arbetslivet. Börja med uppgifterna personen redan har lämnat. För en vanlig fråga om utbildningsutbud, gå direkt till katalogsökningen.

1. **Utforska riktningen.** Utgå från vad personen vill kunna göra efter utbildningen. Om målet är öppet, föreslå två eller tre möjliga riktningar utifrån personens berättelse och be personen reagera. Ställ en eller två frågor åt gången om uppgifter som kan ändra sökningen, exempelvis önskade arbetsuppgifter eller krav på studietakt, distans, ort eller tidpunkt. Gå direkt till sökning när uppgifterna räcker för ett användbart urval. När personen förtydligar eller korrigerar något, uppdatera din tolkning av målet och profilen. Justera söktermer, utbildningsspår eller rangordning där svaret påverkar dem, och säg kort vad som ändrades och varför.
2. **Fånga vad personen kan i dag.** Fråga vid behov om ett konkret projekt, ett problem eller ett ansvar och vad personen själv gjorde. Ta med relevanta tidigare roller och branschbyten, senare kurser, fortbildning, certifieringar och lärande i arbetet. Väg kompetensen efter kopplingen till målet, graden av självständighet och ansvar i tillämpningen, hur den kan överföras och hur nyligen den användes. Låt nyare, konkret tillämpad kompetens väga tyngre när den har starkare koppling till målet. Ge äldre utbildning vikt för relevansen när innehållet bidrar konkret till målet. Bedöm examens betydelse för formell behörighet separat. Slutsatser om kompetens behöver underlag utöver examenstitel, yrkestitel och antal yrkesår. Spegla kort vilka styrkor och överförbara kunskaper du uppfattat. Markera antaganden så att personen kan korrigera dem.
3. **Sök på kompetenser och lärandemål.** Översätt profilen till ämnen, arbetsuppgifter och närliggande söktermer. Pröva fördjupning i nuvarande riktning och närliggande områden där kunskaperna går att använda. Om personen överväger ett byte, sök efter utbildningar som överbryggar konkreta kunskapsluckor. Sök i katalogens beskrivningar och läs behörighetskrav och rekommenderade förkunskaper. Använd `--with-text` om du tillplattar en cache från API:et. Sök över relevanta anordnare och utbildningsformer utifrån personens mål. Kontrollera aktuellt utbildningstillfälle, ansökningsuppgifter och eventuella obligatoriska träffar när de påverkar valet. Kontrollera att en kurs är sökbar fristående om det är ett krav. Om uppgifterna saknas i Susa-navet, använd anordnarens publicerade information när den är tillgänglig.
4. **Motivera träffarna och redovisa behörighetsunderlaget.** Rangordna träffarna efter hur väl de svarar mot målet och de praktiska villkor personen angett. Redovisa två uppgifter för varje träff.
   - **Relevans.** Ange vilket lärandemål som passar, vilken konkret kompetens utbildningen bygger vidare på och vilken kunskapslucka den kan fylla.
   - **Behörighetsunderlag.** Ange vad källan säger om aktuella behörighetskrav och eventuella rekommenderade förkunskaper. Beskriv vilka krav personens uppgifter tyder på att hen uppfyller och vilket krav eller underlag som återstår att kontrollera. Markera när uppgifterna om ett krav saknas. Låt ämnesmässigt starka träffar stå kvar vid osäkerhet och hänvisa vid behov till ansvarig utbildningsanordnare eller antagningsfunktion för bedömning av reell kompetens.

   Ange anordnare, aktuellt tillfälle och direktlänk till utbildningen när den finns. Länka också till anordnarens kursplan, utbildningsplan eller motsvarande fördjupade beskrivning när den går att hitta. Använd dokumentet för att belägga innehåll, lärandemål och förkunskapskrav vid en djupare matchning. Sök hos ansvarig anordnare när ögonblicksbilden saknar direktlänk. Märk en ansökningslänk som sådan. Redovisa ansökningsstatus som okänd om den saknar stöd i källorna. Vid tunt underlag, ge preliminära sökspår och en riktad följdfråga. Ge en kortlista när underlaget räcker och ange vad som har kontrollerats i källorna, exempelvis utbildningstillfälle, ansökningsstatus och publicerade krav. En kontroll av de publicerade kraven är underlag för vägledning. Ett individuellt behörighetsbesked ges av ansvarig antagningsfunktion.

**Exempel i två turer.** En inredningssnickare nämner projektledning och AI. Fråga: ”Vill du främst leda uppdrag och samordna människor, eller använda data och AI för att planera produktionen?” Personen svarar att målet är att planera maskinbeläggning och leveranser och att hen redan samordnar jobb i verkstaden. Prioritera då produktionsplanering och tillämpat datastöd före allmän projektledning. Om en relevant utbildning har ett publicerat krav som personens uppgifter ännu inte täcker, behåll träffen och ange exakt vad som behöver kontrolleras.

## Kolumner i den tillplattade tabellen

`event_id, provider_id, provider_name, education_id, kod, titel_sv, titel_en, typ` (kurs/program/kurspaket)`,
niva, poang, poangsystem, leder_till_examen, examen, amnen_uh, start, slut, starttermin` (t.ex. HT2026)`,
startperiod, startvecka, studietakt_pct, studietid, undervisningssprak, studieort, kommunkod, distans,
obligatoriska_traffar, it_distans, anmalningskod, sista_anmalan, antagningsomgang, urvalsmodell,
antal_platser, institution, finansieringsform, studieavgift, avgift_forsta, avgift_total,
synlig_internationellt, endast_inom_program, installd, url_sv, url_en, ansokningsurl_sv, nyckelord,
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

Katalogen läser [senaste publicerade datum](https://raw.githubusercontent.com/dr-ajson/SUSA/main/snapshots/latest.json) automatiskt. För historiska jämförelser finns filer för varje skolform på https://github.com/dr-ajson/SUSA/releases. Varje ny ögonblicksbild har en release `susa-<kod>-ÅÅÅÅ-MM-DD` med filen `<kod>_ÅÅÅÅ-MM-DD.csv.gz` (gemener). De nya filerna innehåller utbildningsbeskrivning, behörighetskrav och rekommenderade förkunskaper där källan tillhandahåller dem.

| Kod | Utbud som hämtas |
|---|---|
| HS | Universitet, högskolor och polisutbildning |
| YH | Yrkeshögskolans program, kurser och kurspaket som finns i API:et |
| FHS | Folkhögskolans utbud på olika nivåer |
| KKU | Konst- och kulturutbildningar |
| AU | Annan undervisning, däribland utbildningar med endast tillsyn |
| AUB | Arbetsförmedlingens utbildningar på olika nivåer |

För strikt eftergymnasiala urval, kontrollera nivå och behörighetskrav per utbildning i FHS och AUB, samt HS-poster märkta förutbildning. Redovisa okänd nivå separat. NY är nationell yrkesutbildning på gymnasial nivå. För endast tillsyn kan [MYH:s utbudslista](https://www.myh.se/statistik/statistik-utbildningar-med-endast-tillsyn/utbildningar-och-platser) komplettera API-posterna.

För historiska jämförelser, använd samma skolform. Tidsserier och ändringsrapporter finns i `snapshots/` för HS och `snapshots/<kod>/` för de övriga. Historiken börjar vid första hämtningen för respektive skolform. Den ursprungliga HS-bilden har inga fritextkolumner.

## Koppling till sektordatabasen

För att kombinera utbud med ekonomi- och personaldata (skillen `se-uoh-analys`): matcha på
lärosätets namn via `references/anordnare_hs.csv` (Susa-navets namn, t.ex. ”Kungl. Tekniska högskolan”,
kan skilja sig från UKÄ:s). Kontrollera matchningen för varje lärosäte i stället för att anta den.
