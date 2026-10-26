# Pametni trener – obdelava XML dokumentov

Preprosta Python aplikacija, ki prebere tri povezane XML datoteke s podatki o treningih v telovadnici, jih poveže prek ID-jev, filtrira in rezultate izvozi v JSON in XML. Podatkovni model je zasnovan kot osnova za zaledni sistem projekta »Pametni trener«.

## Struktura

```
data/
  uporabniki.xml   12 uporabnikov
  vaje.xml         15 vaj
  treningi.xml     18 treningov
main.py            aplikacija
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
