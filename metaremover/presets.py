"""Built-in fake-EXIF device presets.

iPhone Make/Model/LensModel strings match what Apple Camera writes.
Software is the iOS version only (e.g. "26.6.1"), which is how real dumps
look in 2026. Default pick is iPhone 17 — current volume device as of
Sept 2026. iPhone 15 is a year stale.

EXIF only exists on JPEG/HEIC. PNG has no camera EXIF on a real iPhone;
if a preset is selected we save JPEG.
"""
from __future__ import annotations

import datetime
import io
import math
import random
from dataclasses import dataclass, field

import piexif
from PIL import Image


@dataclass
class DevicePreset:
    key: str
    label: str
    make: str
    model: str
    software: str
    lens_model: str
    f_number: float
    focal_length_mm: float
    focal_length_35mm: int
    iso: int
    exposure_time: tuple[int, int] = (1, 120)
    extra_exif: dict = field(default_factory=dict)
    color_space: int = 1  # Apple writes 65535 (Uncalibrated)
    lens_min_mm: float = 0.0
    lens_max_mm: float = 0.0
    f_min: float = 0.0
    f_max: float = 0.0


# Newest first. Camera numbers from Apple spec pages / public EXIF dumps.
PRESETS: dict[str, DevicePreset] = {
    "iphone18": DevicePreset(
        key="iphone18",
        label="iPhone 18 (newest)",
        make="Apple",
        model="iPhone 18",
        software="26.6.1",
        lens_model="iPhone 18 back dual camera 6.765mm f/1.6",
        f_number=1.6,
        focal_length_mm=6.765,
        focal_length_35mm=26,
        iso=64,
    ),
    "iphone18pro": DevicePreset(
        key="iphone18pro",
        label="iPhone 18 Pro",
        make="Apple",
        model="iPhone 18 Pro",
        software="26.6.1",
        lens_model="iPhone 18 Pro back triple camera 6.765mm f/1.78",
        f_number=1.78,
        focal_length_mm=6.765,
        focal_length_35mm=24,
        iso=50,
    ),
    "iphone17": DevicePreset(
        key="iphone17",
        label="iPhone 17 (recommended)",
        make="Apple",
        model="iPhone 17",
        software="26.6.1",
        lens_model="iPhone 17 back dual camera 6.765mm f/1.6",
        f_number=1.6,
        focal_length_mm=6.765,
        focal_length_35mm=26,
        iso=64,
    ),
    "iphone17pro": DevicePreset(
        key="iphone17pro",
        label="iPhone 17 Pro",
        make="Apple",
        model="iPhone 17 Pro",
        software="26.6.1",
        lens_model="iPhone 17 Pro back dual wide camera 6.765mm f/1.78",
        f_number=1.78,
        focal_length_mm=6.765,
        focal_length_35mm=24,
        iso=50,
    ),
    "iphone16": DevicePreset(
        key="iphone16",
        label="iPhone 16",
        make="Apple",
        model="iPhone 16",
        software="26.6.1",
        lens_model="iPhone 16 back camera 6.765mm f/1.6",
        f_number=1.6,
        focal_length_mm=6.765,
        focal_length_35mm=26,
        iso=64,
    ),
    "iphone17promax": DevicePreset(
        key="iphone17promax",
        label="iPhone 17 Pro Max",
        make="Apple",
        model="iPhone 17 Pro Max",
        software="26.6.1",
        lens_model="iPhone 17 Pro Max back dual wide camera 6.765mm f/1.78",
        f_number=1.78,
        focal_length_mm=6.765,
        focal_length_35mm=24,
        iso=50,
    ),
    "iphone16pro": DevicePreset(
        key="iphone16pro",
        label="iPhone 16 Pro",
        make="Apple",
        model="iPhone 16 Pro",
        software="26.6.1",
        lens_model="iPhone 16 Pro back triple camera 6.765mm f/1.78",
        f_number=1.78,
        focal_length_mm=6.765,
        focal_length_35mm=24,
        iso=50,
    ),
    "iphone15": DevicePreset(
        key="iphone15",
        label="iPhone 15",
        make="Apple",
        model="iPhone 15",
        software="18.6.2",
        lens_model="iPhone 15 back camera 6.765mm f/1.6",
        f_number=1.6,
        focal_length_mm=6.765,
        focal_length_35mm=26,
        iso=64,
    ),
    "iphone15pro": DevicePreset(
        key="iphone15pro",
        label="iPhone 15 Pro",
        make="Apple",
        model="iPhone 15 Pro",
        software="18.6.2",
        lens_model="iPhone 15 Pro back triple camera 6.765mm f/1.78",
        f_number=1.78,
        focal_length_mm=6.765,
        focal_length_35mm=24,
        iso=64,
    ),
    "iphone14": DevicePreset(
        key="iphone14",
        label="iPhone 14",
        make="Apple",
        model="iPhone 14",
        software="18.6.2",
        lens_model="iPhone 14 back dual camera 5.7mm f/1.5",
        f_number=1.5,
        focal_length_mm=5.7,
        focal_length_35mm=26,
        iso=50,
    ),
    "iphone14pro": DevicePreset(
        key="iphone14pro",
        label="iPhone 14 Pro",
        make="Apple",
        model="iPhone 14 Pro",
        software="18.6.2",
        lens_model="iPhone 14 Pro back triple camera 6.86mm f/1.78",
        f_number=1.78,
        focal_length_mm=6.86,
        focal_length_35mm=24,
        iso=64,
    ),
    "iphone13": DevicePreset(
        key="iphone13",
        label="iPhone 13",
        make="Apple",
        model="iPhone 13",
        software="18.6.2",
        lens_model="iPhone 13 back dual camera 5.1mm f/1.6",
        f_number=1.6,
        focal_length_mm=5.1,
        focal_length_35mm=26,
        iso=50,
    ),
    "iphone13pro": DevicePreset(
        key="iphone13pro",
        label="iPhone 13 Pro",
        make="Apple",
        model="iPhone 13 Pro",
        software="18.6.2",
        lens_model="iPhone 13 Pro back triple camera 5.7mm f/1.5",
        f_number=1.5,
        focal_length_mm=5.7,
        focal_length_35mm=26,
        iso=50,
    ),
    "galaxys24": DevicePreset(
        key="galaxys24",
        label="Samsung Galaxy S24",
        make="samsung",
        model="SM-S921B",
        software="S921BXXU2AXE5",
        lens_model="",
        f_number=1.8,
        focal_length_mm=5.4,
        focal_length_35mm=24,
        iso=50,
    ),
    "pixel8": DevicePreset(
        key="pixel8",
        label="Google Pixel 8",
        make="Google",
        model="Pixel 8",
        software="BP2A.250805.005",
        lens_model="",
        f_number=1.68,
        focal_length_mm=6.81,
        focal_length_35mm=25,
        iso=50,
    ),
    "pixel9": DevicePreset(
        key="pixel9",
        label="Google Pixel 9",
        make="Google",
        model="Pixel 9",
        software="BP2A.260805.005",
        lens_model="",
        f_number=1.68,
        focal_length_mm=6.81,
        focal_length_35mm=25,
        iso=50,
    ),
    "pixel10": DevicePreset(
        key="pixel10",
        label="Google Pixel 10",
        make="Google",
        model="Pixel 10",
        software="BP2A.260805.005",
        lens_model="",
        f_number=1.68,
        focal_length_mm=6.81,
        focal_length_35mm=25,
        iso=64,
    ),
    "galaxys25": DevicePreset(
        key="galaxys25",
        label="Samsung Galaxy S25",
        make="samsung",
        model="SM-S931B",
        software="S931BXXU2AYE5",
        lens_model="",
        f_number=1.8,
        focal_length_mm=5.4,
        focal_length_35mm=24,
        iso=50,
    ),
}

