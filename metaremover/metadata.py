"""Metadata reading and stripping.

Reading uses Pillow getexif() plus a raw container scan so JPEG APP1, WEBP
EXIF/XMP, PNG text/C2PA, TIFF IFDs, and AVIF boxes all show up.

Stripping copies pixels into a new Image and saves that — source headers
are never copied. Optional phone EXIF is written afterward as a camera-like
JPEG (no JFIF/APP14 software tells).
"""
from __future__ import annotations

import io
import os
import struct
from dataclasses import dataclass, field

import piexif
from PIL import Image, IptcImagePlugin
from PIL.ExifTags import GPSTAGS, IFD, TAGS

from . import scan

GPS_TAG_NAMES = {
    0: "GPSVersionID", 1: "GPSLatitudeRef", 2: "GPSLatitude",
    3: "GPSLongitudeRef", 4: "GPSLongitude", 5: "GPSAltitudeRef",
    6: "GPSAltitude", 7: "GPSTimeStamp", 29: "GPSDateStamp",
}

_COMMON_IPTC = {
    (2, 5): "Object Name",
    (2, 25): "Keywords",
    (2, 80): "By-line",
    (2, 90): "City",
    (2, 95): "Province/State",
    (2, 101): "Country",
    (2, 105): "Headline",
    (2, 110): "Credit",
    (2, 116): "Copyright Notice",
    (2, 120): "Caption",
}

_PNG_SKIP_INFO = {
    "dpi", "aspect", "gamma", "transparency", "background", "duration",
    "loop", "extension", "chromaticity", "srgb", "interlace", "bits",
    "icc_profile", "exif", "xmp", "text",
}


@dataclass
class MetadataReport:
    path: str
    format: str = ""
    size: tuple[int, int] = (0, 0)
    mode: str = ""
    file_size_bytes: int = 0
    exif: dict = field(default_factory=dict)
    gps: dict = field(default_factory=dict)
    iptc: dict = field(default_factory=dict)
    other_segments: list = field(default_factory=list)
    ai_signals: list = field(default_factory=list)
    has_exif: bool = False
    has_icc: bool = False

    def is_clean(self) -> bool:
        return not (
            self.exif or self.gps or self.iptc or self.other_segments
            or self.has_icc or self.ai_signals
        )

    def summary_lines(self) -> list[str]:
        lines = [
            f"Format: {self.format}    Size: {self.size[0]}x{self.size[1]}    Mode: {self.mode}",
            f"File size: {self.file_size_bytes:,} bytes",
        ]
        if self.ai_signals:
            lines.append("-- AI / provenance signals in the file --")
            for s in self.ai_signals:
                lines.append(f"  {s}")
            lines.append(
                "Note: C2PA/XMP/EXIF/PNG prompts are stripped by a pixel rebuild. "
                "Google SynthID (if present) lives in the pixels and is not metadata. "
                "Instagram/Facebook/TikTok read C2PA at upload, then strip it."
            )
        if self.is_clean():
            lines.append("No EXIF, IPTC, XMP, C2PA, or PNG text found.")
            lines.append(
                "Typical of screenshots, social-media downloads, Grok web WebP, "
                "and already-stripped files. Pick a phone profile so the output "
                "gets camera Make/Model/Date — Windows Details stays empty on a "
                "headerless file."
            )
            return lines

        if self.exif:
            lines.append(f"-- EXIF ({len(self.exif)} fields) --")
            for k, v in self.exif.items():
                lines.append(f"  {k}: {v}")
        if self.gps:
            lines.append("-- GPS --")
            for k, v in self.gps.items():
                lines.append(f"  {k}: {v}")
        if self.iptc:
            lines.append(f"-- IPTC ({len(self.iptc)} fields) --")
            for k, v in self.iptc.items():
                lines.append(f"  {k}: {v}")
        if self.has_icc:
            lines.append("ICC color profile: present")
        if self.other_segments:
            lines.append("-- Other embedded data --")
            for seg in self.other_segments:
                detail = f" ({seg.detail})" if seg.detail else ""
                lines.append(f"  {seg.label}: {seg.size} bytes{detail}")
        return lines


def _decode_exif_value(value) -> str:
    if isinstance(value, bytes):
        if value.startswith(b"ASCII\x00\x00\x00") or value.startswith(b"UNICODE\x00"):
            value = value.split(b"\x00", 1)[-1] if b"\x00" in value[8:] else value[8:]
        try:
            text = value.decode("utf-8", errors="replace").strip("\x00").strip()
            return text if text.isprintable() or " " in text else repr(value)
        except Exception:
            return repr(value)
    if isinstance(value, tuple) and value and all(isinstance(x, (int, float)) for x in value):
        return str(value)
    return str(value)


