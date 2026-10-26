"""Razčlenjevalnik (parser) spletne strani z vajami – StrengthLog.

Program:
1. prenese imenik vaj (https://www.strengthlog.com/exercise-directory/),
2. iz njega razčleni skupine mišic in povezave do vaj,
3. za izbrane vaje prenese še podstran (primarne/sekundarne mišice, koraki izvedbe),
4. podatke shrani v data/vaje_splet.json in data/vaje_splet.xml.

Uporabljena sta samo requests in beautifulsoup4 (pip install -r requirements.txt).
"""
import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.strengthlog.com/"
IMENIK_URL = BASE_URL + "exercise-directory/"
USER_AGENT = "PametniTrener/1.0 (studentska naloga, FERI)"

# angleško ime skupine na strani -> slovensko ime v naši bazi (enako kot v vaje.xml)
SKUPINE = {
    "chest": "prsi", "shoulder": "ramena", "bicep": "roke", "tricep": "roke",
    "forearm": "roke", "leg": "noge", "calve": "noge", "glute": "zadnjica",
    "back": "hrbet", "ab": "trebuh", "neck": "vrat", "cardio": "kardio",
}


# ---------- razčlenjevanje HTML (čiste funkcije, brez omrežja) ----------

def preslikaj_skupino(naslov):
    """'Chest Exercises' -> 'prsi'. Neznane skupine ostanejo v izvirni obliki."""
    prva = naslov.lower().split()[0] if naslov.split() else ""
    for kljuc, slo in SKUPINE.items():
        if prva.startswith(kljuc):
            return slo
    return naslov.lower()


def poisci_imenik(html):
    """Vrne seznam {ime, url, misicnaSkupina} iz strani z imenikom vaj."""
    soup = BeautifulSoup(html, "html.parser")
    glava = next((h for h in soup.find_all("h2") if "muscle directory" in h.get_text().lower()), None)
    if glava is None:
        raise ValueError("V HTML-ju ni razdelka 'Muscle Directory' – struktura strani se je verjetno spremenila.")

    vaje, videni, skupina = [], set(), None
    for el in glava.find_all_next(["h2", "h3", "li"]):
        if el.name == "h2":          # naslednji glavni razdelek = konec imenika
            break
        if el.name == "h3":
            skupina = preslikaj_skupino(el.get_text(" ", strip=True))
            continue
        a = el.find("a", href=True)
        if skupina is None or a is None:
            continue
        url = urljoin(BASE_URL, a["href"])
        ime = a.get_text(" ", strip=True)
        if not url.startswith(BASE_URL) or not ime or url in videni:
            continue
        videni.add(url)
        vaje.append({"ime": ime, "url": url, "misicnaSkupina": skupina})
    return vaje


def seznam_pod_naslovom(soup, zacetek):
    """Besedila elementov prvega seznama (ul/ol) za naslovom, ki se začne z `zacetek`."""
    for h in soup.find_all(["h2", "h3", "h4"]):
        if h.get_text(" ", strip=True).lower().startswith(zacetek):
            sez = h.find_next(["ul", "ol"])
            return [li.get_text(" ", strip=True) for li in sez.find_all("li")] if sez else []
    return []


def poisci_podrobnosti(html):
    """Iz strani ene vaje vrne opis, primarne/sekundarne mišice in korake. Manjkajoče ostane prazno."""
    soup = BeautifulSoup(html, "html.parser")
    opis = ""
    h1 = soup.find("h1")
    if h1 is not None:
        for p in h1.find_all_next("p", limit=6):
            besedilo = p.get_text(" ", strip=True)
            if len(besedilo) > 40:
                opis = besedilo
                break
    koraki = []
    for h in soup.find_all(["h2", "h3"]):
        if "proper form" in h.get_text(" ", strip=True).lower():
            sez = h.find_next("ol")
            koraki = [li.get_text(" ", strip=True) for li in sez.find_all("li")] if sez else []
            break
    return {
        "opis": opis,
        "primarneMisice": seznam_pod_naslovom(soup, "primary muscles"),
        "sekundarneMisice": seznam_pod_naslovom(soup, "secondary muscles"),
        "koraki": koraki,
    }


# ---------- omrežje ----------

def ustvari_sejo():
    seja = requests.Session()
    seja.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})
    return seja


def robots_dovoli(seja, url):
    """Preveri robots.txt. Če ga ni mogoče prebrati, strani ne obremenjujemo več kot običajno in nadaljujemo."""
    rp = robotparser.RobotFileParser()
    try:
        r = seja.get(urljoin(BASE_URL, "robots.txt"), timeout=15)
        rp.parse(r.text.splitlines())
    except requests.RequestException:
        print("Opozorilo: robots.txt ni mogoče prebrati.", file=sys.stderr)
        return True
    return rp.can_fetch(USER_AGENT, url)


