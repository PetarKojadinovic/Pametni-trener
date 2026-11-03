# Pametni trener – obdelava XML dokumentov

Preprosta Python aplikacija, ki prebere tri povezane XML datoteke s podatki o treningih v telovadnici, jih poveže prek ID-jev, filtrira in rezultate izvozi v JSON in XML. Podatkovni model je zasnovan kot osnova za zaledni sistem projekta »Pametni trener«.

## Struktura

```
data/
  uporabniki.xml   12 uporabnikov
  vaje.xml         15 vaj
  treningi.xml     18 treningov
  vaje_splet.json  vaje, pridobljene s spletne strani (nastane ob zagonu scraper.py)
  vaje_splet.xml   isti podatki v XML (nastane ob zagonu scraper.py)
main.py            filtriranje in izvoz XML podatkov
scraper.py         razčlenjevalnik spletne strani z vajami
test_scraper.py    preizkusi razčlenjevalnika (brez omrežja)
requirements.txt   knjižnice za scraper.py in llm_nacrt.py
pxparser.py        razčlenjevalnik datotek PC-Axis (.px)
odprti_podatki.py  spletna aplikacija z odprtimi podatki SURS
test_pxparser.py   preizkusi razčlenjevalnika PX (brez omrežja)
web/index.html     stran z grafi (Chart.js)
llm_nacrt.py       načrt vadbe z LLM (Claude API, strukturiran JSON)
test_llm_nacrt.py  preizkusi prompta in deserializacije (brez omrežja)
web/nacrt.html     obrazec in prikaz načrta vadbe
data/px/           zadnje prenesene datoteke PX (rezerva, če SI-STAT ni dosegljiv)
primer_izhoda/
  filtrirano.json  primer izvoza v JSON
  filtrirano.xml   primer izvoza v XML
```

## Podatki in povezave

| Datoteka | Entiteta | Atributi in polja |
|---|---|---|
| `uporabniki.xml` | `uporabnik` | `id`; ime, priimek, email, datumRegistracije, cilj, teza |
| `vaje.xml` | `vaja` | `id`; ime, misicnaSkupina, oprema, tezavnost, opis |
| `treningi.xml` | `trening` | `id`, `uporabnikId`, `vajaId`; datum, serije, ponovitve, tezaBremena, trajanjeMin |

Povezave: `trening/@uporabnikId` → `uporabnik/@id` in `trening/@vajaId` → `vaja/@id`.

Posebnosti podatkov:
- datumi so v obliki `YYYY-MM-DD`;
- številska polja: serije, ponovitve, teža, trajanje, težavnost;
- manjkajoči podatki: pri nekaterih uporabnikih polje `email` manjka, pri nekaterih vajah je `opis` prazen, pri vajah z lastno težo je `tezaBremena` prazna.

## Zagon

Zahteva Python 3.9 ali novejši, dodatnih knjižnic ni.

```
python main.py
python main.py --skupina noge --od 2026-09-01 --izhod primer_izhoda
python main.py --uporabnik u01
python main.py --min-teza 100
python main.py --oprema palica --do 2026-09-10
```

Filtri (lahko jih kombiniramo):

| Parameter | Pomen |
|---|---|
| `--uporabnik` | ID uporabnika (npr. `u01`) |
| `--skupina` | mišična skupina (npr. `noge`, `prsi`, `hrbet`) |
| `--oprema` | oprema (npr. `palica`, `ročke`, `brez`) |
| `--od`, `--do` | obdobje treningov (`YYYY-MM-DD`) |
| `--min-teza` | najmanjša teža bremena v kg (treningi brez teže se izločijo) |
| `--izhod` | mapa za izvoz (privzeto trenutna) |

## Kaj program naredi

1. Prebere vse tri XML datoteke in jih pretvori v objekte (`dataclass`).
2. Poveže treninge z uporabniki in vajami prek ID-jev (neobstoječe ID-je javi kot opozorilo).
3. Filtrira treninge po izbranih parametrih in jih izpiše v tabeli v konzoli.
4. Shrani rezultat v `filtrirano.json` (seznam objektov) in `filtrirano.xml` (samo filtrirani zapisi).

## Razčlenjevalnik spletne strani (`scraper.py`)

