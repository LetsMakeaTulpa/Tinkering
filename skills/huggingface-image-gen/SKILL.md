---
name: huggingface-image-gen
description: Load when the user wants image generation or editing via Hugging Face Spaces — free, no-API-key open models (FLUX, SDXL, background removal, upscaling, inpainting) — or when in-app image tools lack the needed style control, or the user names a specific open model. Covers the discover→task→space→input workflow, Space selection, queue behavior, and honest failure handling.
---

# Hugging Face Image Generation (Spaces)

The no-key fallback lane: run image generation and editing models as Hugging Face Spaces. Use when the in-app surfaces don't fit (style control, specific open models like SDXL/FLUX variants, background removal, upscaling) or when the user asks for a specific open model.

## Workflow

1. Call the dynamic-space tool with no arguments first — it returns the task catalog and usage (discover → task → space → input).
2. Pick the task: Image Generation, Image Editing, Background Removal, OCR, etc.
3. Pick a Space: prefer official model Spaces (black-forest-labs/FLUX.1-*, stabilityai/*) — they're maintained and documented.
4. Pass inputs per the Space's expected schema; the tool handles the queue and returns the output URL.
5. Download or reference the returned URL; verify the output is actually an image before reporting success.

## Choosing a Space

- Trending/official Spaces first (check trending models via the HF file-system tool).
- Read the Space's README before guessing inputs — Spaces vary wildly in accepted parameters (negative prompts, guidance, steps, aspect ratio).
- GPU Spaces are queued: expect 30s–2min; don't retry-spam, the queue position is returned.
- Zero-GPU Spaces may cold-start; one patient retry after a timeout is fine, more is not.

## Model quick-picks (verify current names — they change)

- General txt2img, high quality: FLUX.1 family Spaces
- Fast/cheap drafts: SDXL or SD-turbo Spaces
- Background removal: RMBG / briaai/RMBG Spaces
- Upscaling: Real-ESRGAN Spaces
- Inpainting/outpainting: SDXL-inpaint Spaces (mask + prompt)

## Rules

- Spaces are community infrastructure: they sleep, queue, and change API without notice. Report failures honestly and fall back to in-app tools when a Space is down — but say you switched.
- Don't upload sensitive images to public Spaces; inputs may be visible to operators or logged.
- This lane needs no API key — that's its whole value. If a Space demands a token, check the session's HF auth context first.
- Route prompts through image-prompt-engineering regardless of the surface.