def pridobi_html(seja, url, poskusi=3):
    for poskus in range(1, poskusi + 1):
        try:
            r = seja.get(url, timeout=15)
            r.raise_for_status()
            return r.text
        except requests.RequestException as napaka:
            print(f"  napaka ({poskus}/{poskusi}) pri {url}: {napaka}", file=sys.stderr)
            time.sleep(2 * poskus)
    return None


# ---------- izbor in izvoz ----------

def izberi(imenik, na_skupino, skupina):
    """Filtrira po skupini in omeji število vaj na skupino (0 = vse)."""
    izbrane, stevec = [], {}
    for v in imenik:
        if skupina and v["misicnaSkupina"] != skupina:
            continue
        stevec[v["misicnaSkupina"]] = stevec.get(v["misicnaSkupina"], 0) + 1
        if na_skupino and stevec[v["misicnaSkupina"]] > na_skupino:
            continue
        izbrane.append(v)
    return izbrane


def izvozi_json(vaje, pot):
    with open(pot, "w", encoding="utf-8") as f:
        json.dump(vaje, f, ensure_ascii=False, indent=2)


def izvozi_xml(vaje, pot):
    root = ET.Element("vajeSplet")
    for v in vaje:
        el = ET.SubElement(root, "vaja", id=v["id"])
        for polje in ("ime", "misicnaSkupina", "url", "opis"):
            ET.SubElement(el, polje).text = v[polje] or None
        for oznaka, otrok, kljuc in (("primarneMisice", "misica", "primarneMisice"),
                                     ("sekundarneMisice", "misica", "sekundarneMisice"),
                                     ("koraki", "korak", "koraki")):
            sez = ET.SubElement(el, oznaka)
            for besedilo in v[kljuc]:
                ET.SubElement(sez, otrok).text = besedilo
        ET.SubElement(el, "datumPridobitve").text = v["datumPridobitve"]
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(pot, encoding="utf-8", xml_declaration=True)


def main():
    p = argparse.ArgumentParser(description="Razčlenjevalnik imenika vaj (StrengthLog).")
    p.add_argument("--na-skupino", type=int, default=3, help="največ vaj na mišično skupino (0 = vse), privzeto 3")
    p.add_argument("--skupina", help="samo ena skupina, npr. prsi, noge, hrbet, ramena, roke, trebuh")
    p.add_argument("--brez-podrobnosti", action="store_true", help="samo imenik, brez prenosa podstrani")
    p.add_argument("--vhod-html", help="razčleni shranjeno HTML datoteko imenika namesto prenosa")
    p.add_argument("--zakasnitev", type=float, default=1.0, help="premor med zahtevki v sekundah (privzeto 1)")
    p.add_argument("--izhod", default=str(Path(__file__).parent / "data"), help="mapa za izvoz (privzeto data)")
    args = p.parse_args()

    seja = ustvari_sejo()
    if args.vhod_html:
        html = Path(args.vhod_html).read_text(encoding="utf-8")
    else:
        if not robots_dovoli(seja, IMENIK_URL):
            sys.exit("robots.txt ne dovoljuje prenosa te strani.")
        html = pridobi_html(seja, IMENIK_URL)
        if html is None:
            sys.exit("Imenika ni bilo mogoče prenesti.")

    imenik = poisci_imenik(html)
    print(f"V imeniku najdenih vaj: {len(imenik)}")
    izbrane = izberi(imenik, args.na_skupino, args.skupina)
    print(f"Izbranih vaj: {len(izbrane)}")

    danes = date.today().isoformat()
    rezultat = []
    for i, v in enumerate(izbrane, start=1):
        podrobnosti = {"opis": "", "primarneMisice": [], "sekundarneMisice": [], "koraki": []}
        if not args.brez_podrobnosti:
            print(f"[{i}/{len(izbrane)}] {v['ime']}")
            if robots_dovoli(seja, v["url"]):
                time.sleep(args.zakasnitev)
                podstran = pridobi_html(seja, v["url"])
                if podstran:
                    podrobnosti = poisci_podrobnosti(podstran)
        rezultat.append({"id": f"w{i:03d}", **v, **podrobnosti, "datumPridobitve": danes})

    izhod = Path(args.izhod)
    izhod.mkdir(parents=True, exist_ok=True)
    izvozi_json(rezultat, izhod / "vaje_splet.json")
    izvozi_xml(rezultat, izhod / "vaje_splet.xml")
    print(f"Shranjeno: {izhod / 'vaje_splet.json'}, {izhod / 'vaje_splet.xml'}")


if __name__ == "__main__":
    main()
