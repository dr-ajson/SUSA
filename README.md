# SUSA-navet

[Skillen Susa-navet](skills/susa-navet/SKILL.md) hämtar, synkar och analyserar svenskt utbildningsutbud från Skolverkets öppna API.

## Använda skillen

Installera hela ZIP-paketet med instruktioner, skript och en daterad kopia av utbudet. Katalogen hämtar senaste [publicerade ögonblicksbild](snapshots/latest.json) automatiskt från det öppna repot. En installation kan därmed använda nya data utan att uppdatera själva skillen. Om körmiljön saknar nätåtkomst används den medföljande bilden, och svaret ska ange datumet. Ingen GitHub-inloggning eller anslutning behövs för den publika hämtningen.

## Veckovisa ögonblicksbilder

[GitHub Actions](.github/workflows/susa-snapshot.yml) hämtar utbudet varje måndag 04:17 UTC och kan köras manuellt. När alla filer är publicerade uppdaterar flödet datumet i katalogen. Varje skolform får en daterad [release](https://github.com/dr-ajson/SUSA/releases) med en komprimerad CSV. Filen innehåller utbildningsbeskrivning, behörighetskrav och rekommenderade förkunskaper där uppgifterna finns i källan.

| Kod | Utbud |
|---|---|
| HS | Universitet, högskolor och polisutbildning |
| YH | Yrkeshögskolan |
| FHS | Folkhögskolan, flera utbildningsnivåer |
| KKU | Konst- och kulturutbildningar |
| AU | Annan undervisning, däribland utbildningar med endast tillsyn |
| AUB | Arbetsförmedlingens utbildningar, flera utbildningsnivåer |

Release och fil heter `susa-<kod>-ÅÅÅÅ-MM-DD` respektive `<kod>_ÅÅÅÅ-MM-DD.csv.gz`, med kod i gemener. Tidsserier och ändringsrapporter finns i `snapshots/` för HS och `snapshots/<kod>/` för de övriga. Den första [HS-bilden från 24 november 2026](https://github.com/dr-ajson/SUSA/releases/tag/susa-hs-2026-11-24) finns kvar i sitt ursprungliga format.

Ögonblicksbilderna återger utbudet som källan publicerar vid hämtningen. För FHS och AUB behöver utbildningsnivån bedömas per post. Förutbildning inom HS redovisas med sin egen nivå. Nationell yrkesutbildning (NY) är gymnasial. För utbildningar med endast tillsyn kan [MYH:s utbudslista](https://www.myh.se/statistik/statistik-utbildningar-med-endast-tillsyn/utbildningar-och-platser) komplettera API:et.

Ladda ner rätt releasefil, packa upp CSV-filen och bifoga den för analys i ChatGPT. Det fungerar även utan att ansluta GitHub till ChatGPT.
