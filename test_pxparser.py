"""Preizkusi razčlenjevalnika PX in obdelave (brez omrežja)."""

import unittest

import odprti_podatki
import pxparser

PRIMER = '''CHARSET="ANSI";
CODEPAGE="windows-1250";
LANGUAGE="sl";
LANGUAGES="sl","en";
MATRIX="TEST01";
TITLE="Delež oseb (%) po: LETO, SPOL, POGOSTOST";
TITLE[en]="Share of persons";
UNITS="%";
NOTE="Prvi del dolge opombe; "
"drugi del.";
STUB="LETO","SPOL";
HEADING="POGOSTOST";
VALUES("LETO")="2022","2025";
VALUES("SPOL")="Moški",
"Ženske";
VALUES[en]("YEAR")="2022","2025";
VALUES("POGOSTOST")="Dnevno","Tedensko","Manj kot enkrat na teden","Nikoli";
CODES("LETO")="2022","2025";
CODES("SPOL")="1","2";
CODES("POGOSTOST")="2","4","5","6";
DATANOTECELL("2022","2","4")=" M";
DATA=
30 50 10 10
20 55 15 10
32 50 8 10
".." 60 "-" 9;
'''


class TestRazcleni(unittest.TestCase):
    def setUp(self):
        self.t = pxparser.razcleni(PRIMER.encode("windows-1250"))

    def test_metapodatki(self):
        self.assertEqual(self.t.matrika, "TEST01")
        self.assertEqual(self.t.naslov, "Delež oseb (%) po: LETO, SPOL, POGOSTOST")
        self.assertEqual(self.t.spremenljivke, ["LETO", "SPOL", "POGOSTOST"])
        self.assertEqual(self.t.vrednosti["SPOL"], ["Moški", "Ženske"])
        self.assertEqual(self.t.kode["POGOSTOST"], ["2", "4", "5", "6"])

    def test_dolg_niz_se_zdruzi(self):
        self.assertEqual(self.t._eno("NOTE"), "Prvi del dolge opombe; drugi del.")

    def test_vrstni_red_celic(self):
        self.assertEqual(self.t.vrednost(LETO="2022", SPOL="Ženske", POGOSTOST="Tedensko"), 55)
        self.assertEqual(self.t.vrednost(LETO="2025", SPOL="1", POGOSTOST="6"), 10)

    def test_manjkajoci_podatki(self):
        self.assertIsNone(self.t.vrednost(LETO="2025", SPOL="Ženske", POGOSTOST="Dnevno"))
        self.assertIsNone(self.t.vrednost(LETO="2025", SPOL="Ženske", POGOSTOST="5"))

    def test_zapisi(self):
        zapisi = list(self.t.zapisi())
        self.assertEqual(len(zapisi), 16)
        self.assertEqual(zapisi[1], {"LETO": "2022", "SPOL": "Moški", "POGOSTOST": "Tedensko", "vrednost": 50})

    def test_napacno_stevilo_celic(self):
        with self.assertRaises(ValueError):
            pxparser.razcleni(PRIMER.replace("30 50 10 10", "30 50 10"))


class TestObdelava(unittest.TestCase):
    def test_vsota_redno_aktivnih(self):
        t = pxparser.razcleni(PRIMER)
        besedila = odprti_podatki._kode_v_besedila(t, "POGOSTOST", odprti_podatki.KODE_REDNO)
        self.assertEqual(besedila, ["Dnevno", "Tedensko"])
        self.assertEqual(odprti_podatki._vsota([30.0, 50.0]), 80.0)
        self.assertIsNone(odprti_podatki._vsota([None, 60.0]))


if __name__ == "__main__":
    unittest.main()
