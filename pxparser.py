"""Preprost razčlenjevalnik datotek PC-Axis (.px) brez zunanjih knjižnic.

Datoteka PX je sestavljena iz zapisov oblike ``KLJUČ[jezik]("podključ")=vrednost;``.
Metapodatki opisujejo spremenljivke (STUB = vrstice, HEADING = stolpci),
njihove vrednosti (VALUES) in kode (CODES), zapis DATA pa vsebuje vse celice
večdimenzionalne tabele v vrstnem redu: zadnja spremenljivka se spreminja najhitreje.
"""

import itertools
import re

# Znaki, s katerimi SURS označuje manjkajoče ali zaupne podatke.
MANJKAJOCI = {"", ".", "..", "...", "....", ".....", "......", "-", "N", "z", "M"}

_KLJUC = re.compile(r'^([A-Z0-9\-]+)(?:\[([a-z]{2})\])?(?:\("(.*)"\))?$', re.S)


def _razdeli_zapise(besedilo):
    """Razdeli besedilo na zapise ``(ključ, vrednost)``; podpičje v narekovajih ne šteje."""
    zapisi, kos, v_narekovajih = [], [], False
    for znak in besedilo:
        if znak == '"':
            v_narekovajih = not v_narekovajih
        if znak == ";" and not v_narekovajih:
            zapis = "".join(kos).strip()
            if zapis:
                kljuc, _, vrednost = zapis.partition("=")
                zapisi.append((kljuc.strip(), vrednost.strip()))
            kos = []
        else:
            kos.append(znak)
    return zapisi


def _nizi(vrednost):
    """Vrne seznam nizov v narekovajih; sosednji nizi v novi vrstici se združijo (dolg tekst)."""
    deli = re.findall(r'"((?:[^"])*)"(\s*,?)', vrednost)
    rezultat, zdruzi = [], False
    for niz, locilo in deli:
        if zdruzi and rezultat:
            rezultat[-1] += niz
        else:
            rezultat.append(niz)
        zdruzi = "," not in locilo
    if not deli:
        return [vrednost]
    return rezultat


def _stevilo(zeton):
    zeton = zeton.strip().strip('"')
    if zeton in MANJKAJOCI:
        return None
    try:
        return float(zeton)
    except ValueError:
        return None


class PxTabela:
    """Razčlenjena tabela PX z izbranim jezikom (privzeto osnovni jezik datoteke)."""

    def __init__(self, metapodatki, podatki):
        self.meta = metapodatki
        self.podatki = podatki
        self.naslov = self._eno("TITLE")
        self.enote = self._eno("UNITS")
        self.matrika = self._eno("MATRIX")
        self.posodobljeno = self._eno("LAST-UPDATED") or self._eno("CREATION-DATE")
        self.spremenljivke = self._seznam("STUB") + self._seznam("HEADING")
        self.vrednosti = {s: self._seznam("VALUES", s) for s in self.spremenljivke}
        self.kode = {
            s: self._seznam("CODES", s) or list(self.vrednosti[s]) for s in self.spremenljivke
        }
        pricakovano = 1
        for s in self.spremenljivke:
            pricakovano *= len(self.vrednosti[s])
        if pricakovano != len(podatki):
            raise ValueError(
                f"{self.matrika}: DATA ima {len(podatki)} celic, pričakovano {pricakovano}"
            )

    def _eno(self, kljuc):
        vrednost = self.meta.get((kljuc, None, None))
        return _nizi(vrednost)[0] if vrednost is not None else None

    def _seznam(self, kljuc, podkljuc=None):
        vrednost = self.meta.get((kljuc, None, podkljuc))
        return _nizi(vrednost) if vrednost is not None else []

    def zapisi(self):
        """Vrne vse celice kot slovarje ``{spremenljivka: vrednost, ..., "vrednost": število}``."""
        kombinacije = itertools.product(*(self.vrednosti[s] for s in self.spremenljivke))
        for kombinacija, stevilo in zip(kombinacije, self.podatki):
            zapis = dict(zip(self.spremenljivke, kombinacija))
            zapis["vrednost"] = stevilo
            yield zapis

    def vrednost(self, **izbor):
        """Vrne eno celico; ključi so imena spremenljivk, vrednosti so besedila ali kode."""
        indeks = 0
        for s in self.spremenljivke:
            izbrano = izbor[s]
            moznosti = self.vrednosti[s]
            i = moznosti.index(izbrano) if izbrano in moznosti else self.kode[s].index(izbrano)
            indeks = indeks * len(moznosti) + i
        return self.podatki[indeks]


def razcleni(vsebina):
    """Razčleni PX iz bajtov ali niza in vrne :class:`PxTabela`."""
    if isinstance(vsebina, bytes):
        glava = vsebina[:2000].decode("latin-1")
        kodna = re.search(r'CODEPAGE="([^"]+)"', glava)
        kodiranje = kodna.group(1) if kodna else "windows-1250"
        besedilo = vsebina.decode(kodiranje, errors="replace")
    else:
        besedilo = vsebina

    besedilo = besedilo.lstrip("﻿")
    zacetek_podatkov = re.search(r"(^|;)\s*DATA\s*=", besedilo)
    if not zacetek_podatkov:
        raise ValueError("Datoteka nima zapisa DATA")
    glava = besedilo[: zacetek_podatkov.start() + 1]
    telo = besedilo[zacetek_podatkov.end():].rstrip().rstrip(";")

    meta = {}
    for kljuc, vrednost in _razdeli_zapise(glava):
        ujemanje = _KLJUC.match(kljuc)
        if not ujemanje:
            continue
        ime, jezik, podkljuc = ujemanje.groups()
        meta[(ime, jezik, podkljuc)] = vrednost

    zetoni = re.findall(r'"[^"]*"|[^\s,;]+', telo)
    podatki = [_stevilo(z) for z in zetoni]
    return PxTabela(meta, podatki)
