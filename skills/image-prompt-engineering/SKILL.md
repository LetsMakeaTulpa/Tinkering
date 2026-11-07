---
name: image-prompt-engineering
description: Load before writing any image-generation prompt — text-to-image, image-to-image, or edit instructions — for prompts that reliably produce the intended image. Structure (subject/scene/style/lighting/camera), concrete-noun discipline, aspect-ratio-aware composition, negative prompts where supported, and the diagnose-one-clause iteration loop.
---

# Image Prompt Engineering

Applies to every generation surface: image_generation (Black Forest), Bria text-to-image, Hugging Face Spaces models, FLUX, SDXL. The prompt is the biggest quality lever — bigger than model choice.

## Structure that works

Build prompts in this order, each slot one clause:

1. **Subject** — who/what, with the 2–3 concrete details that matter (pose, wardrobe, expression). Specific beats generic: "woman in a hallway" < "woman leaning against an institutional hallway wall, arms crossed, half-smirk".
2. **Scene** — where, when, what's around the subject.
3. **Style** — photorealistic / oil painting / 90s anime / technical diagram / flat vector. Name the style explicitly; never assume realism is default.
4. **Lighting** — golden hour, harsh flash, neon rim light, overcast soft. Lighting is the single highest-yield clause for realism.
5. **Camera/render language** — full body shot, low angle, 35mm, shallow depth of field, 8k render. Camera language steers composition better than "detailed".
6. **Mood/color** — muted palette, teal-and-orange, washed-out pastels.

## Rules

- Front-load the subject. Attention decays with clause position; the first 20 words carry the image.
- One style per prompt. "photorealistic oil painting anime render" averages into mush.
- Concrete nouns and verbs, no abstract adjectives alone ("beautiful, amazing, stunning" do nothing; "weathered concrete, buzzing fluorescent tube" do everything).
- Aspect-ratio awareness: describe composition matching the ratio — a full-body portrait wants "full body, standing, feet visible" in a 3:4 or 9:16 frame; otherwise models crop to a headshot.
- For edits/img2img: describe the *whole* target image, not just the delta — generation models redraw everything they're told about.
- Negative prompts (SD/SDXL surfaces): "blurry, lowres, watermark, extra fingers, deformed hands, text". Bria/Black Forest don't take negatives — fix by rephrasing the positive instead.
- Identity preservation: when extending or editing a person, keep original pixels where possible (mask-based ops), and repeat the subject's physical description verbatim in the prompt to anchor identity.

## Iterate like a director, not a slot machine

1. Draft prompt → generate → **actually look at the result**.
2. Diagnose in words what's wrong ("hands wrong", "too dark", "background empty").
3. Change exactly one clause and regenerate. Random re-rolls without diagnosis waste generations.
4. Keep a winner: when a result is 80% right, edit it rather than regenerating from scratch.

## Prompt templates

- Portrait: `{subject, pose, wardrobe}, {location}, {lighting}, {camera framing}, photorealistic, {mood}`
- Scene/landscape: `{place}, {time of day}, {weather}, {lighting}, {style}, {composition note}`
- Product: `{product} on {surface}, {lighting setup, e.g. softbox}, studio background, commercial photography, sharp focus`
- Diagram/technical: route to diagram-builder/SVG instead — wrong modality for generation.
