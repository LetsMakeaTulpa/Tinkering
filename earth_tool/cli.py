import argparse
import sys

from .kml import placemarks_from_csv, write_kml


def main(argv=None):
    parser = argparse.ArgumentParser(prog="earth_tool", description="Google Earth / Earth Engine helper tool")
    sub = parser.add_subparsers(dest="command", required=True)

    kml_parser = sub.add_parser("kml", help="Build a KML file from a CSV of points (columns: lon,lat[,name,description])")
    kml_parser.add_argument("csv_path")
    kml_parser.add_argument("out_path")
    kml_parser.add_argument("--name", default="earth_tool", help="KML document name")

    ndvi_parser = sub.add_parser("ndvi", help="Export a cloud-masked Sentinel-2 NDVI GeoTIFF to Google Drive via Earth Engine")
    ndvi_parser.add_argument("--bounds", required=True, help="minLon,minLat,maxLon,maxLat")
    ndvi_parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    ndvi_parser.add_argument("--end", required=True, help="End date YYYY-MM-DD (exclusive)")
    ndvi_parser.add_argument("--description", default="earth_tool_ndvi", help="Drive export description")
    ndvi_parser.add_argument("--scale", type=int, default=30, help="Export scale in meters")

    args = parser.parse_args(argv)

    if args.command == "kml":
        marks = placemarks_from_csv(args.csv_path)
        write_kml(args.out_path, marks, args.name)
        print(f"Wrote {len(marks)} placemark(s) to {args.out_path}")
        return 0

    if args.command == "ndvi":
        from .gee import export_ndvi, parse_bounds

        try:
            bounds = parse_bounds(args.bounds)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        task_id = export_ndvi(bounds, args.start, args.end, args.description, args.scale)
        print(f"Started Earth Engine export task {task_id} (check the Tasks tab in the Earth Engine Code Editor)")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
