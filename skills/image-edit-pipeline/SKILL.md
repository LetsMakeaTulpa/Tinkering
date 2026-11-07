---
name: image-edit-pipeline
description: Load whenever an image job needs more than one operation — extend/outpaint to a new aspect ratio, remove or replace backgrounds, erase objects, upscale, enhance, product/tryon shots, or any generate-then-fix sequence. Sequences image operators into ordered pipelines with inspect-after-every-step discipline.
---

# Image Edit Pipeline

Multi-step image operations chained across the Bria operators and image_generation edit. One call rarely finishes a real job — this is the sequencing skill.

## Available operators (Bria connector)

- gen/edit: `text_to_image`, `edit_image` (natural-language edit, up to 4 reference images), `expand_image` (outpaint / aspect-ratio change)
- retouch: `erase_from_image` (masked), `erase_foreground`, `remove_background`, `crop_out_foreground`, `blur_background`, `generate_background`
- quality: `enhance_image` (detail/sharpen, optional upscale), `increase_resolution` (2x/4x)
- commercial: `product_holding`, `virtual_tryon`, `ad_resize`, `ad_to_layers`
- also: `image_generation.edit_image` for natural-language edits; Hugging Face Spaces for free external models

## Canonical pipelines

**Outpaint / extend to full body** (the classic ask):
1. `expand_image` with target aspect ratio (3:4 or 9:16) — this is the outpaint step; describe the extension in the prompt (scene continuation, subject description to anchor identity).
2. Inspect the seam. If the extension drifted (wrong shoes, warped legs): `edit_image` with a targeted instruction, or `erase_from_image` + regenerate that region.
3. `enhance_image` to unify grain/detail across old and new pixels.

**Clean product shot**: `remove_background` → `generate_background` (prompted surface/scene) → `enhance_image` → `increase_resolution`.

**Person + garment**: `virtual_tryon` (person photo + garment photo, no prompt needed) → `enhance_image`.

**Declutter a scene**: `erase_foreground` (removes subject, rebuilds what's behind) → `edit_image` for lighting consistency.

**Fix one region**: prefer `edit_image` with a precise instruction over regenerate-from-scratch; it preserves everything outside the edit.

## Rules

- **Inspect after every step** (one focused question per image-analysis call). Never chain 4 ops blind — errors compound and you won't know which step caused them.
- Order matters: expand → edit → enhance → upscale. Upscaling before edits wastes resolution on pixels you'll replace.
- Identity drift is the #1 failure in person edits: keep original pixels (edit/erase, not full regenerate) and repeat the subject's physical description in every prompted step.
- Bria takes image URLs (preferred) or base64; local paths only work when the server shares the filesystem — pass returned URLs between steps.
- When a step fails, report the actual error and which step; don't silently skip it and ship a half-processed image.
- Same input twice → reuse the intermediate, don't re-run the chain.

## When not to pipeline

One clean `text_to_image` with a good prompt (see image-prompt-engineering) beats a 5-step rescue chain. If a chain exceeds ~4 rescue steps, regenerate instead.
