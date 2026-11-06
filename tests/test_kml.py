import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from earth_tool.kml import build_kml, placemark, placemarks_from_csv, write_kml

NS = "{http://www.opengis.net/kml/2.2}"


class KmlTest(unittest.TestCase):
    def test_build_kml_is_valid_xml_with_coordinates(self):
        marks = [placemark("Home", -122.4194, 37.7749, "SF & <home>")]
        root = ET.fromstring(build_kml(marks))
        coords = root.find(f".//{NS}coordinates")
        self.assertEqual(coords.text, "-122.4194,37.7749,0")
        name = root.find(f".//{NS}Placemark/{NS}name")
        self.assertEqual(name.text, "Home")

    def test_special_chars_escaped(self):
        marks = [placemark("A&B <x>", 1.0, 2.0)]
        text = build_kml(marks)
        self.assertIn("A&amp;B &lt;x&gt;", text)
        ET.fromstring(text)

    def test_csv_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "points.csv")
            with open(csv_path, "w", encoding="utf-8") as fh:
                fh.write("name,lon,lat,description\nAlpha,10.5,20.25,first\nBeta,-1,0,\n")
            marks = placemarks_from_csv(csv_path)
            self.assertEqual(len(marks), 2)
            self.assertEqual(marks[0]["lon"], 10.5)
            out = os.path.join(tmp, "out.kml")
            write_kml(out, marks, "test")
            root = ET.parse(out).getroot()
            self.assertEqual(len(root.findall(f".//{NS}Placemark")), 2)

    def test_csv_missing_columns_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "bad.csv")
            with open(csv_path, "w", encoding="utf-8") as fh:
                fh.write("name,value\nA,1\n")
            with self.assertRaises(ValueError):
                placemarks_from_csv(csv_path)


if __name__ == "__main__":
    unittest.main()
