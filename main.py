"""Pametni trener – obdelava povezanih XML dokumentov.

Program prebere uporabniki.xml, vaje.xml in treningi.xml, jih poveže prek ID-jev,
filtrira treninge in rezultat izpiše v konzolo ter izvozi v filtrirano.json in filtrirano.xml.
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent / "data"


# ---------- modeli (deserializacija XML -> objekti) ----------

@dataclass
class Uporabnik:
    id: str
    ime: str
    priimek: str
    email: Optional[str]          # lahko manjka
    datum_registracije: date
    cilj: str
    teza: float


@dataclass
class Vaja:
    id: str
    ime: str
    misicna_skupina: str
    oprema: str
    tezavnost: int
    opis: Optional[str]           # lahko je prazen


@dataclass
class Trening:
    id: str
    uporabnik_id: str
    vaja_id: str
    datum: date
    serije: int
    ponovitve: int
    teza_bremena: Optional[float]  # prazno pri vajah z lastno težo
    trajanje_min: int


def besedilo(el, tag):
    """Vrne besedilo podelementa ali None, če manjka ali je prazen."""
    child = el.find(tag)
    if child is None or child.text is None or not child.text.strip():
        return None
    return child.text.strip()


def preberi_uporabnike(pot):
    return [
        Uporabnik(
            id=el.get("id"),
            ime=besedilo(el, "ime"),
            priimek=besedilo(el, "priimek"),
            email=besedilo(el, "email"),
            datum_registracije=date.fromisoformat(besedilo(el, "datumRegistracije")),
            cilj=besedilo(el, "cilj"),
            teza=float(besedilo(el, "teza")),
        )
        for el in ET.parse(pot).getroot().findall("uporabnik")
    ]


def preberi_vaje(pot):
    return [
        Vaja(
            id=el.get("id"),
            ime=besedilo(el, "ime"),
            misicna_skupina=besedilo(el, "misicnaSkupina"),
            oprema=besedilo(el, "oprema"),
            tezavnost=int(besedilo(el, "tezavnost")),
            opis=besedilo(el, "opis"),
        )
        for el in ET.parse(pot).getroot().findall("vaja")
    ]


def preberi_treninge(pot):
    treningi = []
    for el in ET.parse(pot).getroot().findall("trening"):
        teza = besedilo(el, "tezaBremena")
        treningi.append(Trening(
            id=el.get("id"),
            uporabnik_id=el.get("uporabnikId"),
            vaja_id=el.get("vajaId"),
            datum=date.fromisoformat(besedilo(el, "datum")),
            serije=int(besedilo(el, "serije")),
            ponovitve=int(besedilo(el, "ponovitve")),
            teza_bremena=float(teza) if teza is not None else None,
            trajanje_min=int(besedilo(el, "trajanjeMin")),
        ))
    return treningi


# ---------- povezovanje prek ID-jev ----------

def poveži(uporabniki, vaje, treningi):
    """Vsak trening poveže z uporabnikom (uporabnikId) in vajo (vajaId)."""
    po_uporabnikih = {u.id: u for u in uporabniki}
    po_vajah = {v.id: v for v in vaje}
    zapisi = []
    for t in treningi:
        u, v = po_uporabnikih.get(t.uporabnik_id), po_vajah.get(t.vaja_id)
        if u is None or v is None:
            print(f"Opozorilo: trening {t.id} ima neobstoječ ID (uporabnik={t.uporabnik_id}, vaja={t.vaja_id})",
                  file=sys.stderr)
            continue
        zapisi.append({"trening": t, "uporabnik": u, "vaja": v})
    return zapisi


# ---------- filtriranje ----------

def filtriraj(zapisi, args):
    rezultat = []
    for z in zapisi:
        t, u, v = z["trening"], z["uporabnik"], z["vaja"]
        if args.uporabnik and u.id != args.uporabnik:
            continue
        if args.skupina and v.misicna_skupina.lower() != args.skupina.lower():
            continue
        if args.oprema and v.oprema.lower() != args.oprema.lower():
            continue
        if args.od and t.datum < args.od:
            continue
        if args.do and t.datum > args.do:
            continue
        if args.min_teza is not None and (t.teza_bremena is None or t.teza_bremena < args.min_teza):
            continue
        rezultat.append(z)
    return rezultat


# ---------- izpis ----------

def izpisi_tabelo(zapisi):
    glave = ["ID", "Datum", "Uporabnik", "Vaja", "Skupina", "Serije x pon.", "Teža (kg)", "Min"]
    vrstice = [[
        z["trening"].id,
        z["trening"].datum.isoformat(),
        f'{z["uporabnik"].ime} {z["uporabnik"].priimek}',
        z["vaja"].ime,
        z["vaja"].misicna_skupina,
        f'{z["trening"].serije} x {z["trening"].ponovitve}',
        "-" if z["trening"].teza_bremena is None else f'{z["trening"].teza_bremena:.1f}',
        str(z["trening"].trajanje_min),
    ] for z in zapisi]
    sirine = [max(len(str(x)) for x in [g] + [r[i] for r in vrstice]) for i, g in enumerate(glave)]
    print(" | ".join(g.ljust(s) for g, s in zip(glave, sirine)))
    print("-+-".join("-" * s for s in sirine))
    for r in vrstice:
        print(" | ".join(x.ljust(s) for x, s in zip(r, sirine)))
    print(f"\nŠtevilo zadetkov: {len(vrstice)}")


# ---------- izvoz ----------

def v_slovar(z):
    t, u, v = z["trening"], z["uporabnik"], z["vaja"]
    return {
        "id": t.id,
        "datum": t.datum.isoformat(),
        "uporabnik": {"id": u.id, "ime": u.ime, "priimek": u.priimek, "cilj": u.cilj},
        "vaja": {"id": v.id, "ime": v.ime, "misicnaSkupina": v.misicna_skupina, "oprema": v.oprema},
        "serije": t.serije,
        "ponovitve": t.ponovitve,
        "tezaBremena": t.teza_bremena,
        "trajanjeMin": t.trajanje_min,
    }


def izvozi_json(zapisi, pot):
    with open(pot, "w", encoding="utf-8") as f:
        json.dump([v_slovar(z) for z in zapisi], f, ensure_ascii=False, indent=2)


def izvozi_xml(zapisi, pot):
    root = ET.Element("filtriraniTreningi")
    for z in zapisi:
        t, u, v = z["trening"], z["uporabnik"], z["vaja"]
        el = ET.SubElement(root, "trening", id=t.id, uporabnikId=u.id, vajaId=v.id)
        ET.SubElement(el, "datum").text = t.datum.isoformat()
        ET.SubElement(el, "uporabnik").text = f"{u.ime} {u.priimek}"
        ET.SubElement(el, "vaja").text = v.ime
        ET.SubElement(el, "misicnaSkupina").text = v.misicna_skupina
        ET.SubElement(el, "serije").text = str(t.serije)
        ET.SubElement(el, "ponovitve").text = str(t.ponovitve)
        ET.SubElement(el, "tezaBremena").text = None if t.teza_bremena is None else str(t.teza_bremena)
        ET.SubElement(el, "trajanjeMin").text = str(t.trajanje_min)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(pot, encoding="utf-8", xml_declaration=True)


# ---------- glavni program ----------

def main():
    p = argparse.ArgumentParser(description="Filtriranje treningov iz povezanih XML datotek.")
    p.add_argument("--uporabnik", help="ID uporabnika, npr. u01")
    p.add_argument("--skupina", help="mišična skupina, npr. noge, prsi, hrbet")
    p.add_argument("--oprema", help="oprema, npr. palica, ročke, brez")
    p.add_argument("--od", type=date.fromisoformat, help="treningi od datuma (YYYY-MM-DD)")
    p.add_argument("--do", type=date.fromisoformat, help="treningi do datuma (YYYY-MM-DD)")
    p.add_argument("--min-teza", type=float, help="najmanjša teža bremena v kg")
    p.add_argument("--izhod", default=".", help="mapa za filtrirano.json in filtrirano.xml (privzeto trenutna)")
    args = p.parse_args()

    uporabniki = preberi_uporabnike(DATA_DIR / "uporabniki.xml")
    vaje = preberi_vaje(DATA_DIR / "vaje.xml")
    treningi = preberi_treninge(DATA_DIR / "treningi.xml")
    print(f"Prebrano: {len(uporabniki)} uporabnikov, {len(vaje)} vaj, {len(treningi)} treningov\n")

    rezultat = filtriraj(poveži(uporabniki, vaje, treningi), args)
    izpisi_tabelo(rezultat)

    izhod = Path(args.izhod)
    izhod.mkdir(parents=True, exist_ok=True)
    izvozi_json(rezultat, izhod / "filtrirano.json")
    izvozi_xml(rezultat, izhod / "filtrirano.xml")
    print(f"Shranjeno: {izhod / 'filtrirano.json'}, {izhod / 'filtrirano.xml'}")


if __name__ == "__main__":
    main()
