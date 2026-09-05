"""Phone-like pixel structure pass.

The default "subtle" preset is the combination that changes codec/grid
structure without an obvious look:

  1% edge crop → 98.5% scale round-trip → sub-pixel shift → faint RGB
  grain → 0.2px blur + sharpen → JPEG 93 4:2:0 at save.

Also applies a tiny rotation, Lab round-trip, local tone, vignette, and
per-channel CA — all below typical viewing threshold.

This does not remove Google SynthID or other robust pixel watermarks.
"""
from __future__ import annotations

import io
import random

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageTransform

_AI_EDGE = {
    512, 576, 640, 720, 768, 832, 896, 960, 1024, 1080, 1152, 1280,
    1344, 1408, 1536, 1664, 1792, 1920, 2048, 2560, 3072,
}

_STRENGTH = {
    "subtle": dict(
        crop=0.01, scale=0.985, shift=0.45, rot=0.18,
        grain=(0.75, 0.48, 0.85), blur=0.20, sharp=1.10,
        vignette=0.04, tone=1.6, lab=0.5, ca=0.35, jpeg=None,
    ),
    "strong": dict(
        crop=0.015, scale=0.97, shift=0.80, rot=0.28,
        grain=(1.4, 0.9, 1.6), blur=0.32, sharp=1.16,
        vignette=0.06, tone=2.4, lab=0.9, ca=0.55, jpeg=90,
    ),
    "nuclear": dict(
        crop=0.02, scale=0.96, shift=1.15, rot=0.40,
        grain=(2.1, 1.3, 2.3), blur=0.42, sharp=1.20,
        vignette=0.08, tone=3.2, lab=1.2, ca=0.80, jpeg=88,
    ),
}


def _center_crop(im: Image.Image, ratio_w: int, ratio_h: int) -> Image.Image:
    w, h = im.size
    target = ratio_w / ratio_h
    current = w / h
    if abs(current - target) < 0.01:
        return im
    if current > target:
        nw = int(round(h * target))
        left = (w - nw) // 2
        return im.crop((left, 0, left + nw, h))
    nh = int(round(w / target))
    top = (h - nh) // 2
    return im.crop((0, top, w, top + nh))


def apply_aspect(im: Image.Image, aspect: str) -> Image.Image:
    if aspect == "4:3":
        return _center_crop(im, 4, 3)
    if aspect == "4:5":
        return _center_crop(im, 4, 5)
    if aspect == "9:16":
        return _center_crop(im, 9, 16)
    if aspect == "16:9":
        return _center_crop(im, 16, 9)
    return im


def _deround(im: Image.Image) -> Image.Image:
    w, h = im.size
    if w not in _AI_EDGE and h not in _AI_EDGE:
        return im
    dx = random.randint(3, 11)
    dy = random.randint(3, 11)
    if w - 2 * dx < 32 or h - 2 * dy < 32:
        return im
    return im.crop((dx, dy, w - max(1, dx - 2), h - max(1, dy - 1)))


def _edge_crop_rescale(im: Image.Image, frac: float) -> Image.Image:
    w, h = im.size
    cx = max(1, int(round(w * frac)))
    cy = max(1, int(round(h * frac)))
    if w - 2 * cx < 32 or h - 2 * cy < 32:
        return im
    cropped = im.crop((cx, cy, w - cx, h - cy))
    return cropped.resize((w, h), Image.Resampling.LANCZOS)


def _scale_roundtrip(im: Image.Image, scale: float) -> Image.Image:
    w, h = im.size
    nw = max(8, int(round(w * scale)))
    nh = max(8, int(round(h * scale)))
    if (nw, nh) == (w, h):
        return im
    return im.resize((nw, nh), Image.Resampling.LANCZOS).resize((w, h), Image.Resampling.LANCZOS)


