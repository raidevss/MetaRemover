# Changelog

## 1.1.0 — 2026-09-05

Quality-first release. Pixel pass default is **Off**. Camera-only exports are one JPEG at quality 98, 4:4:4 chroma — no grain, crop, or second compress.

### Why this release

Turning on Camera + Pixel Subtle/Nuclear + Anti-AI stacked resamples and JPEG 4:2:0. That is what looked “lowered quality.” Metadata strip does not need that.

### Changes

- Pixel pass defaults to Off (recommended). Subtle / Strong / Nuclear are opt-in.
- Camera-only path: JPEG quality 98, 4:4:4. Pixel/Anti-AI paths stay 4:2:0 at 92–95.
- Exact pixel copy (`frombytes`) instead of `putdata`.
- Anti-AI uses the Pixel strength instead of ignoring Nuclear.
- README: honest SynthID research, tool comparison, EXIF needed for a realistic upload.

### What still cannot be promised

Google/OpenAI **SynthID** lives in pixels. No metadata tool removes it. Methods that sometimes clear vendor verifiers (img2img / diffusion regen) visibly damage the photo. This release does not claim SynthID removal.
