---
name: ui-visual-review
description: Taking, inspecting, and iterating on screenshots and visual UI states — capturing pages with headless browsers, checking layout/color/contrast, and verifying visual changes match intent. Use when the user mentions screenshots, "check how it looks", UI regressions, or wants visual verification of a web app or HTML artifact.
---

# UI Visual Review

## Capture

Headless Chromium/Playwright, one command shape:
```bash
chromium --headless --screenshot=out.png --window-size=1280,800 URL
# or, with more control:
npx playwright screenshot --viewport-size="1280,800" --wait-for-timeout=2000 URL out.png
```
Then **always inspect the image file itself** before drawing conclusions — CSS silently fails (404 fonts, blocked images, flex collapse).

## Multi-state capture

To review beyond the initial state (hover, modal, scrolled), use a small Playwright script:
```python
async with async_playwright() as p:
    b = await p.chromium.launch()
    page = await (await b.new_context(viewport={"width": 1280, "height": 800})).new_page()
    await page.goto(URL)
    await page.screenshot(path="home.png", full_page=True)
```
`full_page=True` beats viewport screenshots for layout review.

## What to check in the screenshot

- Overflow: horizontal scrollbars, clipped text (`text-overflow: ellipsis` vs accidental wrap).
- Contrast: run a quick estimate — WCAG AA needs 4.5:1 body text. If suspicious, sample the colors from the image and compute the ratio.
- Spacing consistency: equal gutters, aligned baselines; look for the one element that's 1px off.
- Fallback states: also screenshot at 375px wide (mobile) — most layout bugs live there.

## Regression testing

For repeat verification, pin screenshots per state and diff:
```bash
compare -metric AE baseline.png current.png diff.png
```
Review the diff image, not just the number — antialiasing noise inflates `AE`; judge visually.

## Pitfalls

- `--headless` renders with no fonts/animations timing of a real session; wait for fonts (`document.fonts.ready`) before screenshotting.
- Fixed-time waits (`wait_for_timeout`) are flaky; prefer `wait_for_selector` / networkidle.
- Don't ship a screenshot of the wrong viewport size — record the viewport in the filename.