def _subpixel_shift(im: Image.Image, amount: float) -> Image.Image:
    dx = random.uniform(-amount, amount)
    dy = random.uniform(-amount, amount)
    w, h = im.size
    return im.transform(
        (w, h),
        ImageTransform.AffineTransform((1, 0, dx, 0, 1, dy)),
        resample=Image.Resampling.BICUBIC,
    )


def _tiny_rotate(im: Image.Image, degrees: float) -> Image.Image:
    angle = random.uniform(0.6, 1.0) * degrees * random.choice((-1.0, 1.0))
    w, h = im.size
    rotated = im.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    rw, rh = rotated.size
    left = max(0, (rw - w) // 2)
    top = max(0, (rh - h) // 2)
    return rotated.crop((left, top, left + w, top + h))


def _rgb_grain(arr: np.ndarray, sigmas: tuple[float, float, float]) -> np.ndarray:
    rng = np.random.default_rng()
    h, w, _ = arr.shape
    gray = arr.mean(axis=2, keepdims=True)
    shadow = (1.12 - gray / 255.0).clip(0.35, 1.25)
    for c, sigma in enumerate(sigmas):
        arr[:, :, c] += rng.normal(0, sigma, (h, w)) * shadow[:, :, 0]
    return arr


def _local_tone(arr: np.ndarray, amount: float) -> np.ndarray:
    h, w, _ = arr.shape
    rng = np.random.default_rng()
    noise = rng.normal(128, 48, (h, w)).clip(0, 255).astype(np.uint8)
    radius = max(6.0, min(h, w) / 12.0)
    tone_im = Image.fromarray(noise, "L").filter(ImageFilter.GaussianBlur(radius=radius))
    tone = (np.asarray(tone_im).astype(np.float32) - 128.0) / 128.0
    arr += tone[:, :, None] * amount
    return arr


def _lab_jitter(arr: np.ndarray, amount: float) -> np.ndarray:
    rgb = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    lab = np.asarray(rgb.convert("LAB")).astype(np.float32)
    rng = np.random.default_rng()
    lab[:, :, 0] += rng.normal(0, amount * 0.6, lab.shape[:2])
    lab[:, :, 1] += rng.normal(0, amount * 0.35, lab.shape[:2])
    lab[:, :, 2] += rng.normal(0, amount * 0.35, lab.shape[:2])
    lab = np.clip(lab, 0, 255).astype(np.uint8)
    back = Image.fromarray(lab, "LAB").convert("RGB")
    return np.asarray(back).astype(np.float32)


def _vignette(arr: np.ndarray, amount: float) -> np.ndarray:
    h, w, _ = arr.shape
    yy, xx = np.ogrid[0:h, 0:w]
    cy = (h - 1) / 2.0
    cx = (w - 1) / 2.0
    rx = max(cx, 1.0)
    ry = max(cy, 1.0)
    r = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    falloff = 1.0 - amount * np.clip(r - 0.65, 0, 1) ** 2
    arr *= falloff[:, :, None]
    return arr


def _chromatic_aberration(im: Image.Image, px: float) -> Image.Image:
    w, h = im.size
    r, g, b = im.split()
    r = r.transform((w, h), ImageTransform.AffineTransform((1, 0, -px, 0, 1, 0)), resample=Image.Resampling.BICUBIC)
    b = b.transform((w, h), ImageTransform.AffineTransform((1, 0, px, 0, 1, 0)), resample=Image.Resampling.BICUBIC)
    return Image.merge("RGB", (r, g, b))


def _lsb_dither(arr: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng()
    arr += rng.integers(-1, 2, size=arr.shape).astype(np.float32)
    return arr


def _jpeg_roundtrip(im: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, subsampling="4:2:0", optimize=False)
    buf.seek(0)
    out = Image.open(buf)
    out.load()
    return out.convert("RGB")


def structure_pass(
    im: Image.Image,
    *,
    strength: str = "subtle",
    aspect: str = "none",
    deround: bool = True,
) -> Image.Image:
    cfg = _STRENGTH.get(strength, _STRENGTH["subtle"])
    had_alpha = im.mode in ("RGBA", "LA", "PA")
    alpha = im.getchannel("A") if had_alpha else None
    work = im.convert("RGB")

    work = apply_aspect(work, aspect)
    if deround:
        work = _deround(work)
    if min(work.size) >= 64:
        work = _edge_crop_rescale(work, cfg["crop"])
        work = _scale_roundtrip(work, cfg["scale"])
        work = _subpixel_shift(work, cfg["shift"])
        work = _tiny_rotate(work, cfg["rot"])

    arr = np.asarray(work).astype(np.float32)
    arr = _rgb_grain(arr, cfg["grain"])
    arr = _local_tone(arr, cfg["tone"])
    arr = _lab_jitter(arr, cfg["lab"])
    arr = _vignette(arr, cfg["vignette"])
    arr = _lsb_dither(arr)
    work = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    work = _chromatic_aberration(work, cfg["ca"])
    work = work.filter(ImageFilter.GaussianBlur(radius=cfg["blur"]))
    work = ImageEnhance.Sharpness(work).enhance(cfg["sharp"])
    if cfg["jpeg"]:
        work = _jpeg_roundtrip(work, cfg["jpeg"])

    if alpha is not None:
        out = work.convert("RGBA")
        out.putalpha(alpha.resize(out.size, Image.Resampling.BILINEAR))
        return out
    return work


def phone_look(im: Image.Image, *, aspect: str = "none", deround: bool = True) -> Image.Image:
    return structure_pass(im, strength="subtle", aspect=aspect, deround=deround)


def _squeeze(im: Image.Image, frac: float) -> Image.Image:
    """BOX down, LANCZOS up — kills VAE/upsampler checkerboards (Sightengine/Hive)."""
    w, h = im.size
    nw = max(16, int(round(w * frac)))
    nh = max(16, int(round(h * frac)))
    small = im.resize((nw, nh), Image.Resampling.BOX)
    return small.resize((w, h), Image.Resampling.LANCZOS)


def _bayer_demosaic(arr: np.ndarray) -> np.ndarray:
    """RGGB mosaic then bilinear reconstruct. Real cameras never see native RGB."""
    h, w, _ = arr.shape
    if h < 4 or w < 4:
        return arr
    mosaic = np.zeros((h, w), dtype=np.float32)
    mosaic[0::2, 0::2] = arr[0::2, 0::2, 0]
    mosaic[0::2, 1::2] = arr[0::2, 1::2, 1]
    mosaic[1::2, 0::2] = arr[1::2, 0::2, 1]
    mosaic[1::2, 1::2] = arr[1::2, 1::2, 2]
    r = np.zeros((h, w), dtype=np.float32)
    g = np.zeros((h, w), dtype=np.float32)
    b = np.zeros((h, w), dtype=np.float32)
    r[0::2, 0::2] = mosaic[0::2, 0::2]
    g[0::2, 1::2] = mosaic[0::2, 1::2]
    g[1::2, 0::2] = mosaic[1::2, 0::2]
    b[1::2, 1::2] = mosaic[1::2, 1::2]

    def fill(ch: np.ndarray) -> np.ndarray:
        img = Image.fromarray(np.clip(ch, 0, 255).astype(np.uint8), "L")
        return np.asarray(img.filter(ImageFilter.GaussianBlur(radius=0.85))).astype(np.float32)

    r2, g2, b2 = fill(r), fill(g), fill(b)
    r2[0::2, 0::2] = mosaic[0::2, 0::2]
    g2[0::2, 1::2] = mosaic[0::2, 1::2]
    g2[1::2, 0::2] = mosaic[1::2, 0::2]
    b2[1::2, 1::2] = mosaic[1::2, 1::2]
    return np.stack([r2, g2, b2], axis=2)


def _fft_soften(arr: np.ndarray, cutoff: float = 0.38, strength: float = 0.62) -> np.ndarray:
    """Attenuate mid/high frequencies where diffusion VAE grids live."""
    h, w = arr.shape[:2]
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    radius = np.sqrt(((yy - cy) / max(cy, 1)) ** 2 + ((xx - cx) / max(cx, 1)) ** 2)
    mask = np.clip((cutoff + 0.18 - radius) / 0.18, 0.0, 1.0)
    blend = 1.0 - strength + strength * mask
    out = np.empty_like(arr)
    for c in range(3):
        spec = np.fft.fftshift(np.fft.fft2(arr[:, :, c]))
        spec *= blend
        rec = np.fft.ifft2(np.fft.ifftshift(spec)).real
        out[:, :, c] = rec
    return out


def _mesh_warp(im: Image.Image, amp: float = 1.6) -> Image.Image:
    w, h = im.size
    cols, rows = 8, 8
    mesh = []
    cw, ch = w / cols, h / rows
    for j in range(rows):
        for i in range(cols):
            x0, y0 = int(i * cw), int(j * ch)
            x1, y1 = int((i + 1) * cw), int((j + 1) * ch)
            dx = int(round(random.uniform(-amp, amp)))
            dy = int(round(random.uniform(-amp, amp)))
            quad = (
                x0 + dx, y0 + dy,
                x1 + dx, y0 + dy,
                x1 + dx, y1 + dy,
                x0 + dx, y1 + dy,
            )
            mesh.append(((x0, y0, x1, y1), quad))
    return im.transform(im.size, Image.Transform.MESH, mesh, Image.Resampling.BILINEAR)


def _motion_blur(im: Image.Image, radius: float = 0.55) -> Image.Image:
    return im.filter(ImageFilter.GaussianBlur(radius=radius))


def anti_ai_pass(im: Image.Image, *, aspect: str = "none") -> Image.Image:
    """Camera-forensics stack aimed at pixel classifiers (Sightengine, Hive).

    Sightengine docs: scoring is pixels only — EXIF/C2PA do nothing.
    Empirical (r/StableDiffusion, Image-Detection-Bypass-Utility):
    downscale+up, Bayer CFA, FFT smoothing, JPEG ~80, sensor grain.
    Not guaranteed. SynthID may survive.
    """
    had_alpha = im.mode in ("RGBA", "LA", "PA")
    alpha = im.getchannel("A") if had_alpha else None
    work = im.convert("RGB")
    work = apply_aspect(work, aspect)
    work = _deround(work)
    if min(work.size) >= 64:
        work = _edge_crop_rescale(work, 0.018)
        work = _squeeze(work, random.uniform(0.68, 0.78))
        work = _mesh_warp(work, amp=1.5)
        work = _tiny_rotate(work, 0.32)
        work = _subpixel_shift(work, 0.9)

    arr = np.asarray(work).astype(np.float32)
    arr = _bayer_demosaic(arr)
    arr = _fft_soften(arr, cutoff=0.36, strength=0.58)
    arr = _rgb_grain(arr, (2.4, 1.5, 2.7))
    arr = _local_tone(arr, 2.8)
    arr = _vignette(arr, 0.07)
    # Slightly crush blacks / drop sat so it looks like a phone JPEG, not a render.
    arr = 16.0 + (arr - 16.0) * 0.96
    work = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    work = ImageEnhance.Color(work).enhance(0.94)
    work = ImageEnhance.Contrast(work).enhance(0.97)
    work = _chromatic_aberration(work, 0.7)
    work = _motion_blur(work, 0.45)
    work = ImageEnhance.Sharpness(work).enhance(1.08)
    work = _jpeg_roundtrip(work, random.randint(78, 84))

    if alpha is not None:
        out = work.convert("RGBA")
        out.putalpha(alpha.resize(out.size, Image.Resampling.BILINEAR))
        return out
    return work

