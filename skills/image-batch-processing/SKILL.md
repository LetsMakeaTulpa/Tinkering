---
name: image-batch-processing
description: Batch operations on image files — resizing, format conversion, compression, watermarking, thumbnails, EXIF stripping, contact sheets — using PIL/Pillow or ImageMagick. Use when the user has a folder of images to process or mentions bulk resize/convert/compress tasks.
---

# Image Batch Processing

## Tool choice

- **Pillow** (Python): when logic matters (conditional sizes, naming schemes, per-image decisions). Scriptable, cross-platform.
- **ImageMagick / `magick`**: one-liners for uniform transforms. `mogrify` for in-place batch, `convert` for individual outputs.
- **ffmpeg**: batches that involve video frames or GIFs.

## Always

1. **Never modify originals in place.** Write to a sibling output dir (`out/`), keep names predictable (`name_800w.jpg`).
2. Detect the actual installed tool and version first (`magick -version`, `python3 -c "import PIL"`); offer to install if missing (`pip install pillow` or the system package).
3. For large batches, print progress and a final count; fail per-file without aborting the batch (log, continue, summarize).

## Common recipes

Resize keeping aspect to fit 800px wide:
```python
from PIL import Image
from pathlib import Path
for p in Path("input").glob("*.jpg"):
    im = Image.open(p).convert("RGB")
    w, h = im.size
    im.resize((800, int(h * 800 / w)), Image.Resampling.LANCZOS).save(
        Path("output") / p.name, quality=85, optimize=True)
```

Strip EXIF (privacy — GPS/phone model): `Image.open(p)._getexif()` removal is unreliable; prefer `im.resize(im.size)` re-save which drops metadata, or `exiftool -all=` for lossless strip.

WebP conversion: `im.save(out, "WEBP", quality=80)` — typically 25–35% smaller than JPEG q85 at similar quality.

Contact sheet / grid:
```bash
magick montage input/*.jpg -tile 5x -geometry 300x300+4+4 -background '#222' sheet.png
```

## Pitfalls

- PNG photos are huge — convert to JPEG/WebP for photos, keep PNG only where transparency or sharp edges matter.
- CMYK JPEGs open with inverted-looking colors in PIL: check `im.mode` and convert `"CMYK" → "RGB"` explicitly.
- Animated GIFs: `Image.open` shows only frame 1; use `magick` or `ffmpeg` for full handling.