def _merge_exif_from_pillow(im: Image.Image, report: MetadataReport) -> None:
    try:
        exif = im.getexif()
    except Exception:
        return
    if not exif:
        return

    pointer_tags = {0x8769, 0x8825, 0xA005}  # ExifIFD, GPSIFD, InteropIFD
    for tag_id, value in exif.items():
        if tag_id in pointer_tags:
            continue
        name = TAGS.get(tag_id, f"Tag-{tag_id}")
        report.exif[name] = _decode_exif_value(value)
        report.has_exif = True

    try:
        exif_ifd = exif.get_ifd(IFD.Exif)
    except Exception:
        exif_ifd = {}
    for tag_id, value in (exif_ifd or {}).items():
        name = TAGS.get(tag_id, f"Exif-{tag_id}")
        report.exif[name] = _decode_exif_value(value)
        report.has_exif = True

    try:
        gps_ifd = exif.get_ifd(IFD.GPSInfo)
    except Exception:
        gps_ifd = {}
    for tag_id, value in (gps_ifd or {}).items():
        name = GPSTAGS.get(tag_id, GPS_TAG_NAMES.get(tag_id, f"GPS:{tag_id}"))
        report.gps[name] = _decode_exif_value(value)


def _merge_exif_from_piexif(exif_bytes: bytes, report: MetadataReport) -> None:
    data = exif_bytes
    if not data:
        return
    if not data.startswith(b"Exif\x00\x00"):
        data = b"Exif\x00\x00" + data
    try:
        exif_dict = piexif.load(data)
    except Exception:
        if not report.has_exif:
            report.has_exif = True
            report.exif["(raw)"] = f"{len(exif_bytes)} bytes, could not parse"
        return

    report.has_exif = True
    pointer_tags = {piexif.ImageIFD.ExifTag, piexif.ImageIFD.GPSTag}
    for ifd_name in ("0th", "Exif", "1st"):
        for tag_id, value in exif_dict.get(ifd_name, {}).items():
            if ifd_name == "0th" and tag_id in pointer_tags:
                continue
            try:
                name = piexif.TAGS[ifd_name][tag_id]["name"]
            except KeyError:
                name = f"{ifd_name}:{tag_id}"
            if name not in report.exif:
                report.exif[name] = _decode_exif_value(value)
    for tag_id, value in exif_dict.get("GPS", {}).items():
        name = GPS_TAG_NAMES.get(tag_id, f"GPS:{tag_id}")
        if name not in report.gps:
            report.gps[name] = _decode_exif_value(value)


def read_metadata(path: str) -> MetadataReport:
    report = MetadataReport(path=path)
    with open(path, "rb") as f:
        raw = f.read()

    with Image.open(io.BytesIO(raw)) as im:
        report.format = im.format or ""
        report.size = im.size
        report.mode = im.mode
        report.file_size_bytes = len(raw)
        report.has_icc = "icc_profile" in im.info and bool(im.info.get("icc_profile"))

        _merge_exif_from_pillow(im, report)
        exif_bytes = im.info.get("exif")
        if exif_bytes:
            _merge_exif_from_piexif(bytes(exif_bytes), report)

        try:
            iptc_raw = IptcImagePlugin.getiptcinfo(im)
        except Exception:
            iptc_raw = None
        if iptc_raw:
            for key, value in iptc_raw.items():
                label = _COMMON_IPTC.get(key, f"IPTC {key}")
                if isinstance(value, list):
                    value = ", ".join(
                        v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v)
                        for v in value
                    )
                elif isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                report.iptc[label] = value

        xmp = im.info.get("xmp")
        if xmp:
            blob = xmp if isinstance(xmp, bytes) else str(xmp).encode("utf-8", "replace")
            report.other_segments.append(
                scan.SegmentInfo("XMP (Pillow)", len(blob), scan._xmp_hint(blob))
            )

        if report.format == "PNG":
            for key, value in im.info.items():
                if key.lower() in _PNG_SKIP_INFO or not isinstance(value, (str, bytes)):
                    continue
                text = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
                report.other_segments.append(
                    scan.SegmentInfo(f"PNG info:{key}", len(text), text[:120])
                )

        raw_scan = scan.scan_bytes(raw, report.format)
        existing = {(s.label, s.size, s.detail) for s in report.other_segments}
        for seg in raw_scan.segments:
            key = (seg.label, seg.size, seg.detail)
            if key not in existing:
                report.other_segments.append(seg)
                existing.add(key)

    report.ai_signals = scan.find_ai_markers(raw)
    if scan.detect_xai_signature(report.exif):
        if "xAI/Grok EXIF signature (Artist UUID + Signature blob)" not in report.ai_signals:
            report.ai_signals.append("xAI/Grok EXIF signature (Artist UUID + Signature blob)")
    for seg in report.other_segments:
        if any(tok in seg.label for tok in ("C2PA", "generation", "AIGC", "JUMBF")):
            if seg.label not in report.ai_signals:
                report.ai_signals.append(seg.label)
    return report


