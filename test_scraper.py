"""Preizkus razčlenjevalnika na lokalnih HTML odlomkih (brez omrežja): python -m unittest test_scraper

Odlomki posnemajo strukturo strani StrengthLog (imenik vaj in podstran vaje).
"""
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import scraper

IMENIK_HTML = """
<html><body>
<nav><ul><li><a href="/about/">About</a></li></ul></nav>
<h2>Muscle Directory: Complete List of All Exercises</h2>
<h3>Chest Exercises</h3>
<ol>
  <li><a href="https://www.strengthlog.com/bench-press/">Bench Press</a></li>
  <li><a href="https://www.strengthlog.com/bar-dip/">Bar Dip</a></li>
  <li><a href="/cable-chest-press/">Cable Chest Press</a></li>
  <li><a href="https://www.strengthlog.com/clap-push-up/">Clap Push-Up</a></li>
</ol>
<h3>Leg Exercises</h3>
<div><ol>
  <li><a href="https://www.strengthlog.com/barbell-squat/">Barbell Squat</a></li>
  <li><a href="https://www.strengthlog.com/bench-press/">Bench Press</a></li>
  <li><a href="https://example.com/outside/">Outside link</a></li>
  <li>Item without link</li>
</ol></div>
<h2>The Best Strength Training Exercises for Every Body Part</h2>
<ul><li><a href="https://www.strengthlog.com/recent-post/">Recent post</a></li></ul>
</body></html>
"""

PODSTRAN_HTML = """
<html><body>
<h1>How to Bench Press: Muscles Worked &amp; Proper Form</h1>
<p>Short.</p>
<p>The barbell bench press is one of the most popular exercises in the world and one of the best chest exercises.</p>
<h3>Primary muscles worked:</h3>
<ul><li>Chest</li><li>Front Deltoid</li></ul>
<h3>Secondary muscles worked:</h3>
<ul><li>Triceps</li></ul>
<h2>How to Bench Press with Proper Form</h2>
<ol><li>Lie on the bench.</li><li>Lower the bar to your chest.</li><li>Press it up.</li></ol>
</body></html>
"""


class TestRazclenjevalnik(unittest.TestCase):
    def test_imenik(self):
        vaje = scraper.poisci_imenik(IMENIK_HTML)
        imena = [v["ime"] for v in vaje]
        self.assertEqual(imena, ["Bench Press", "Bar Dip", "Cable Chest Press", "Clap Push-Up", "Barbell Squat"])
        self.assertEqual(vaje[0]["misicnaSkupina"], "prsi")
        self.assertEqual(vaje[2]["url"], "https://www.strengthlog.com/cable-chest-press/")  # relativna povezava
        self.assertEqual(vaje[-1]["misicnaSkupina"], "noge")   # podvojena vaja in tuja povezava izpuščeni

    def test_manjka_razdelek(self):
        with self.assertRaises(ValueError):
            scraper.poisci_imenik("<html><body><h2>Nekaj drugega</h2></body></html>")

    def test_podrobnosti(self):
        p = scraper.poisci_podrobnosti(PODSTRAN_HTML)
        self.assertTrue(p["opis"].startswith("The barbell bench press"))
        self.assertEqual(p["primarneMisice"], ["Chest", "Front Deltoid"])
        self.assertEqual(p["sekundarneMisice"], ["Triceps"])
        self.assertEqual(len(p["koraki"]), 3)

    def test_podrobnosti_manjkajo(self):
        p = scraper.poisci_podrobnosti("<html><body><h1>Prazna stran</h1></body></html>")
        self.assertEqual(p, {"opis": "", "primarneMisice": [], "sekundarneMisice": [], "koraki": []})

    def test_izbor_po_skupini(self):
        imenik = scraper.poisci_imenik(IMENIK_HTML)
        self.assertEqual(len(scraper.izberi(imenik, 2, None)), 3)       # 2 prsi + 1 noge
        self.assertEqual(len(scraper.izberi(imenik, 0, "prsi")), 4)

    def test_izvoz(self):
        vaja = {"id": "w001", "ime": "Bench Press", "misicnaSkupina": "prsi", "url": "https://x/",
                "opis": "", "primarneMisice": ["Chest"], "sekundarneMisice": [], "koraki": ["a", "b"],
                "datumPridobitve": "2026-10-26"}
        with tempfile.TemporaryDirectory() as mapa:
            scraper.izvozi_json([vaja], Path(mapa) / "v.json")
            scraper.izvozi_xml([vaja], Path(mapa) / "v.xml")
            self.assertEqual(json.loads((Path(mapa) / "v.json").read_text(encoding="utf-8"))[0]["id"], "w001")
            root = ET.parse(Path(mapa) / "v.xml").getroot()
            self.assertEqual(root.find("vaja").get("id"), "w001")
            self.assertEqual(len(root.findall("vaja/koraki/korak")), 2)


if __name__ == "__main__":
    unittest.main()
