import csv
import xml.etree.ElementTree as ET

KML_NS = "http://www.opengis.net/kml/2.2"
ET.register_namespace("", KML_NS)


def placemark(name, lon, lat, description=""):
    return {"name": str(name), "lon": float(lon), "lat": float(lat), "description": str(description)}


def _sub(parent, tag, text=None):
    el = ET.SubElement(parent, f"{{{KML_NS}}}{tag}")
    if text is not None:
        el.text = text
    return el


def build_kml(placemarks, document_name="earth_tool"):
    kml = ET.Element(f"{{{KML_NS}}}kml")
    document = _sub(kml, "Document")
    _sub(document, "name", document_name)
    for pm in placemarks:
        place = _sub(document, "Placemark")
        _sub(place, "name", pm["name"])
        if pm["description"]:
            _sub(place, "description", pm["description"])
        point = _sub(place, "Point")
        _sub(point, "coordinates", f"{pm['lon']},{pm['lat']},0")
    return ET.tostring(kml, encoding="unicode", xml_declaration=True)


def placemarks_from_csv(path):
    marks = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = {f.strip().lower() for f in (reader.fieldnames or [])}
        required = {"lon", "lat"}
        missing = required - fields
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")
        for row in reader:
            row = {k.strip().lower(): v for k, v in row.items()}
            marks.append(
                placemark(
                    row.get("name", ""),
                    row["lon"],
                    row["lat"],
                    row.get("description", ""),
                )
            )
    return marks


def write_kml(path, placemarks, document_name="earth_tool"):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_kml(placemarks, document_name))
