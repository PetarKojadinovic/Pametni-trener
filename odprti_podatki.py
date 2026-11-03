"""Spletna aplikacija s statistiko telesne dejavnosti in telesne mase (SURS, PC-Axis).

Ob vsakem nalaganju strani zaledje s portala SI-STAT prenese datoteke PX,
jih razčleni (pxparser.py), obdela (seštevki, združevanje regij, izračun ITM)
in vrne JSON, ki ga stran web/index.html izriše s Chart.js.

Zagon:  python odprti_podatki.py        nato odpri http://localhost:8000
"""

import argparse
import json
import pathlib
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pxparser

KORENSKA = pathlib.Path(__file__).resolve().parent
SPLET = KORENSKA / "web"
PREDPOMNILNIK = KORENSKA / "data" / "px"
PX_URL = "https://pxweb.stat.si/SiStatData/Resources/PX/Databases/Data/{}.px"
STRAN_URL = "https://pxweb.stat.si/SiStatData/pxweb/sl/Data/-/{}.px"

TABELE = {
    "aktivnost": "0887601S",  # pogostost športne aktivnosti po spolu in starosti
    "aktivnost_regije": "0887602S",  # pogostost športne aktivnosti po regijah
    "telo": "0889301S",  # povprečna višina in teža po spolu in starosti
    "itm": "0889302S",  # kategorije ITM po spolu in starosti
    "itm_regije": "0889308S",  # kategorije ITM po regijah
}

# Kode pogostosti 1-4 pomenijo vsaj enkrat na teden.
KODE_REDNO = {"1", "2", "3", "4"}
# Kode ITM: 3 = čezmerna hranjenost, 4 = debelost.
KODE_PREKOMERNO = {"3", "4"}


def prenesi(matrika, casovna_omejitev=20):
    """Prenese datoteko PX; ob napaki uporabi zadnjo shranjeno kopijo."""
    pot = PREDPOMNILNIK / f"{matrika}.px"
    try:
        zahteva = urllib.request.Request(
            PX_URL.format(matrika), headers={"User-Agent": "PametniTrener/1.0 (studijski projekt)"}
        )
        with urllib.request.urlopen(zahteva, timeout=casovna_omejitev) as odgovor:
            vsebina = odgovor.read()
        pxparser.razcleni(vsebina)  # v predpomnilnik shranimo samo veljavno datoteko
        PREDPOMNILNIK.mkdir(parents=True, exist_ok=True)
        pot.write_bytes(vsebina)
        return vsebina, "SI-STAT (sveže)"
    except Exception as napaka:  # omrežje ali neveljavna vsebina
        if pot.exists():
            print(f"Opozorilo: {matrika} ni bilo mogoče prenesti ({napaka}), uporabljam kopijo")
            return pot.read_bytes(), "lokalna kopija"
        raise


def _spremenljivka(tabela, zacetek):
    """Poišče ime spremenljivke po začetku imena (npr. 'POGOSTOST')."""
    for ime in tabela.spremenljivke:
        if ime.startswith(zacetek):
            return ime
    raise KeyError(f"{tabela.matrika}: ni spremenljivke {zacetek}")


def _kode_v_besedila(tabela, ime, kode):
    return [b for b, k in zip(tabela.vrednosti[ime], tabela.kode[ime]) if k in kode]


def obdelaj_aktivnost(t):
    """Porazdelitev pogostosti in delež redno aktivnih (vsaj 1x na teden) po letu, spolu, starosti."""
    pog = _spremenljivka(t, "POGOSTOST")
    redno = _kode_v_besedila(t, pog, KODE_REDNO)
    nikoli = _kode_v_besedila(t, pog, {"6"})
    rezultat = {}
    for leto in t.vrednosti["LETO"]:
        for spol in t.vrednosti["SPOL"]:
            for starost in t.vrednosti["STAROSTNA SKUPINA"]:
                izbor = {"LETO": leto, "SPOL": spol, "STAROSTNA SKUPINA": starost}
                porazdelitev = {p: t.vrednost(**izbor, **{pog: p}) for p in t.vrednosti[pog]}
                rezultat.setdefault(leto, {}).setdefault(spol, {})[starost] = {
                    "porazdelitev": porazdelitev,
                    "redno": _vsota(porazdelitev[p] for p in redno),
                    "nikoli": _vsota(porazdelitev[p] for p in nikoli),
                }
    return {
        "leta": t.vrednosti["LETO"],
        "spoli": t.vrednosti["SPOL"],
        "starosti": t.vrednosti["STAROSTNA SKUPINA"],
        "pogostosti": t.vrednosti[pog],
        "podatki": rezultat,
    }


