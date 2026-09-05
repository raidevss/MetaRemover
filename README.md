# MetaRemover

Windows desktop app that **strips every metadata / provenance layer** from a photo, then optionally writes a phone-camera EXIF trail so Windows Details, Discord, and similar surfaces show Make / Model / Date.

**v1.1.0 default is quality-first:** Pixel pass Off, one JPEG at quality 98 / 4:4:4 if a camera profile is selected. Grain, crop, and Anti-AI are opt-in.

## Recommended settings (realistic upload, no extra softness)

| Control | Set to | Why |
| --- | --- | --- |
| Camera | iPhone 17 (default) | Make, Model, lens, DateTimeOriginal, APEX exposure, thumbnail |
| GPS | Optional | Fake location in EXIF. Most social apps strip it on upload |
| Pixel pass | **Off** | Leaves pixels alone. This is what keeps sharpness |
| Anti-AI | **Off** | Classifier pass *is* a resample. It will look softer |
| Aspect | Original | Crops change framing |

Camera None + Pixel Off keeps PNG/WebP/TIFF as the same format (true lossless strip).

A phone preset always saves **JPEG** — real iPhones never write camera EXIF on PNG.

## What it removes vs what it cannot

| Layer | Where it lives | This tool |
| --- | --- | --- |
| C2PA Content Credentials | JPEG APP11 / PNG `caBX` / AVIF uuid / XMP | Removed |
| IPTC `DigitalSourceType` (`trainedAlgorithmicMedia`) | XMP / IPTC | Removed |
| EXIF / GPS / IPTC / XMP | File headers | Removed; optional phone EXIF written back |
| PNG prompts / ComfyUI workflow | `tEXt` / `iTXt` | Removed |
| xAI / Grok JPEG signature | EXIF Artist UUID + `Signature:` blob | Removed |
| China AIGC (TC260) / Samsung genAIType | PNG iTXt / maker notes | Removed |
| JPEG JFIF + Adobe APP14 | Software-export markers | Dropped on camera JPEGs |
| **Google SynthID** / OpenAI pixel watermark | **Pixels** | **Not removed.** No metadata tool can |

Instagram, Facebook, Threads, TikTok, and LinkedIn **read C2PA/IPTC at upload** and apply an “AI info” label, **then** strip the metadata from the served file. A naive EXIF-only rewrite that leaves C2PA still gets labeled.

Grok web-UI downloads are often WebP with no tags. The original JPEG (`imagine-public.x.ai`) carries an xAI EXIF signature, not C2PA.

## Research notes (Sept 2026)

### SynthID

