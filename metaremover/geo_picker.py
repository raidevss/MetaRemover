"""Offline click-to-pick GPS map. No OSM tiles — land is bundled Natural Earth 110m."""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from . import theme

_LAND_PATH = Path(__file__).resolve().parent / "data" / "land-110m.json"


@lru_cache(maxsize=1)
def _land_rings() -> list[list[tuple[float, float]]]:
    topo = json.loads(_LAND_PATH.read_text(encoding="utf-8"))
    scale = topo["transform"]["scale"]
    translate = topo["transform"]["translate"]
    decoded: list[list[tuple[float, float]]] = []
    for arc in topo["arcs"]:
        x = y = 0
        pts: list[tuple[float, float]] = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * scale[0] + translate[0], y * scale[1] + translate[1]))
        decoded.append(pts)

    def ring(indexes: list[int]) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        for i in indexes:
            seg = decoded[i] if i >= 0 else list(reversed(decoded[~i]))
            if out:
                seg = seg[1:]
            out.extend(seg)
        return out

    rings: list[list[tuple[float, float]]] = []
    for geom in topo["objects"]["land"]["geometries"]:
        arcs = geom.get("arcs") or []
        gtype = geom.get("type")
        if gtype == "MultiPolygon":
            for poly in arcs:
                for r in poly:
                    rings.append(ring(r))
        elif gtype == "Polygon":
            for r in arcs:
                rings.append(ring(r))
    return rings


class GeoMap(QWidget):
    picked = Signal(float, float)

    def __init__(self, lat: float, lon: float, parent=None):
        super().__init__(parent)
        self.setMinimumSize(520, 360)
        self.setMouseTracking(True)
        self.lat = lat
        self.lon = lon
        self._cx = lon
        self._cy = lat
        self._zoom = 1.0
        self._drag = None
        self._moved = False
        self._hover: tuple[float, float] | None = None
        self._rings = _land_rings()

    def set_point(self, lat: float, lon: float, fly: bool = True) -> None:
        self.lat = max(-85.0, min(85.0, lat))
        self.lon = ((lon + 180) % 360) - 180
        if fly:
            self._cx = self.lon
            self._cy = self.lat
            if self._zoom < 4:
                self._zoom = 8.0
        self.update()

    def _spans(self) -> tuple[float, float]:
        w, h = max(self.width(), 1), max(self.height(), 1)
        span_lon = 360.0 / self._zoom
        span_lat = span_lon * (h / w) * 0.5
        span_lat = min(170.0, span_lat)
        return span_lon, span_lat

    def _to_px(self, lon: float, lat: float) -> QPointF:
        span_lon, span_lat = self._spans()
        w, h = self.width(), self.height()
        x = (lon - (self._cx - span_lon / 2.0)) / span_lon * w
        y = ((self._cy + span_lat / 2.0) - lat) / span_lat * h
        return QPointF(x, y)

    def _from_px(self, x: float, y: float) -> tuple[float, float]:
        span_lon, span_lat = self._spans()
        w, h = max(self.width(), 1), max(self.height(), 1)
        lon = (self._cx - span_lon / 2.0) + (x / w) * span_lon
        lat = (self._cy + span_lat / 2.0) - (y / h) * span_lat
        lon = ((lon + 180) % 360) - 180
        lat = max(-85.0, min(85.0, lat))
        return lat, lon

    def paintEvent(self, event) -> None:
        dark = theme.is_dark()
        c = theme.map_colors(dark)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), c["ocean"])

        span_lon, span_lat = self._spans()
        west = self._cx - span_lon / 2.0
        east = self._cx + span_lon / 2.0
        south = self._cy - span_lat / 2.0
        north = self._cy + span_lat / 2.0

        land = QBrush(c["land"])
        coast = QPen(c["coast"], 1.0)
        p.setBrush(land)
        p.setPen(coast)
        for ring in self._rings:
            poly = QPolygonF()
            visible = False
            for lon, lat in ring:
                if west - 20 <= lon <= east + 20 and south - 10 <= lat <= north + 10:
                    visible = True
                poly.append(self._to_px(lon, lat))
            if visible and poly.size() > 2:
                p.drawPolygon(poly)

        grid_pen = QPen(c["grid"], 1)
        p.setPen(grid_pen)
        step = 30 if self._zoom < 3 else 15 if self._zoom < 8 else 5 if self._zoom < 16 else 1
        start_lon = math.floor(west / step) * step
        lon = start_lon
        while lon <= east:
            a = self._to_px(lon, south)
            b = self._to_px(lon, north)
            p.drawLine(a, b)
            lon += step
        start_lat = math.floor(south / step) * step
        lat = start_lat
        while lat <= north:
            a = self._to_px(west, lat)
            b = self._to_px(east, lat)
            p.drawLine(a, b)
            lat += step

        pin = self._to_px(self.lon, self.lat)
        p.setPen(QPen(c["pin"], 2))
        p.setBrush(QBrush(c["pin_fill"]))
        p.drawEllipse(pin, 7, 7)
        path = QPainterPath()
        path.moveTo(pin + QPointF(0, 16))
        path.lineTo(pin + QPointF(-6, 4))
        path.lineTo(pin + QPointF(6, 4))
        path.closeSubpath()
        p.drawPath(path)

        p.setPen(c["text"])
        p.setFont(QFont("Segoe UI", 9))
        if self._hover:
            hlat, hlon = self._hover
            p.drawText(8, self.height() - 10, f"{hlat:.4f}, {hlon:.4f}    wheel zoom · drag pan · click pin")
        else:
            p.drawText(8, self.height() - 10, "Wheel zoom · drag to pan · click to drop pin")

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        factor = 1.18 if delta > 0 else 1 / 1.18
        old = self._zoom
        self._zoom = max(1.0, min(64.0, self._zoom * factor))
        if self._zoom != old:
            lat, lon = self._from_px(event.position().x(), event.position().y())
            self._cx += (lon - self._cx) * 0.25
            self._cy += (lat - self._cy) * 0.25
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag = event.position()
            self._moved = False

    def mouseMoveEvent(self, event) -> None:
        self._hover = self._from_px(event.position().x(), event.position().y())
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            dx = event.position().x() - self._drag.x()
            dy = event.position().y() - self._drag.y()
            if abs(dx) + abs(dy) > 4:
                self._moved = True
            span_lon, span_lat = self._spans()
            self._cx -= dx / max(self.width(), 1) * span_lon
            self._cy += dy / max(self.height(), 1) * span_lat
            self._cx = ((self._cx + 180) % 360) - 180
            self._cy = max(-80.0, min(80.0, self._cy))
            self._drag = event.position()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            if not self._moved:
                lat, lon = self._from_px(event.position().x(), event.position().y())
                self.lat, self.lon = lat, lon
                self.picked.emit(lat, lon)
                self.update()
            self._drag = None
            self._moved = False


