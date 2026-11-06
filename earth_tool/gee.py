def _load_ee():
    try:
        import ee
    except ImportError as exc:
        raise RuntimeError(
            "The ndvi command needs the earthengine-api package and an "
            "authenticated Earth Engine project: pip install earthengine-api, "
            "then run `earthengine authenticate`."
        ) from exc
    return ee


def parse_bounds(text):
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("--bounds must be minLon,minLat,maxLon,maxLat")
    min_lon, min_lat, max_lon, max_lat = parts
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValueError("Invalid bounds: need minLon<maxLon within [-180,180] and minLat<maxLat within [-90,90]")
    return min_lon, min_lat, max_lon, max_lat


def cloud_masked_s2(ee, aoi, start, end):
    def mask(image):
        qa = image.select("QA60")
        cloud = 1 << 10
        cirrus = 1 << 11
        mask_value = image.updateMask(qa.bitwiseAnd(cloud).eq(0).And(qa.bitwiseAnd(cirrus).eq(0)))
        return mask_value

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .map(mask)
    )
    return collection.median().clip(aoi)


def ndvi_image(composite):
    return composite.normalizedDifference(["B8", "B4"]).rename("NDVI")


def export_ndvi(bounds, start, end, description="earth_tool_ndvi", scale=30):
    ee = _load_ee()
    if not ee.data._credentials:
        ee.Initialize()
    else:
        ee.Initialize()
    min_lon, min_lat, max_lon, max_lat = bounds
    aoi = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
    composite = cloud_masked_s2(ee, aoi, start, end)
    image = ndvi_image(composite)
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        region=aoi,
        scale=scale,
        maxPixels=1e9,
    )
    task.start()
    return task.id
