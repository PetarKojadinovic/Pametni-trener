"""Preizkusi sestavljanja prompta in deserializacije odgovora (brez klica API)."""

import json
import unittest
from types import SimpleNamespace

from pydantic import ValidationError

import llm_nacrt
from llm_nacrt import NacrtVadbe, VnosUporabnika, sestavi_prompt

PRIMER_JSON = {
    "naslov": "Tritedenski začetni načrt",
    "povzetek": "Celotelesni treningi trikrat na teden.",
    "dnevi": [
        {
            "dan": "sreda", "datum": "2026-11-04", "poudarek": "celo telo", "trajanje_min": 45,
            "ogrevanje": "5 min hoje", "ohlajanje": "raztezanje",
            "vaje": [
                {"ime": "Sklece", "vaja_id": "v04", "misicna_skupina": "prsi", "serije": 3,
                 "ponovitve": "8-10", "pocitek_s": 60, "opomba": "ravno telo"},
                {"ime": "Plank", "vaja_id": None, "misicna_skupina": "trebuh", "serije": 3,
                 "ponovitve": "30 s", "pocitek_s": 45, "opomba": ""},
            ],
        }
    ],
    "nasveti": ["Spi vsaj 7 ur."],
    "opozorila": [],
}


def vnos(**spremembe):
    podatki = dict(cilj="moč", raven="začetnik", dni_na_teden=3, trajanje_min=45,
                   oprema=["brez", "ročke"], lokalni_cas="2026-11-03T19:30:00")
    podatki.update(spremembe)
    return VnosUporabnika(**podatki)


class TestPrompt(unittest.TestCase):
    def test_prompt_vsebuje_vnos_uporabnika(self):
        p = sestavi_prompt(vnos(ime="Ana", fokus=["noge"], omejitve="boli me koleno", starost=30))
        for del_ in ["Ana", "največjo moč", "začetnik", "3-krat", "45 minut", "brez, ročke",
                     "noge", "boli me koleno", "30 let"]:
            self.assertIn(del_, p)

    def test_prompt_se_spreminja_z_vnosom(self):
        self.assertNotEqual(sestavi_prompt(vnos()), sestavi_prompt(vnos(cilj="hujšanje", dni_na_teden=5)))

    def test_cas_brskalnika(self):
        zvecer = sestavi_prompt(vnos(lokalni_cas="2026-11-03T19:30:00"))
        self.assertIn("torek, 2026-11-03", zvecer)
        self.assertIn("začne jutri", zvecer)
        self.assertIn("začne danes", sestavi_prompt(vnos(lokalni_cas="2026-11-05T08:00:00")))

    def test_vaje_iz_baze_filtrirane_po_opremi(self):
        p = sestavi_prompt(vnos(oprema=["brez"]))
        self.assertIn("Sklece", p)
        self.assertNotIn("Počep s palico", p)
        self.assertTrue(all(v.oprema == "brez" for v in llm_nacrt.razpolozljive_vaje(["brez"])))


class TestVnos(unittest.TestCase):
    def test_neveljaven_vnos(self):
        for napacno in [dict(cilj="leteti"), dict(dni_na_teden=9), dict(oprema=[]),
                        dict(oprema=["kettlebell"]), dict(omejitve="x" * 301)]:
            with self.assertRaises(ValidationError):
                vnos(**napacno)


class TestOdgovor(unittest.TestCase):
    def test_deserializacija_json(self):
        nacrt = NacrtVadbe.model_validate_json(json.dumps(PRIMER_JSON))
        self.assertEqual(nacrt.dnevi[0].vaje[0].vaja_id, "v04")
        self.assertIsNone(nacrt.dnevi[0].vaje[1].vaja_id)
        self.assertEqual(nacrt.stevilo_vaj(), 2)
        self.assertEqual(nacrt.iz_baze(), 50)

    def test_manjkajoce_polje(self):
        slabo = dict(PRIMER_JSON)
        del slabo["dnevi"]
        with self.assertRaises(ValidationError):
            NacrtVadbe.model_validate(slabo)

    def test_shema_za_model(self):
        shema = NacrtVadbe.model_json_schema()
        self.assertEqual(set(shema["required"]), {"naslov", "povzetek", "dnevi", "nasveti", "opozorila"})

    def test_pridobi_nacrt_z_laznim_odjemalcem(self):
        poslano = {}

        def parse(**kwargs):
            poslano.update(kwargs)
            return SimpleNamespace(stop_reason="end_turn", parsed_output=NacrtVadbe.model_validate(PRIMER_JSON))

        odjemalec = SimpleNamespace(messages=SimpleNamespace(parse=parse))
        nacrt = llm_nacrt.pridobi_nacrt(vnos(ime="Marko"), odjemalec)
        self.assertIsInstance(nacrt, NacrtVadbe)
        self.assertIs(poslano["output_format"], NacrtVadbe)
        self.assertIn("Marko", poslano["messages"][0]["content"])

    def test_zavrnitev(self):
        odjemalec = SimpleNamespace(messages=SimpleNamespace(
            parse=lambda **_: SimpleNamespace(stop_reason="refusal", parsed_output=None)))
        with self.assertRaises(llm_nacrt.NapakaLLM):
            llm_nacrt.pridobi_nacrt(vnos(), odjemalec)


if __name__ == "__main__":
    unittest.main()
