# Tinkering
Nope

## Flask Hello, World!

A minimal Flask web app that serves `Hello, World!` on the root URL (`/`).

### Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open <http://localhost:5000> — you should see `Hello, World!`.

The app binds to `0.0.0.0` and respects the `PORT` environment variable (defaults to `5000`).

## Google Earth tool (`earth_tool`)

A small helper package with two commands:

- `kml` — build a `.kml` file (openable in Google Earth) from a CSV of points. Works offline, no credentials needed.
- `ndvi` — export a cloud-masked Sentinel-2 NDVI GeoTIFF to Google Drive via Google Earth Engine. Requires `earthengine-api` and an authenticated Earth Engine project.

### KML from CSV

CSV columns: `lon,lat` required, `name,description` optional.

```bash
python3 -m earth_tool kml points.csv out.kml --name my-trip
```

### NDVI export (Earth Engine)

```bash
pip install earthengine-api
earthengine authenticate
python3 -m earth_tool ndvi --bounds -122.5,37.7,-122.3,37.9 --start 2024-06-01 --end 2024-09-01 --description sf_summer_ndvi
```

The export runs as a task; watch it in the Tasks tab of the [Earth Engine Code Editor](https://code.earthengine.google.com/).

### Tests

```bash
python3 -m unittest discover -s tests -v
```