for _p in PRESETS.values():
    if _p.make == "Apple":
        _p.color_space = 65535  # Uncalibrated, as Apple Camera writes
        if not _p.lens_min_mm:
            _p.lens_min_mm = 2.22
            _p.lens_max_mm = _p.focal_length_mm
            _p.f_min = _p.f_number
            _p.f_max = 2.2


def _rational(value: float, denom: int = 1000) -> tuple[int, int]:
    return (int(round(value * denom)), denom)


def _srational(value: float, denom: int = 1000) -> tuple[int, int]:
    return (int(round(value * denom)), denom)


def _exposure_from_image(image: Image.Image | None, fallback_iso: int) -> tuple[int, tuple[int, int]]:
    iso = fallback_iso
    exposure = (1, 120)
    if image is None:
        return iso, exposure
    gray = image.convert("L").resize((32, 32)).getextrema()
    mid = (gray[0] + gray[1]) / 2.0
    if mid < 40:
        iso, exposure = random.choice([640, 800, 1000]), (1, 30)
    elif mid < 80:
        iso, exposure = random.choice([200, 250, 320]), (1, 60)
    elif mid < 140:
        iso, exposure = random.choice([50, 64, 80]), (1, 120)
    else:
        iso, exposure = random.choice([32, 40, 50]), random.choice([(1, 160), (1, 200), (1, 250)])
    return iso, exposure