Google SynthID (and OpenAI’s use of the same family) is a **post-hoc pixel watermark**, not a file tag. [ExifReader’s 2026 guide](https://www.exifreader.com/blog/remove-ai-metadata-from-images/) and [MetaStrip](https://metastrip.app/blog/remove-c2pa-content-credentials-from-image) state the same boundary: strip C2PA/EXIF all day; SynthID is still there. [The Verge](https://www.theverge.com/tech/980416/google-gemini-ai-watermarks-removal) (Aug 2026): turning off Gemini’s visible sparkle does **not** turn off SynthID or C2PA.

Independent engineering ([remove-ai-watermarks](https://github.com/wiltodelta/remove-ai-watermarks/blob/main/docs/synthid.md)):

- Google’s paper (arXiv:2510.09263): SynthID-O keeps ~99.99% detection after JPEG, crop, and resize.
- A quality-preserving **local** remover that still fools Gemini / OpenAI Verify was **not found**.
- Diffusion img2img that *sometimes* clears the vendor oracle needs strength ~0.05 (OpenAI) to ~0.15 (Google) and lands around **25–36 dB PSNR** — that is visible damage.
- Attacks that beat the watermark verifier are often still caught as “went through a remover” ([Goonatilake & Ateniese 2026](https://arxiv.org/abs/2605.09203)).

MetaRemover will not ship a fake “remove SynthID” button.

### Best metadata removers (what actually matters)

Good tools edit **containers only**. Bad tools re-encode pixels.

| Tool | C2PA | EXIF/IPTC/XMP | Pixels | Notes |
| --- | --- | --- | --- | --- |
| **MetaRemover** (this) | Yes (rebuild) | Yes + optional camera write-back | Untouched when Pixel Off | Desktop, offline, Windows |
| [ExifReader AI Remover](https://www.exifreader.com/blog/remove-ai-metadata-from-images/) | Yes | AI-only or all | Untouched | Honest about SynthID |
| [MetaStrip](https://metastrip.app/blog/remove-c2pa-content-credentials-from-image) | Yes | Yes | Untouched | Browser, no upload |
| ExifTool ` -all=` | Partial/manual | Yes | Untouched | Can drop ICC and shift color |
| ExifCleaner | Often EXIF-only | GPS/EXIF | Untouched | Verify C2PA still gone |
| “SynthID remover” websites | Marketing | Varies | Often re-encode | Treat as unverified |

For **Instagram AI Info**, the reliable pre-upload fix is **C2PA + IPTC DigitalSourceType gone**. Meta has said the label is driven by those technical standards, not a public pixel scan at upload.

### Metadata a realistic phone upload should have

Windows Details / Discord look “empty” on a headerless PNG. A camera JPEG should carry:

- `Make` / `Model` (e.g. Apple / iPhone 17)
- `Software` = iOS version only (`26.6.1`), not “Photoshop”
- `DateTime` / `DateTimeOriginal` / `OffsetTime*`
- `FNumber`, `ExposureTime`, `ISOSpeedRatings`, `FocalLength`, `FocalLengthIn35mmFilm`
- `LensMake` / `LensModel`
- Optional `GPS*` (lat/lon/alt/timestamp)
- Embedded JPEG thumbnail
- APP1 EXIF **first**, no JFIF APP0, no Adobe APP14

That is what the Camera profiles write. GPS is optional because most social apps strip it after they read C2PA.

### Anti-AI classifiers (Hive, Sightengine)

Those score **pixels**, not EXIF. Light JPEG at phone quality (85–90) is the usual advice; heavy noise/blur is what makes a file look processed. MetaRemover’s Anti-AI pass is opt-in, not default, and is **not guaranteed**. Hive/Sightengine still do well on lightly edited fakes in 2026 tests.

## Features

- **Before / after reader** — EXIF, GPS, IPTC, ICC, XMP, PNG text, WEBP chunks, AVIF boxes, C2PA / JUMBF, Grok signature, AIGC labels.
- **Lossless strip** (default) — copy pixels, drop every source header/chunk.
- **Camera JPEG write** — APP1 EXIF first, no JFIF / APP14. Quality 98, 4:4:4 when Pixel is Off.
- **Device profiles** — iPhone 13–18 (and Pro / Pro Max), Galaxy S24 / S25, Pixel 8 / 9 / 10. Default iPhone 17 / iOS 26.
- **GPS map picker** — offline Natural Earth land. Search uses Nominatim.
- **Pixel pass** — opt-in Subtle / Strong / Nuclear grain + light resample. Not SynthID.
- **Anti-AI pass** — opt-in classifier-oriented stack. Softens. Not guaranteed.
- Dark / light theme, drag-and-drop, multi-select.

## Requirements

- Windows
- Python 3.10 or newer
- `requirements.txt`: PySide6, Pillow, piexif, numpy

## Install

```powershell
git clone https://github.com/raidevss/MetaRemover.git
cd MetaRemover
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Run

Double-click **`MetaRemover.vbs`** (no console) or **`MetaRemover.bat`**. A Desktop shortcut is created the first time.

```powershell
venv\Scripts\python.exe main.py
```

## Usage

1. Add images, or drag files / a folder. Click one to read metadata.
2. Camera — iPhone 17 by default, or None for a headerless strip.
3. GPS — optional.
4. Pixel pass — **leave Off** unless you want grain.
5. Anti-AI — leave Off unless you accept softness.
6. Process the selection (Ctrl+click to add).

## Device profiles

| Key | Label |
| --- | --- |
| `iphone18` / `iphone18pro` | iPhone 18 / 18 Pro |
| `iphone17` (default) | iPhone 17 |
| `iphone17pro` / `iphone17promax` | iPhone 17 Pro / Pro Max |
| `iphone16` / `iphone16pro` | iPhone 16 / 16 Pro |
| `iphone15` / `iphone15pro` | iPhone 15 / 15 Pro |
| `iphone14` / `iphone14pro` | iPhone 14 / 14 Pro |
| `iphone13` / `iphone13pro` | iPhone 13 / 13 Pro |
| `galaxys24` / `galaxys25` | Galaxy S24 / S25 |
| `pixel8` / `pixel9` / `pixel10` | Pixel 8 / 9 / 10 |

## Supported formats

JPEG, PNG, WEBP, TIFF, BMP, AVIF.

## Disclaimer

For files you own or are allowed to process. Camera EXIF does not make an image “not AI,” does not defeat SynthID, and is not a guarantee against platform labels or forensic classifiers.

## License

[MIT](LICENSE)
