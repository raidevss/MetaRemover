"""Low-level byte scanning for metadata Pillow does not surface.

Used for the before/after report. The strip path rebuilds from pixels, so
these segments are dropped regardless of type.

AI-string matching is restricted to metadata regions (JPEG markers before
SOS, PNG chunks except IDAT, WEBP/ISOBMFF boxes except coded image data)
so compressed pixels cannot produce fake 'c2pa' / vendor hits.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class SegmentInfo:
    label: str
    size: int
    detail: str = ""


@dataclass
class RawScanResult:
    segments: list[SegmentInfo] = field(default_factory=list)
    metadata_bytes: bytes = b""

    def add(self, label: str, size: int, detail: str = "") -> None:
        self.segments.append(SegmentInfo(label, size, detail))


_JPEG_APPN_KNOWN = {
    0xFFE0: "APP0 (JFIF)",
    0xFFE1: "APP1 (Exif/XMP)",
    0xFFE2: "APP2 (ICC profile)",
    0xFFED: "APP13 (Photoshop/IPTC)",
    0xFFEE: "APP14 (Adobe)",
    0xFFEB: "APP11 (JPEG-XT/JUMBF, e.g. C2PA content credentials)",
}

# Distinctive provenance / generator fingerprints. Short generic tokens like
# "adobe" / "apple" / "google" are omitted — they appear in ICC profiles.
_AI_MARKERS = (
    b"trainedAlgorithmicMedia",
    b"TrainedAlgorithmicMedia",
    b"compositeWithTrainedAlgorithmicMedia",
    b"compositeSynthetic",
    b"computationalCapture",
    b"DigitalSourceType",
    b"Content Credentials",
    b"c2pa.actions.gen-ai",
    b"c2pa.software-agent",
    b"SynthID",
    b"synthid",
    b"InvisMark",
    b"ContentSeal",
    b"Content Seal",
)

_VENDOR_MARKERS = (
    b"midjourney",
    b"stable diffusion",
    b"stablediffusion",
    b"comfyui",
    b"automatic1111",
    b"invokeai",
    b"dall-e",
    "dall·e".encode("utf-8"),
    b"chatgpt",
    b"openai",
    b"gpt-image",
    b"gpt-image-1",
    b"gemini",
    b"imagen",
    b"nano banana",
    b"nanobanana",
    b"firefly",
    b"seedream",
    b"flux.2",
    b"flux1",
    b"black forest labs",
    b"grok imagine",
    b"imagine-public.x.ai",
    b"dreamina",
    b"novelai",
    b"ideogram",
    b"recraft",
    b"runwayml",
    b"kling",
    b"luma ai",
    b"pika labs",
    b"higgsfield",
    b"leonardo.ai",
    b"seaart",
    b"liblib",
    b"jimeng",
    b"doubao",
    b"volcengine",
    b"microsoft designer",
    b"bing image",
    b"copilot",
    b"pixel studio",
    b"apple intelligence",
    b"image playground",
    b"canva",
    b"bria.ai",
    b"elevenlabs",
)

_AI_TEXT_KEYS = {
    "parameters",
    "prompt",
    "negative_prompt",
    "negative prompt",
    "workflow",
    "comment",
    "software",
    "aigc",
    "label",
    "contentproducer",
    "sd-metadata",
    "invokeai_metadata",
    "comfyui",
    "dream",
    "usercomment",
    "hf-job-id",
    "genaitype",
}

_XAI_SIG_RE = re.compile(rb"^Signature:\s+[A-Za-z0-9+/=]{64,}")

# C2PA JUMBF in ISO-BMFF (AVIF/HEIC) uses this UUID.
_C2PA_UUID = bytes.fromhex("6332706100110010800000aa00389b71")


def metadata_region(raw: bytes) -> bytes:
    """Container bytes that can hold metadata, with coded pixels removed."""
    if raw[:2] == b"\xff\xd8":
        return _jpeg_metadata_region(raw)
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return _png_metadata_region(raw)
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return _webp_metadata_region(raw)
    if len(raw) >= 12 and raw[4:8] == b"ftyp":
        return _isobmff_metadata_region(raw)
    if raw[:4] in (b"II*\x00", b"MM\x00*"):
        return raw[: min(len(raw), 256 * 1024)]
    return raw[: min(len(raw), 64 * 1024)]


def find_ai_markers(raw: bytes) -> list[str]:
    """String scan of the metadata region for provenance / generator fingerprints."""
    region = metadata_region(raw)
    found: list[str] = []
    lower = region.lower()

    def add(label: str) -> None:
        if label not in found:
            found.append(label)

    for marker in _AI_MARKERS:
        if marker.lower() in lower:
            add(marker.decode("latin-1", "replace"))

    # JUMBF fourcc / C2PA box types — too short to search in pixels.
    if b"c2pa" in lower or b"jumb" in lower:
        add("C2PA/JUMBF box")
    if b"cabx" in lower:
        add("PNG caBX (C2PA Content Credentials)")

    for vendor in _VENDOR_MARKERS:
        if vendor in lower:
            add(vendor.decode("utf-8", "replace"))

    if b"dcterms:provenance" in lower or b"c2pa.org" in lower or b"contentcredentials.org" in lower:
        add("C2PA cloud / XMP provenance pointer")
    if b"aigc" in lower and (b"contentproducer" in lower or b'"label"' in lower or b"label" in lower):
        add("China AIGC label (TC260)")
    if b"genaitype" in lower:
        add("Samsung Galaxy AI genAIType")
    if b"hf-job-id" in lower or b"hf_job_id" in lower:
        add("Hugging Face job id")
    return found


def detect_xai_signature(exif_fields: dict) -> bool:
    """Grok JPEG downloads: Artist is a UUID, ImageDescription is 'Signature: <b64>'."""
    artist = str(exif_fields.get("Artist") or "").strip()
    desc = str(exif_fields.get("ImageDescription") or "").strip()
    if not artist or not desc:
        return False
    try:
        UUID(artist)
    except (ValueError, TypeError):
        return False
    return bool(_XAI_SIG_RE.match(desc.encode("utf-8", "replace")))


def scan_bytes(raw: bytes, fmt: str = "") -> RawScanResult:
    fmt = (fmt or "").upper()
    if fmt == "JPEG" or raw[:2] == b"\xff\xd8":
        return scan_jpeg(raw)
    if fmt == "PNG" or raw[:8] == b"\x89PNG\r\n\x1a\n":
        return scan_png(raw)
    if fmt == "WEBP" or (raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"):
        return scan_webp(raw)
    if fmt in ("AVIF", "HEIF", "HEIC") or (len(raw) >= 12 and raw[4:8] == b"ftyp"):
        return scan_isobmff(raw)
    if fmt in ("TIFF", "TIF") or raw[:4] in (b"II*\x00", b"MM\x00*"):
        result = RawScanResult()
        result.add("TIFF IFD metadata", min(len(raw), 256 * 1024))
        result.metadata_bytes = raw[: min(len(raw), 256 * 1024)]
        return result
    return RawScanResult()


def scan_jpeg(raw: bytes) -> RawScanResult:
    result = RawScanResult()
    if raw[:2] != b"\xff\xd8":
        return result
    meta = bytearray()
    pos = 2
    n = len(raw)
    while pos + 4 <= n:
        if raw[pos] != 0xFF:
            pos += 1
            continue
        marker = struct.unpack(">H", raw[pos:pos + 2])[0]
        if marker in (0xFFD8, 0xFFD9) or 0xFFD0 <= marker <= 0xFFD7:
            pos += 2
            continue
        if marker == 0xFFDA:
            break
        if pos + 4 > n:
            break
        seg_len = struct.unpack(">H", raw[pos + 2:pos + 4])[0]
        payload = raw[pos + 4:pos + 2 + seg_len]
        meta.extend(payload)

        if marker == 0xFFFE:
            text = payload.decode("latin-1", errors="replace")
            result.add("COM (comment)", len(payload), text[:120])
        elif marker == 0xFFE1:
            if payload.startswith(b"http://ns.adobe.com/xap/1.0/\x00"):
                xmp_bytes = payload[len(b"http://ns.adobe.com/xap/1.0/\x00"):]
                result.add("XMP metadata", len(xmp_bytes), _xmp_hint(xmp_bytes))
            elif payload.startswith(b"http://ns.adobe.com/xmp/extension/\x00"):
                result.add("XMP Extended", len(payload))
            elif payload.startswith(b"Exif\x00\x00"):
                result.add("EXIF (APP1)", len(payload) - 6)
            else:
                result.add("APP1 (unrecognized)", len(payload))
        elif marker == 0xFFE2:
            if payload.startswith(b"ICC_PROFILE\x00"):
                result.add("ICC color profile", len(payload))
            elif payload.startswith(b"MPF\x00"):
                result.add("Multi-Picture Format (MPF)", len(payload))
            else:
                result.add("APP2 (unrecognized)", len(payload))
        elif marker == 0xFFED:
            if payload.startswith(b"Photoshop 3.0\x00"):
                result.add("Photoshop/IPTC resource block", len(payload))
            else:
                result.add("APP13 (unrecognized)", len(payload))
        elif marker == 0xFFEE:
            result.add("Adobe APP14 (encoder tag — not a camera JPEG)", len(payload))
        elif marker == 0xFFEB:
            result.add("APP11 (JUMBF / C2PA content credentials)", len(payload))
        elif marker == 0xFFE0:
            if payload.startswith(b"JFIF"):
                result.add("JFIF header", len(payload), "software-export tell; cameras usually omit this")
            elif payload.startswith(b"JFXX"):
                result.add("JFIF thumbnail (JFXX)", len(payload))
        elif 0xFFE0 <= marker <= 0xFFEF:
            result.add(_JPEG_APPN_KNOWN.get(marker, f"APPn 0x{marker:04X}"), len(payload))

        pos += 2 + seg_len

    result.metadata_bytes = bytes(meta)
    return result


def scan_png(raw: bytes) -> RawScanResult:
    result = RawScanResult()
    sig = b"\x89PNG\r\n\x1a\n"
    if raw[:8] != sig:
        return result

    interesting = {
        b"tEXt": "PNG text chunk",
        b"zTXt": "PNG compressed text chunk",
        b"iTXt": "PNG international text chunk",
        b"eXIf": "PNG Exif chunk",
        b"iCCP": "PNG ICC profile chunk",
        b"tIME": "PNG last-modified timestamp chunk",
        b"pHYs": "PNG physical pixel dimensions chunk",
        b"caBX": "C2PA Content Credentials (caBX)",
        b"C2PA": "C2PA data chunk",
        b"C2CI": "C2PA content information chunk",
        b"C2CS": "C2PA signature chunk",
        b"jUMB": "JUMBF box (C2PA)",
        b"orNT": "PNG EXIF orientation chunk",
    }
    meta = bytearray()
    pos = 8
    n = len(raw)
    while pos + 8 <= n:
        length = struct.unpack(">I", raw[pos:pos + 4])[0]
        ctype = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + length]
        if ctype != b"IDAT":
            meta.extend(ctype)
            meta.extend(data[: min(len(data), 64 * 1024)])
        if ctype in interesting:
            detail = ""
            if ctype == b"tEXt":
                keyword, _, text = data.partition(b"\x00")
                key = keyword.decode("latin-1", "replace")
                detail = f"{key}: {text.decode('latin-1', 'replace')[:100]}"
                if key.lower() in _AI_TEXT_KEYS:
                    result.add("AI generation parameters", length, key)
            elif ctype == b"iTXt":
                keyword = data.split(b"\x00", 1)[0]
                key = keyword.decode("latin-1", errors="replace")
                detail = key
                blob = data.lower()
                if key.lower() in _AI_TEXT_KEYS or b"aigc" in blob or b"trainedalgorithmic" in blob:
                    result.add("AI / AIGC label (iTXt)", length, key)
                if key in ("XML:com.adobe.xmp", "xml:com.adobe.xmp"):
                    result.add("XMP in PNG iTXt", length, _xmp_hint(data))
            elif ctype == b"zTXt":
                keyword = data.split(b"\x00", 1)[0]
                detail = f"{keyword.decode('latin-1', errors='replace')} (compressed)"
            result.add(interesting[ctype], length, detail)
        if ctype == b"IEND":
            break
        pos += 8 + length + 4
    result.metadata_bytes = bytes(meta)
    return result


def scan_webp(raw: bytes) -> RawScanResult:
    result = RawScanResult()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
        return result
    meta = bytearray()
    pos = 12
    n = len(raw)
    while pos + 8 <= n:
        fourcc = raw[pos:pos + 4]
        size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        data = raw[pos + 8:pos + 8 + size]
        if fourcc not in (b"VP8 ", b"VP8L", b"VP8X", b"ANIM", b"ANMF", b"ALPH"):
            meta.extend(fourcc)
            meta.extend(data[: min(len(data), 64 * 1024)])
        if fourcc == b"EXIF":
            result.add("WEBP EXIF chunk", size)
        elif fourcc == b"XMP ":
            result.add("WEBP XMP chunk", size, _xmp_hint(data))
        elif fourcc == b"ICCP":
            result.add("WEBP ICC profile", size)
        elif fourcc in (b"C2PA", b"c2pa"):
            result.add("WEBP C2PA chunk", size)
        pos += 8 + size + (size & 1)
    result.metadata_bytes = bytes(meta)
    return result


def scan_isobmff(raw: bytes) -> RawScanResult:
    """AVIF / HEIC / HEIF boxes."""
    result = RawScanResult()
    if len(raw) < 12 or raw[4:8] != b"ftyp":
        return result
    brand = raw[8:12].decode("latin-1", "replace")
    result.add("ISOBMFF ftyp", 12, f"brand {brand}")
    meta = bytearray()

    def walk(buf: bytes, offset: int, end: int, depth: int = 0) -> None:
        pos = offset
        while pos + 8 <= end:
            size = struct.unpack(">I", buf[pos:pos + 4])[0]
            btype = buf[pos + 4:pos + 8]
            header = 8
            if size == 1 and pos + 16 <= end:
                size = struct.unpack(">Q", buf[pos + 8:pos + 16])[0]
                header = 16
            if size == 0:
                size = end - pos
            if size < header:
                break
            box_end = min(pos + size, end)
            payload = buf[pos + header:box_end]
            if btype not in (b"mdat", b"idat", b"m1ds"):
                meta.extend(btype)
                meta.extend(payload[: min(len(payload), 32 * 1024)])
            if btype in (b"meta", b"moov", b"iprp", b"ipco", b"iref", b"iinf"):
                if depth < 6:
                    walk(buf, pos + header, box_end, depth + 1)
            elif btype == b"xml ":
                result.add("ISOBMFF XML (often XMP)", len(payload), _xmp_hint(payload))
            elif btype in (b"c2pa", b"jumb", b"uuid"):
                label = "C2PA uuid box" if btype == b"uuid" else f"ISOBMFF {btype.decode('latin-1')} box"
                if btype == b"uuid" and payload[:16] == _C2PA_UUID:
                    label = "C2PA Content Credentials (uuid)"
                elif btype == b"uuid" and _C2PA_UUID not in payload[:32] and b"c2pa" not in payload[:64].lower():
                    pos = box_end
                    continue
                result.add(label, len(payload))
            pos = box_end

    walk(raw, 0, min(len(raw), 2 * 1024 * 1024))
    result.metadata_bytes = bytes(meta)
    return result


def _jpeg_metadata_region(raw: bytes) -> bytes:
    out = bytearray()
    pos = 2
    n = min(len(raw), 2 * 1024 * 1024)
    while pos + 4 <= n:
        if raw[pos] != 0xFF:
            return raw[:n]
        marker = raw[pos + 1]
        if marker in (0xDA, 0xD9):
            end = raw.rfind(b"\xff\xd9")
            if end >= pos:
                out.extend(raw[end + 2:n])
            break
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            pos += 2
            continue
        length = int.from_bytes(raw[pos + 2:pos + 4], "big")
        if length < 2 or pos + 2 + length > n:
            break
        out.extend(raw[pos + 4:pos + 2 + length])
        pos += 2 + length
    return bytes(out)


def _png_metadata_region(raw: bytes) -> bytes:
    out = bytearray()
    pos = 8
    n = min(len(raw), 4 * 1024 * 1024)
    saw_idat = False
    while pos + 8 <= n:
        length = struct.unpack(">I", raw[pos:pos + 4])[0]
        ctype = raw[pos + 4:pos + 8]
        start = pos + 8
        if ctype != b"IDAT":
            out.extend(ctype)
            out.extend(raw[start:start + min(length, n - start)])
        else:
            saw_idat = True
        pos = start + length + 4
        if ctype == b"IEND":
            out.extend(raw[pos:n])
            break
    return bytes(out) if saw_idat else raw[:n]


def _webp_metadata_region(raw: bytes) -> bytes:
    out = bytearray()
    pos = 12
    n = len(raw)
    while pos + 8 <= n:
        fourcc = raw[pos:pos + 4]
        size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        data = raw[pos + 8:pos + 8 + size]
        if fourcc not in (b"VP8 ", b"VP8L", b"VP8X", b"ANIM", b"ANMF", b"ALPH"):
            out.extend(fourcc)
            out.extend(data)
        pos += 8 + size + (size & 1)
    return bytes(out)


def _isobmff_metadata_region(raw: bytes) -> bytes:
    out = bytearray()
    pos = 0
    n = min(len(raw), 2 * 1024 * 1024)
    while pos + 8 <= n:
        size = struct.unpack(">I", raw[pos:pos + 4])[0]
        btype = raw[pos + 4:pos + 8]
        header = 8
        if size == 1 and pos + 16 <= n:
            size = struct.unpack(">Q", raw[pos + 8:pos + 16])[0]
            header = 16
        if size == 0:
            size = n - pos
        if size < header:
            break
        payload = raw[pos + header:pos + min(size, n - pos)]
        if btype not in (b"mdat", b"idat"):
            out.extend(btype)
            out.extend(payload[: min(len(payload), 64 * 1024)])
        pos += size
    return bytes(out)


def _xmp_hint(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    hints = []
    for needle, label in (
        ("trainedAlgorithmicMedia", "trainedAlgorithmicMedia"),
        ("compositeWithTrainedAlgorithmicMedia", "compositeWithTrainedAlgorithmicMedia"),
        ("DigitalSourceType", "DigitalSourceType"),
        ("c2pa", "c2pa"),
        ("ChatGPT", "ChatGPT"),
        ("Firefly", "Firefly"),
        ("SynthID", "SynthID"),
    ):
        if needle.lower() in text.lower():
            hints.append(label)
    return ", ".join(hints[:6])
