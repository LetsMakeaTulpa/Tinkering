# Skills

Agent skills for Mistral Code, following the standard Agent Skills format
(see [anthropics/skills](https://github.com/anthropics/skills) and the
[Agent Skills spec](https://github.com/agentskills/agentskills)).

Each skill is a directory with a `SKILL.md` containing YAML frontmatter
(`name`, `description`) plus instructions. The `description` is what the
agent reads to decide when to load the skill, so it states trigger
conditions explicitly.

## Visual skills

| Skill | Purpose |
|---|---|
| `image-outpainting` | Extending images beyond their borders (web tools + local diffusers) |
| `image-generation-api` | Correct request shapes for Stability/Replicate/local generation APIs |
| `image-batch-processing` | Bulk resize/convert/compress/strip-EXIF with Pillow or ImageMagick |
| `svg-graphics` | Authoring and rendering SVG icons, diagrams, and illustrations |
| `chart-dataviz` | Charts from data (matplotlib) and structure diagrams (Mermaid) |
| `ui-visual-review` | Screenshot capture, visual inspection, and screenshot diffing |
| `image-prompt-engineering` | Prompt craft: subject/scene/style/lighting/camera structure, iteration discipline |
| `image-edit-pipeline` | Multi-step edit chains: outpaint, background swap, erase, enhance, upscale |
| `huggingface-image-gen` | Free no-key generation via Hugging Face Spaces (FLUX, SDXL, RMBG, Real-ESRGAN) |

The last three are also published to the Mistral skill registry (workspace skills
`image-prompt-engineering`, `image-edit-pipeline`, `huggingface-image-gen`).

## Adding a skill

1. `mkdir skills/<skill-name> && $EDITOR skills/<skill-name>/SKILL.md`
2. Frontmatter must include `name` (lowercase-hyphenated) and `description`
   (third person, states when to use it).
3. Keep the body skimmable: workflow steps, concrete commands, and a
   pitfalls section. Link detail docs rather than inlining everything.
4. Test the trigger: would the `description` cause the skill to load when
   someone asks a relevant question, and not otherwise?