def _jpeg_camera_container(data: bytes) -> bytes:
    """Drop JFIF APP0 and Adobe APP14 so the file looks like a camera JPEG.

    Pillow always writes those software-export markers. Windows Details and
    forensic tools treat a JFIF-only header as 'no camera metadata' even when
    APP1 EXIF is present later in the file.
    """
    if data[:2] != b"\xff\xd8":
        return data
    out = bytearray(b"\xff\xd8")
    pos = 2
    n = len(data)
    while pos + 4 <= n:
        if data[pos] != 0xFF:
            out.extend(data[pos:])
            break
        marker = struct.unpack(">H", data[pos:pos + 2])[0]
        if marker == 0xFFDA:
            out.extend(data[pos:])
            break
        if marker in (0xFFD8, 0xFFD9) or 0xFFD0 <= marker <= 0xFFD7 or marker == 0xFF01:
            out.extend(data[pos:pos + 2])
            pos += 2
            continue
        seglen = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        block = data[pos:pos + 2 + seglen]
        payload = block[4:]
        drop = False
        if marker == 0xFFE0 and payload.startswith((b"JFIF", b"JFXX")):
            drop = True
        elif marker == 0xFFEE and payload.startswith(b"Adobe"):
            drop = True
        if not drop:
            out.extend(block)
        pos += 2 + seglen
    return bytes(out)


def _write_jpeg_with_exif(path: str, image: Image.Image, exif_bytes: bytes | None, quality: int) -> None:
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    save_kwargs = {
        "format": "JPEG",
        "quality": quality,
        "optimize": False,
        "progressive": False,
        "subsampling": "4:2:0",
    }
    buf = io.BytesIO()
    image.save(buf, **save_kwargs)
    data = buf.getvalue()
    if exif_bytes:
        out = io.BytesIO()
        piexif.insert(exif_bytes, data, out)
        data = out.getvalue()
    data = _jpeg_camera_container(data)
    if exif_bytes and b"Exif\x00\x00" not in data[:4096]:
        app1 = b"\xff\xe1" + struct.pack(">H", len(exif_bytes) + 2) + exif_bytes
        data = data[:2] + app1 + data[2:]
        data = _jpeg_camera_container(data)
    with open(path, "wb") as f:
        f.write(data)


def strip_and_save(
    src_path: str,
    dst_path: str,
    *,
    fake_exif_bytes: bytes | None = None,
    preset_key: str | None = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    disrupt_watermarks: bool = False,
    watermark_strength: str = "medium",
    jpeg_quality: int = 93,
    photo_realism: bool = False,
    force_jpeg: bool = False,
    social_look: bool = False,
    aspect: str = "none",
    pixel_strength: str | None = None,
    anti_ai: bool = False,
) -> str:
    """Rebuild from raw pixels and save. Returns the actual output path."""
    from . import presets as pr
    from . import realism

    with Image.open(src_path) as src:
        src.load()
        mode = src.mode
        clean = Image.new(mode, src.size)
        clean.putdata(list(src.getdata()))

    if pixel_strength is None:
        if social_look or photo_realism:
            pixel_strength = "subtle"
        elif disrupt_watermarks:
            pixel_strength = {
                "light": "subtle", "medium": "subtle", "subtle": "subtle",
                "strong": "strong", "nuclear": "nuclear",
            }.get(watermark_strength, "subtle")

    if social_look:
        force_jpeg = True

    if anti_ai:
        clean = realism.anti_ai_pass(clean, aspect=aspect)
        force_jpeg = True
        jpeg_quality = min(jpeg_quality, 82)
    elif pixel_strength:
        clean = realism.structure_pass(clean, strength=pixel_strength, aspect=aspect)
    elif aspect and aspect != "none":
        clean = realism.apply_aspect(clean.convert("RGB") if clean.mode != "RGB" else clean, aspect)

    want_jpeg = bool(fake_exif_bytes or preset_key or force_jpeg or social_look or pixel_strength or anti_ai)
    if want_jpeg:
        root, _ = os.path.splitext(dst_path)
        dst_path = root + ".jpg"

    if preset_key:
        fake_exif_bytes = pr.build_exif_bytes(
            preset_key,
            width=clean.size[0],
            height=clean.size[1],
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            image=clean,
        )

    ext = os.path.splitext(dst_path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        _write_jpeg_with_exif(dst_path, clean, fake_exif_bytes, jpeg_quality)
        return dst_path

    save_kwargs: dict = {}
    if ext == ".png":
        save_kwargs["optimize"] = True
    elif ext in (".tif", ".tiff"):
        if fake_exif_bytes:
            save_kwargs["exif"] = fake_exif_bytes
    elif ext == ".webp":
        save_kwargs["quality"] = jpeg_quality
        if fake_exif_bytes:
            save_kwargs["exif"] = fake_exif_bytes
    clean.save(dst_path, **save_kwargs)
    return dst_path
