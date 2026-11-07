---
name: svg-graphics
description: Creating and editing SVG graphics, icons, diagrams, and illustrations as text files — precise, scalable, diffable, and renderable without external APIs. Use when the user needs an image asset, icon, logo sketch, simple illustration, or diagram, especially when no image-generation API is available or the asset must be editable/reproducible.
---

# SVG Graphics

SVG is often the *right* visual medium for a coding agent: it's text, so it's inspectable, versionable, and needs no GPU or API keys.

## When to choose SVG

- Icons, logos, diagrams, banners, wireframes, simple flat illustration.
- Anything the user may want to tweak later (colors, text, proportions).
- Not ideal for photorealism — reach for a generation API or photo instead.

## Workflow

1. Draft the SVG as a file (`asset.svg`) — never inline-only; the user needs the file.
2. **Render and look at it.** Never ship an SVG you haven't rendered:
   ```bash
   rsvg-convert -w 1024 asset.svg -o preview.png   # or inkscape, or chromium --headless --screenshot
   ```
   Then actually inspect the preview image before iterating.
3. Iterate on geometry from the preview, not from imagination.

## Practical geometry rules

- `viewBox="0 0 W H"` defines the coordinate system; width/height attributes scale it. Always set viewBox.
- Round coordinates to integers where possible; avoid subpixel text.
- Use `transform="translate(x,y) scale(s)"` groups instead of recomputing every coordinate when moving/scaling shapes.
- Text: set `font-family` to widely available fonts (sans-serif fallback), and add `dominant-baseline` for vertical centering.
- Gradients via `<linearGradient>`/`<radialGradient>` in `<defs>`; reference with `fill="url(#id)"`.
- For icons: draw on a 24×24 grid with a 2px stroke, `stroke-linecap="round"`, `stroke-linejoin="round"` — matches common icon conventions.

## Conversion targets

- PNG: `rsvg-convert -w 1024 in.svg -o out.png` (also supports `-a` to keep aspect).
- Favicon: render at 32×32 and 16×16 and verify legibility at that size.
- Clean/minify: keep it hand-written and tidy; avoid Inkscape metadata bloat when generating programmatically.