Program prebere imenik vaj na strani [StrengthLog](https://www.strengthlog.com/exercise-directory/), ki je povezana z našim projektom (baza vaj za načrte vadbe). Stran je statična, zato Puppeteer ni potreben; uporabljena sta `requests` (prenos) in `BeautifulSoup` (razčlenjevanje HTML).

Kaj razčleni:
1. **Imenik vaj**: iz razdelka »Muscle Directory« prebere skupine mišic (naslovi `h3`) in povezave do vaj (seznami `li/a`). Angleške skupine preslika v slovenske (`Chest` → `prsi`), enako kot v `vaje.xml`.
2. **Podstran vaje**: opis, primarne in sekundarne mišice ter korake izvedbe. Če podatka na strani ni, ostane prazen (podobno kot pri `opis` v `vaje.xml`).

Zagon (potrebna je enkratna namestitev knjižnic):

```
pip install -r requirements.txt
python scraper.py
python scraper.py --skupina prsi --na-skupino 5
python scraper.py --na-skupino 0 --zakasnitev 2
python scraper.py --brez-podrobnosti
```

| Parameter | Pomen |
|---|---|
| `--na-skupino` | največ vaj na mišično skupino (privzeto 3, `0` = vse) |
| `--skupina` | samo ena skupina (`prsi`, `noge`, `hrbet`, `ramena`, `roke`, `trebuh` …) |
| `--brez-podrobnosti` | samo imenik, brez prenosa podstrani |
| `--zakasnitev` | premor med zahtevki v sekundah (privzeto 1) |
| `--vhod-html` | razčleni shranjeno HTML datoteko imenika namesto prenosa |
| `--izhod` | mapa za izvoz (privzeto `data`) |

Izhod je v `data/vaje_splet.json` (seznam objektov) in `data/vaje_splet.xml`. Vsaka vaja ima unikaten `id` (`w001`, `w002` …), povezavo, skupino, mišice, korake in datum pridobitve (`YYYY-MM-DD`). Ti podatki so namenjeni prikazu vaj v končni aplikaciji.

Spoštovanje strani: program pred prenosom preveri `robots.txt`, med zahtevki počaka in se predstavi s svojim imenom (`User-Agent`). Če se zgradba strani spremeni, program javi jasno napako.

Preizkusi razčlenjevalnika (brez omrežja, na lokalnih HTML odlomkih):

```
python -m unittest -v test_scraper
```

## Odprti podatki Slovenije (`odprti_podatki.py`)

Aplikacija prikazuje statistiko telesne dejavnosti in telesne mase prebivalcev Slovenije, kar je neposredno povezano s projektom (vadba, telesna teža, ITM). Podatki so z [Nacionalnega portala odprtih podatkov](https://podatki.gov.si) oziroma iz podatkovne baze SURS [SI-STAT](https://pxweb.stat.si/SiStatData/pxweb/sl/Data/) in so v obliki **PC-Axis** (`.px`).

| Tabela | Vsebina |
|---|---|
| `0887601S` | pogostost športne ali rekreativne aktivnosti po spolu in starosti |
| `0887602S` | pogostost športne ali rekreativne aktivnosti po statističnih regijah |
| `0889301S` | povprečna telesna višina in teža po spolu in starosti |
| `0889302S` | kategorije indeksa telesne mase (ITM) po spolu in starosti |
| `0889308S` | kategorije ITM po statističnih regijah |

Delovanje:
1. Ob vsakem nalaganju strani (ali ob kliku »Osveži podatke«) zaledje vzporedno prenese vseh pet datotek PX s SI-STAT. Portal ne dovoli neposrednih zahtevkov iz brskalnika (CORS), zato prenos opravi Python strežnik.
2. `pxparser.py` datoteke razčleni brez zunanjih knjižnic: prebere kodno tabelo (`CODEPAGE`), spremenljivke (`STUB`, `HEADING`), vrednosti in kode ter večdimenzionalno matriko `DATA`. Oznake manjkajočih podatkov (`..`, `-`, `z` …) pretvori v prazne vrednosti.
3. Obdelava podatkov:
   - **agregacija:** delež redno aktivnih je seštevek kategorij od »dvakrat na dan« do »1 do 3-krat na teden«; prekomerna masa je seštevek čezmerne hranjenosti in debelosti;
   - **združevanje:** tabeli aktivnosti in ITM se povežeta po imenu statistične regije (kohezijske regije se izločijo);
   - **izpeljava:** iz povprečne višine in teže se izračuna ITM = teža / višina².
4. Stran `web/index.html` z [Chart.js](https://www.chartjs.org/) izriše kazalnike in pet grafov. Filtri (leto, spol, starostna skupina, razvrščanje regij) graf takoj posodobijo.

Če SI-STAT ni dosegljiv, aplikacija uporabi zadnjo uspešno preneseno kopijo iz `data/px/` in to označi na strani.

Zagon (dodatne knjižnice niso potrebne):

```
python odprti_podatki.py
python odprti_podatki.py --vrata 8080
python odprti_podatki.py --izvoz podatki.json
```

Nato odpremo `http://localhost:8000`. Parameter `--izvoz` namesto strežnika samo shrani obdelane podatke v JSON.

Preizkusi:

```
python -m unittest -v test_pxparser
```

## Načrt vadbe z LLM (`llm_nacrt.py`, `web/nacrt.html`)

Aplikacija uporabniku sestavi osebni tedenski načrt vadbe s pomočjo modela Claude (Anthropic, Claude API). Stran je dostopna na `http://localhost:8000/nacrt.html` (povezava je tudi na glavni strani).

**Vhodni podatki** (nič ni statično):
- obrazec: cilj (spustni meni), izkušnje, število treningov na teden, trajanje, oprema in mišične skupine (potrditvena polja), starost, teža, poškodbe/omejitve (besedilo);
- brskalnik: trenutni lokalni čas, dan v tednu in časovni pas (`Intl`), na podlagi katerih model razporedi treninge po datumih (po 18. uri se načrt začne naslednji dan);
- lastni podatki: vaje iz `data/vaje.xml`, filtrirane po izbrani opremi, ki jih model po možnosti uporabi in navede njihov ID.

**Dinamičen prompt:** `sestavi_prompt()` iz teh podatkov sestavi besedilo, npr.:

```
Cilj: povečati največjo moč (nizko število ponovitev, daljši počitki).
Vadi lahko 4-krat na teden, vsakič največ 45 minut ...
Razpoložljiva oprema: brez, drog. Ne predlagaj vaj, ki zahtevajo drugo opremo.
Danes je torek, 2026-11-03, ura 16:38 (Europe/Ljubljana). Načrt se lahko začne danes ...
- v04: Sklece (prsi, oprema: brez, težavnost 2/5)
- v05: Zgibe (hrbet, oprema: drog, težavnost 4/5)
```

**Strukturiran izhod (JSON):** model se kliče z `client.messages.parse(..., output_format=NacrtVadbe)`. API iz razreda ustvari shemo JSON in zagotovi, da odgovor ustreza shemi; SDK ga nato deserializira v objekte:

| Razred (Pydantic, `llm_nacrt.py`) | Polja |
|---|---|
| `NacrtVadbe` | naslov, povzetek, dnevi[], nasveti[], opozorila[] |
| `DanVadbe` | dan, datum, poudarek, trajanje_min, ogrevanje, vaje[], ohlajanje |
| `VajaNacrta` | ime, vaja_id (ID iz `vaje.xml` ali `null`), misicna_skupina, serije, ponovitve, pocitek_s, opomba |

Tudi vhod je razred (`VnosUporabnika`), ki preveri tipe in meje (npr. 1–6 dni, dovoljene vrednosti opreme). Na odjemalcu so v `web/nacrt.html` enaki razredi v JavaScriptu (`NacrtVadbe.izJson()`), iz katerih stran izriše načrt. Pod načrtom sta za preverjanje prikazana poslani prompt in prejeti JSON.

Zagon:

```
pip install -r requirements.txt
set ANTHROPIC_API_KEY=sk-ant-...        (PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-...")
python odprti_podatki.py
python llm_nacrt.py --cilj moč --dni 4 --oprema brez drog     # v konzoli
python llm_nacrt.py --samo-prompt                              # samo prompt, brez klica API
```

Privzeti model je `claude-opus-5-5`; drugega nastavimo z okoljsko spremenljivko `PAMETNI_MODEL` (npr. `claude-haiku-5-5` za cenejše preizkuse).

Preizkusi (brez klica API, z lažnim odjemalcem):

```
python -m unittest -v test_llm_nacrt
```