def _jpeg_thumbnail(image: Image.Image) -> bytes:
    thumb = image.convert("RGB").copy()
    thumb.thumbnail((320, 240), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=70, subsampling="4:2:0", optimize=False)
    return buf.getvalue()


def build_exif_bytes(
    preset_key: str,
    *,
    width: int,
    height: int,
    when: datetime.datetime | None = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    image: Image.Image | None = None,
) -> bytes:
    preset = PRESETS[preset_key]
    if when is None:
        when = datetime.datetime.now().astimezone() - datetime.timedelta(
            hours=random.randint(0, 72),
            seconds=random.randint(0, 3599),
        )
    elif when.tzinfo is None:
        when = when.astimezone()
    dt_str = when.strftime("%Y:%m:%d %H:%M:%S")
    offset = when.strftime("%z")
    offset_fmt = f"{offset[:3]}:{offset[3:]}" if offset else "+00:00"
    subsec = f"{when.microsecond // 1000:03d}"
    iso, exposure = _exposure_from_image(image, preset.iso)
    shutter_apex = math.log2(exposure[1] / max(exposure[0], 1))
    aperture_apex = 2.0 * math.log2(max(preset.f_number, 1.0))

    zeroth = {
        piexif.ImageIFD.Make: preset.make,
        piexif.ImageIFD.Model: preset.model,
        piexif.ImageIFD.Software: preset.software,
        piexif.ImageIFD.DateTime: dt_str,
        piexif.ImageIFD.Orientation: 1,
        piexif.ImageIFD.XResolution: (72, 1),
        piexif.ImageIFD.YResolution: (72, 1),
        piexif.ImageIFD.ResolutionUnit: 2,
        piexif.ImageIFD.YCbCrPositioning: 1,
        piexif.ImageIFD.HostComputer: preset.model,
    }

    exif_ifd = {
        piexif.ExifIFD.ExifVersion: b"0232",
        piexif.ExifIFD.DateTimeOriginal: dt_str,
        piexif.ExifIFD.DateTimeDigitized: dt_str,
        piexif.ExifIFD.OffsetTime: offset_fmt,
        piexif.ExifIFD.OffsetTimeOriginal: offset_fmt,
        piexif.ExifIFD.OffsetTimeDigitized: offset_fmt,
        piexif.ExifIFD.SubSecTime: subsec,
        piexif.ExifIFD.SubSecTimeOriginal: subsec,
        piexif.ExifIFD.SubSecTimeDigitized: subsec,
        piexif.ExifIFD.ExposureTime: exposure,
        piexif.ExifIFD.FNumber: _rational(preset.f_number, 100),
        piexif.ExifIFD.ISOSpeedRatings: iso,
        piexif.ExifIFD.ExposureProgram: 2,
        piexif.ExifIFD.MeteringMode: 5,
        piexif.ExifIFD.Flash: 16,
        piexif.ExifIFD.FocalLength: _rational(preset.focal_length_mm, 1000),
        piexif.ExifIFD.FocalLengthIn35mmFilm: preset.focal_length_35mm,
        piexif.ExifIFD.ColorSpace: preset.color_space,
        piexif.ExifIFD.PixelXDimension: width,
        piexif.ExifIFD.PixelYDimension: height,
        piexif.ExifIFD.WhiteBalance: 0,
        piexif.ExifIFD.ExposureBiasValue: (0, 1),
        piexif.ExifIFD.SceneCaptureType: 0,
        piexif.ExifIFD.SensingMethod: 2,
        piexif.ExifIFD.ComponentsConfiguration: b"\x01\x02\x03\x00",
        piexif.ExifIFD.ShutterSpeedValue: _srational(shutter_apex, 1000),
        piexif.ExifIFD.ApertureValue: _rational(aperture_apex, 1000),
        piexif.ExifIFD.BrightnessValue: _srational(max(-4.0, min(12.0, shutter_apex + aperture_apex - 5)), 1000),
        piexif.ExifIFD.LensSpecification: (
            _rational(preset.lens_min_mm or preset.focal_length_mm, 1000),
            _rational(preset.lens_max_mm or preset.focal_length_mm, 1000),
            _rational(preset.f_min or preset.f_number, 100),
            _rational(preset.f_max or preset.f_number, 100),
        ),
        piexif.ExifIFD.SceneType: b"\x01",
        piexif.ExifIFD.FileSource: b"\x03",
        piexif.ExifIFD.ExposureMode: 0,
        piexif.ExifIFD.DigitalZoomRatio: (1, 1),
        piexif.ExifIFD.MaxApertureValue: _rational(aperture_apex, 1000),
        piexif.ExifIFD.LightSource: 0,
        piexif.ExifIFD.SubjectArea: (
            max(1, width // 2),
            max(1, height // 2),
            max(8, width // 5),
            max(8, height // 5),
        ),
    }
    if preset.lens_model:
        exif_ifd[piexif.ExifIFD.LensModel] = preset.lens_model
        exif_ifd[piexif.ExifIFD.LensMake] = preset.make

    gps_ifd = {}
    if gps_lat is not None and gps_lon is not None:
        gps_ifd = _build_gps_ifd(gps_lat, gps_lon, when)

    thumb = _jpeg_thumbnail(image) if image is not None else None
    first = {}
    if thumb:
        first = {
            piexif.ImageIFD.Compression: 6,
            piexif.ImageIFD.XResolution: (72, 1),
            piexif.ImageIFD.YResolution: (72, 1),
            piexif.ImageIFD.ResolutionUnit: 2,
        }

    exif_dict = {
        "0th": zeroth,
        "Exif": exif_ifd,
        "GPS": gps_ifd,
        "1st": first,
        "thumbnail": thumb,
        "Interop": {
            piexif.InteropIFD.InteroperabilityIndex: "R98",
        },
    }
    return piexif.dump(exif_dict)


def _to_dms_rational(value: float) -> tuple:
    value = abs(value)
    degrees = int(value)
    minutes_full = (value - degrees) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60
    return (
        (degrees, 1),
        (minutes, 1),
        (int(round(seconds * 100)), 100),
    )


def _build_gps_ifd(lat: float, lon: float, when: datetime.datetime) -> dict:
    return {
        piexif.GPSIFD.GPSVersionID: (2, 3, 0, 0),
        piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S",
        piexif.GPSIFD.GPSLatitude: _to_dms_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W",
        piexif.GPSIFD.GPSLongitude: _to_dms_rational(lon),
        piexif.GPSIFD.GPSAltitudeRef: 0,
        piexif.GPSIFD.GPSAltitude: (random.randint(8, 48), 1),
        piexif.GPSIFD.GPSImgDirectionRef: "T",
        piexif.GPSIFD.GPSImgDirection: _rational(random.uniform(0, 359.9), 100),
        piexif.GPSIFD.GPSHPositioningError: (random.randint(4, 14), 1),
        piexif.GPSIFD.GPSSpeedRef: "K",
        piexif.GPSIFD.GPSSpeed: (0, 1),
        piexif.GPSIFD.GPSTimeStamp: (
            (when.hour, 1),
            (when.minute, 1),
            (when.second, 1),
        ),
        piexif.GPSIFD.GPSDateStamp: when.strftime("%Y:%m:%d"),
    }