def obdelaj_regije(akt, itm):
    """Združi tabeli po imenu statistične regije: delež redno aktivnih in delež s prekomerno težo."""
    reg_a = _spremenljivka(akt, "STATISTIČNA")
    pog = _spremenljivka(akt, "POGOSTOST")
    reg_i = _spremenljivka(itm, "KOHEZIJSKA")
    kat = _spremenljivka(itm, "KATEGORIJE")
    redno = _kode_v_besedila(akt, pog, KODE_REDNO)
    prekomerno = _kode_v_besedila(itm, kat, KODE_PREKOMERNO)

    skupna_leta = [l for l in akt.vrednosti["LETO"] if l in itm.vrednosti["LETO"]]
    # Kohezijski regiji (koda z eno števko, razen 0 = Slovenija) izpustimo.
    regije = [
        r for r, k in zip(itm.vrednosti[reg_i], itm.kode[reg_i]) if len(k) == 2 or k == "0"
    ]
    regije = [r for r in regije if r in akt.vrednosti[reg_a]]

    rezultat = {}
    for leto in skupna_leta:
        vrstice = []
        for regija in regije:
            vrstice.append({
                "regija": regija,
                "redno": _vsota(akt.vrednost(LETO=leto, **{reg_a: regija, pog: p}) for p in redno),
                "prekomerno": _vsota(
                    itm.vrednost(LETO=leto, **{reg_i: regija, kat: k}) for k in prekomerno
                ),
                "debelost": itm.vrednost(LETO=leto, **{reg_i: regija, kat: prekomerno[-1]}),
            })
        rezultat[leto] = vrstice
    return {"leta": skupna_leta, "podatki": rezultat}


def obdelaj_itm(t):
    kat = _spremenljivka(t, "KATEGORIJE")
    rezultat = {}
    for zapis in t.zapisi():
        (rezultat.setdefault(zapis["SPOL"], {})
         .setdefault(zapis["STAROSTNA SKUPINA"], {})
         .setdefault(zapis[kat], {}))[zapis["LETO"]] = zapis["vrednost"]
    return {
        "leta": t.vrednosti["LETO"],
        "kategorije": t.vrednosti[kat],
        "spoli": t.vrednosti["SPOL"],
        "starosti": t.vrednosti["STAROSTNA SKUPINA"],
        "podatki": rezultat,
    }


def obdelaj_telo(t):
    """Povprečna višina in teža ter iz njiju izračunan ITM = teža / višina[m]^2."""
    mera = _spremenljivka(t, "VIŠINA")
    visina, teza = t.vrednosti[mera]
    rezultat = {}
    for leto in t.vrednosti["LETO"]:
        for spol in t.vrednosti["SPOL"]:
            for starost in t.vrednosti["STAROSTNA SKUPINA"]:
                izbor = {"LETO": leto, "SPOL": spol, "STAROSTNA SKUPINA": starost}
                v = t.vrednost(**izbor, **{mera: visina})
                m = t.vrednost(**izbor, **{mera: teza})
                itm = round(m / (v / 100) ** 2, 1) if v and m else None
                rezultat.setdefault(leto, {}).setdefault(spol, {})[starost] = {
                    "visina": v, "teza": m, "itm": itm,
                }
    return {
        "leta": t.vrednosti["LETO"],
        "spoli": t.vrednosti["SPOL"],
        "starosti": t.vrednosti["STAROSTNA SKUPINA"],
        "podatki": rezultat,
    }


def _vsota(vrednosti):
    vrednosti = list(vrednosti)
    if any(v is None for v in vrednosti):
        return None
    return round(sum(vrednosti), 1)


