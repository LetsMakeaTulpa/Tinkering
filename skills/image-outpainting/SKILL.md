---
name: image-outpainting
description: Extending images beyond their original borders (adding full bodies, wider scenes, expanded backgrounds) using browser automation of web outpainting tools or local diffusers. Use when the user wants to expand an existing image's canvas, "see more" of a scene, or turn a partial view into a full composition.
---

# Image Outpainting

Extend an existing image beyond its borders. Three strategies, in order of preference:

## Strategy 1: Web tool automation (Playwright)

Best quality, requires a headed browser session and a logged-in account.

1. Never assume the site's DOM. First navigate and **dump the actual selectors**:
   ```python
   await page.goto(url)
   print(await page.content())  # inspect before writing selectors
   ```
2. Most outpaint UIs use **click-to-expand grid buttons** around the canvas, not drag handles. Find buttons adjacent to the canvas via `page.get_by_role("button")` near canvas coordinates.
3. Auth: session storage or manual login wait:
   ```python
   await page.wait_for_url("**/dashboard", timeout=120_000)  # user logs in
   ```
4. Wrap `browser.close()` in `finally:` so a selector timeout never leaks a browser process.

## Strategy 2: Local diffusers outpainting

Fully offline. The classic technique:

1. Pad the image with a margin (fill with noise or edge-repeat).
2. Run img2img with a mask that covers only the padded region.
3. Use a working model id — `runwayml/stable-diffusion-v1-5` was removed from Hugging Face; use `stable-diffusion-v1-5/stable-diffusion-v1-5` or a current SDXL.
4. On CPU: `pipe.enable_attention_slicing()`, expect minutes per step-batch; keep resolution ≤512 for drafts.

## Strategy 3: Seam-tolerant paste-back

Blend generated region into the original: feather the mask edge by 8–16px so the seam isn't visible, and match noise/grain across the whole composite last.

## Pitfalls

- Text or faces near the outpainted edge will bleed — mask generously.
- Generated continuations of a specific person often drift; keep the original pixels untouched (inpaint-style masking) and describe the subject in the prompt to anchor identity.
- Check free-tier limits before automating a paid site; detect the "credits exhausted" state and fail fast.
