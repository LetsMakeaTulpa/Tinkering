---
name: image-generation-api
description: Generating or editing images programmatically via image-generation APIs (Stability AI, Leonardo, Replicate, local diffusers). Use when the user wants scriptable/repeatable image generation, has or asks about API keys, or wants to avoid browser automation. Covers correct request shapes, error handling, and output verification.
---

# Image Generation via API

## Before choosing a provider

Check, in order:
1. Env vars for keys: `STABILITY_API_KEY`, `REPLICATE_API_TOKEN`, `LEONARDO_API_KEY`, `OPENAI_API_KEY`. Never ask the user for a key that's already in env; never echo a key.
2. Local capability (GPU/CPU, disk for model weights).
3. Whether the user needs img2img, inpainting, or plain txt2img — these use different endpoints.

## Stability AI (v2beta) — correct shapes

Multipart **or** JSON depending on endpoint; the common bug is mixing them.

- Text-to-image (sd3): send `prompt` in `data`, and **omit** the `image` field; `files={"none": ""}` is the documented idiom for the empty file part.
- Image-to-image: send the image as a **file part**, not in `data`:
  ```python
  files = {"image": open("init.jpg", "rb")}
  data = {"prompt": "...", "mode": "image-to-image",
          "output_format": "png", "aspect_ratio": "3:4"}
  # image_strength goes in data (0.0–1.0; lower = closer to init)
  ```
- Errors: `Accept: application/json` when you want structured errors, and guard:
  ```python
  try:
      detail = response.json()
  except ValueError:
      detail = response.text
  if not response.ok:
      raise RuntimeError(f"{response.status_code}: {detail}")
  ```
- Save only when `response.headers["content-type"].startswith("image/")` — otherwise you write an error JSON to a `.png`.

## Replicate

Simpler client model; use the `replicate` package and `replicate.run()`, polling handled for you. Good default when the user has no key but wants to pick one.

## Local (diffusers) fallback

- Model must exist: prefer `stable-diffusion-xl-base-1.0` or `stable-diffusion-v1-5/stable-diffusion-v1-5`.
- `torch_dtype=torch.float32` on CPU, `enable_attention_slicing()`.
- Set expectations: ~2–15 minutes per image on a laptop CPU at 512px; upscales should use a real super-resolution model or stay honest at native res.

## Verification

After every generation: open the output with PIL (`Image.open(...).verify()`) and confirm dimensions/format before reporting success. A "200" response with a corrupt or empty image is a common silent failure.