class GeoPickerDialog(QDialog):
    def __init__(self, parent=None, lat: float = 37.334606, lon: float = -122.009102):
        super().__init__(parent)
        self.setWindowTitle("Pick GPS location")
        self.resize(780, 560)
        self.lat = float(lat)
        self.lon = float(lon)

        root = QVBoxLayout(self)
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search city, address, place…")
        self.search_edit.returnPressed.connect(self._search)
        go = QPushButton("Search")
        go.clicked.connect(self._search)
        search_row.addWidget(self.search_edit, stretch=1)
        search_row.addWidget(go)
        root.addLayout(search_row)

        self.map = GeoMap(self.lat, self.lon)
        self.map.picked.connect(self._on_picked)
        root.addWidget(self.map, stretch=1)

        self.coord_label = QLabel(self._fmt())
        self.coord_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.coord_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _fmt(self) -> str:
        hemi_n = "N" if self.lat >= 0 else "S"
        hemi_e = "E" if self.lon >= 0 else "W"
        return f"Lat {abs(self.lat):.6f}° {hemi_n}    Lon {abs(self.lon):.6f}° {hemi_e}"

    def _on_picked(self, lat: float, lon: float) -> None:
        self.lat = lat
        self.lon = lon
        self.coord_label.setText(self._fmt())

    def _search(self) -> None:
        query = self.search_edit.text().strip()
        if not query:
            return
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"format": "json", "limit": "1", "q": query}
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MetaRemover/1.0 (local desktop GPS picker; not a tile client)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            self.coord_label.setText("Search failed (network). Click the map instead.")
            return
        if not data:
            self.coord_label.setText("No results. Try another query or click the map.")
            return
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        self._on_picked(lat, lon)
        self.map.set_point(lat, lon, fly=True)
