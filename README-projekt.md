# Pametni trener

Mobilna aplikacija za fitnes in vadbo v telovadnici. Uporabniku sestavi osebni načrt vadbe, beleži treninge in napredek, spremlja prehrano ter treninge vpiše v koledar. Projekt temelji na integraciji več obstoječih spletnih storitev.

**Avtor:** Petar Kojadinović

## Integrirane storitve

| Storitev | Namen | Dokumentacija |
|---|---|---|
| wger REST API | baza vaj (opis, mišične skupine, oprema) | https://wger.readthedocs.io/en/latest/api/api.html |
| Open Food Facts API | hranilne vrednosti živil po črtni kodi | https://openfoodfacts.github.io/openfoodfacts-server/api/ |
| Google Calendar API | termini treningov v koledarju (OAuth 2.0) | https://developers.google.com/workspace/calendar/api/guides/overview |
| Claude API (Anthropic) | sestavljanje načrta vadbe in klepetalni asistent | https://docs.claude.com |

Vse storitve komunicirajo prek REST/HTTPS, podatki se izmenjujejo v obliki JSON.

## Podatki

- **Iz storitev:** vaje (wger), živila in hranilne vrednosti (Open Food Facts), koledarski dogodki (Google Calendar), načrti vadbe (Claude API).
- **Lastni podatki:** uporabnik in cilji, načrti vadbe, dnevnik treningov, dnevnik prehrane, dnevnik telesne teže, tedensko poročilo.

## Arhitektura

Uporabnik → mobilna aplikacija (React Native/Expo) → zaledni sistem (FastAPI) → zunanje storitve (wger, Open Food Facts, Google Calendar, Claude API).

Zaledni sistem je integracijska plast: mobilna aplikacija komunicira samo z njim, on pa kliče zunanje storitve in hrani lastno bazo.

## Dokumentacija

Popoln opis projekta (povzetek, storitve, podatki, akterji in diagram): [docs/Obrazec_TIDS_izpolnjen.docx](docs/Obrazec_TIDS_izpolnjen.docx)
