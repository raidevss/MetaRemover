# MetaRemover

Windows desktop app that **rebuilds a photo from its pixels**, drops every metadata and provenance layer that lived in the file headers, then optionally writes a phone-camera JPEG so Windows Details, Discord, and similar surfaces show Make / Model / Date instead of “no metadata”.

Drag images in, inspect before/after, pick a camera, optionally drop a GPS pin, process. Default camera is iPhone 17.

## Why a pixel rebuild

Most “EXIF strippers” rewrite tags in place. That leaves C2PA Content Credentials (JPEG APP11 / PNG `caBX`), IPTC `DigitalSourceType`, PNG ComfyUI workflows, ICC profiles, and vendor chunks sitting in the container.

MetaRemover copies pixel values into a new image and saves that file. Source headers are never copied.

## What it removes vs what it cannot

| Layer | Where it lives | This tool |
| --- | --- | --- |
| C2PA Content Credentials | JPEG APP11 / PNG `caBX` / AVIF uuid / XMP | Removed |
| IPTC `DigitalSourceType` (trainedAlgorithmicMedia) | XMP / IPTC | Removed |
| EXIF / GPS / IPTC / XMP | File headers | Removed; optional phone EXIF written back |
| PNG prompts / ComfyUI workflow | `tEXt` / `iTXt` | Removed |
| xAI / Grok JPEG signature | EXIF Artist UUID + `Signature:` blob | Removed |
| China AIGC (TC260) / Samsung genAIType | PNG iTXt / maker notes | Removed |
| JPEG JFIF + Adobe APP14 | Software-export markers | Dropped on camera JPEGs |
| JPEG quantization-table fingerprint | Codec tables | Wiped on re-encode |
| LSB / naive stego | Low bits | Destroyed by resample |
| **Google SynthID** / OpenAI pixel watermark | Frequency-domain **pixels** | **Not guaranteed.** Built to survive crop, JPEG, noise, screenshots. |

OpenAI (since May 2026) and Google embed SynthID in the pixels as well as C2PA. Metadata tools cannot clear that. OpenAI Verify and the Gemini app can still match those files.

Instagram, Facebook, Threads, TikTok, and LinkedIn **read C2PA/IPTC at upload** and apply an “AI info” label, **then** strip the metadata from the served file. A naive EXIF-only strip still gets labeled.

Grok web-UI downloads are often WebP with no tags. The original JPEG (download button / `imagine-public.x.ai`) carries an xAI EXIF signature, not C2PA.

Sources: [ExifReader 2026](https://www.exifreader.com/blog/remove-ai-metadata-from-images/), [C2PA vs watermarking](https://metastrip.app/blog/content-credentials-vs-watermarking-vs-metadata), [OpenAI provenance (May 2026)](https://openai.com/index/advancing-content-provenance/), [Instagram AI labels](https://www.theverge.com/ai-artificial-intelligence/989617/instagram-ai-content-label-confusion).

## Features

- **Before / after reader** — EXIF (Pillow `getexif` + piexif), GPS, IPTC, ICC, XMP, PNG text, WEBP chunks, AVIF boxes, C2PA / `caBX` / JUMBF, Grok signature, AIGC labels.
- **Clean strip** — rebuild from raw pixels. Source headers and chunks are not copied.
- **Camera JPEG write** — APP1 EXIF first, no JFIF / APP14. Windows Details shows Make / Model / Date taken. Thumbnail and APEX exposure tags included.
- **Device profiles** — iPhone 13–18 (and Pro / Pro Max), Galaxy S24 / S25, Pixel 8 / 9 / 10. A phone preset always saves **JPEG**. Default is iPhone 17 on iOS 26.
- **GPS map picker** — offline world map (Natural Earth land). Search uses Nominatim; no OSM tiles.
- **Pixel pass** (Subtle default) — 1% crop, 98.5% scale round-trip, sub-pixel shift, 0.1–0.3° rotation, per-channel grain, 0.2px blur + sharpen, Lab / tone / vignette / CA, JPEG 93 4:2:0. Does not remove SynthID.
- **Anti-AI pass** — stronger camera-pipeline stack aimed at pixel classifiers (Sightengine, Hive). EXIF does nothing there. Not guaranteed.
- **Aspect crop** — original, 4:3 phone, 4:5 Instagram, 9:16 story, 16:9.
- **Dark / light theme**, drag-and-drop, multi-select process.

Hover help lives on the field **names** (Camera, GPS, Pixel pass), not on the pickers.

## Requirements

- Windows
- Python 3.10 or newer
- Dependencies in `requirements.txt`: PySide6, Pillow, piexif, numpy

## Install

```powershell
git clone https://github.com/raidevss/MetaRemover.git
cd MetaRemover
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Run

Double-click **`MetaRemover.vbs`** (no console window) or **`MetaRemover.bat`**. A Desktop shortcut is created the first time you run the launcher.

Or from a terminal:

```powershell
venv\Scripts\python.exe main.py
```

## Usage

1. **Add** images, or drag files / a folder onto the list. Thumbnails stay in the list; click one to read its metadata.
2. **Camera** — pick a phone profile (default iPhone 17) or None for a headerless strip.
3. **GPS** — optional. Search or click the map. Most apps strip GPS on upload.
4. **Pixel pass** — Subtle is the default. Off leaves pixels untouched besides the rebuild.
5. **Anti-AI** — optional, heavier pixel pipeline. Overrides the pixel-pass strength.
6. **Aspect** — optional center crop.
7. **Output** — same folder as `name_clean.jpg` by default, or choose a folder.
8. Select one or more files (**Ctrl+click** to add) and **Process**.

Only the current selection is processed.

## How a camera JPEG is written

When a phone preset is selected, the output is always JPEG:

1. Pixels are copied into a new image (and optionally run through the pixel / anti-AI pass).
2. EXIF is built to match a real Camera dump: Make, Model, Software (iOS version only on iPhones), lens, APEX exposure, thumbnail.
3. The JPEG is written with APP1 EXIF first and no JFIF / Adobe APP14 software tells.

PNG has no camera EXIF on a real iPhone. Saving PNG with a phone profile would leave Windows Details empty, so the tool forces JPEG.

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

Static rasters only: JPEG, PNG, WEBP, TIFF, BMP, AVIF.

## Project layout

```
MetaRemover/
├── main.py                 # Qt entry
├── MetaRemover.vbs         # silent launcher + desktop shortcut
├── MetaRemover.bat
├── requirements.txt
└── metaremover/
    ├── gui.py              # desktop UI
    ├── metadata.py         # read + pixel-rebuild strip
    ├── scan.py             # raw container scan (C2PA, PNG text, …)
    ├── presets.py          # fake-EXIF device profiles
    ├── realism.py          # pixel pass + anti-AI pass
    ├── geo_picker.py       # offline GPS map
    ├── theme.py
    └── data/land-110m.json # Natural Earth land (map)
```

## Notes

- Nuclear / anti-AI modes slightly change pixels. That is the point.
- If a platform still flags the image after a clean strip, it is reading pixels (SynthID / a classifier), not metadata.
- GPS is optional fake location in EXIF. It does not change the picture.

## Disclaimer

This tool is for inspecting and cleaning metadata on files you own or are allowed to process. Writing a phone-camera EXIF trail does not make an image “not AI,” does not defeat SynthID, and is not a guarantee against platform labels or forensic classifiers. Use it accordingly.

## License

[MIT](LICENSE)