def zberi_podatke():
    """Prenese vse tabele hkrati, jih razčleni in obdela v en JSON objekt."""
    with ThreadPoolExecutor(max_workers=len(TABELE)) as izvajalec:
        preneseno = dict(zip(TABELE, izvajalec.map(prenesi, TABELE.values())))
    tabele = {ime: pxparser.razcleni(vsebina) for ime, (vsebina, _) in preneseno.items()}
    return {
        "pridobljeno": datetime.now().isoformat(timespec="seconds"),
        "viri": [
            {
                "matrika": t.matrika,
                "naslov": t.naslov,
                "posodobljeno": t.posodobljeno,
                "vir": preneseno[ime][1],
                "url": STRAN_URL.format(t.matrika),
            }
            for ime, t in tabele.items()
        ],
        "aktivnost": obdelaj_aktivnost(tabele["aktivnost"]),
        "regije": obdelaj_regije(tabele["aktivnost_regije"], tabele["itm_regije"]),
        "itm": obdelaj_itm(tabele["itm"]),
        "telo": obdelaj_telo(tabele["telo"]),
    }


class Obdelovalec(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SPLET), **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] != "/api/podatki":
            return super().do_GET()
        try:
            telo, status = json.dumps(zberi_podatke(), ensure_ascii=False).encode("utf-8"), 200
        except Exception as napaka:
            telo = json.dumps({"napaka": str(napaka)}, ensure_ascii=False).encode("utf-8")
            status = 502
        self._poslji_json(telo, status)

    def do_POST(self):
        """POST /api/nacrt: podatki obrazca -> dinamičen prompt -> Claude -> NacrtVadbe (JSON)."""
        if self.path.split("?")[0] != "/api/nacrt":
            self.send_error(404)
            return
        try:
            import llm_nacrt  # potrebuje paket anthropic samo za to funkcijo
            from pydantic import ValidationError

            dolzina = min(int(self.headers.get("Content-Length", 0)), 10_000)
            try:
                vnos = llm_nacrt.VnosUporabnika.model_validate_json(self.rfile.read(dolzina))
            except ValidationError as napaka:
                polja = ", ".join(".".join(map(str, e["loc"])) for e in napaka.errors())
                raise ValueError(f"Neveljaven vnos: {polja}")
            nacrt = llm_nacrt.pridobi_nacrt(vnos)
            odgovor = {"nacrt": nacrt.model_dump(), "model": llm_nacrt.MODEL,
                       "prompt": llm_nacrt.sestavi_prompt(vnos),
                       "statistika": {"vaj": nacrt.stevilo_vaj(), "iz_baze": nacrt.iz_baze()}}
            telo, status = json.dumps(odgovor, ensure_ascii=False).encode("utf-8"), 200
        except ValueError as napaka:
            telo, status = json.dumps({"napaka": str(napaka)}, ensure_ascii=False).encode("utf-8"), 400
        except Exception as napaka:  # NapakaLLM, manjkajoč paket ...
            telo, status = json.dumps({"napaka": str(napaka)}, ensure_ascii=False).encode("utf-8"), 502
        self._poslji_json(telo, status)

    def _poslji_json(self, telo, status):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(telo)))
        self.end_headers()
        self.wfile.write(telo)


def main():
    parser = argparse.ArgumentParser(description="Vizualizacija odprtih podatkov SURS (PC-Axis)")
    parser.add_argument("--vrata", type=int, default=8000, help="vrata strežnika (privzeto 8000)")
    parser.add_argument("--izvoz", metavar="DATOTEKA",
                        help="namesto strežnika samo shrani obdelane podatke v JSON")
    args = parser.parse_args()

    if args.izvoz:
        pathlib.Path(args.izvoz).write_text(
            json.dumps(zberi_podatke(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Shranjeno v {args.izvoz}")
        return

    streznik = ThreadingHTTPServer(("127.0.0.1", args.vrata), Obdelovalec)
    print(f"Aplikacija teče na http://localhost:{args.vrata} (Ctrl+C za izhod)")
    try:
        streznik.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
