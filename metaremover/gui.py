from __future__ import annotations

import os
import traceback

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)

from . import metadata as md
from . import presets as pr
from . import theme

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".avif"}

_TIP_CAMERA = "Writes this phone's Make, Model, lens, and date on a JPEG. Social apps still strip EXIF after they read C2PA."
_TIP_GPS = "Optional fake location in EXIF. Search or click the map. Most apps strip GPS on upload."
_TIP_PIXEL = "Light crop and grain, then one JPEG save. Nuclear is stronger grain, not a second compress. Does not remove SynthID."
_TIP_ANTIAI = "Camera-pipeline pass for pixel classifiers. Uses the Pixel strength. JPEG is saved once. Not guaranteed."
_TIP_ASPECT = "Optional center crop to a phone or social ratio. Original keeps the frame."
_TIP_OUTPUT = "Where cleaned files go. Default is the same folder as name_clean.jpg."
_TIP_LIST = "Click one. Ctrl+click to add more. Only the selection is processed."


def _thumb(path: str, size: int) -> QPixmap:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    img = reader.read()
    if img.isNull():
        return QPixmap()
    pix = QPixmap.fromImage(img)
    return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _label(text: str, tip: str) -> QLabel:
    lab = QLabel(text)
    lab.setToolTip(tip)
    lab.setToolTipDuration(6000)
    return lab


class FileListWidget(QListWidget):
    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setIconSize(QSize(48, 48))
        self.setSpacing(2)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                local = url.toLocalFile()
                if os.path.isdir(local):
                    for entry in os.listdir(local):
                        full = os.path.join(local, entry)
                        if os.path.splitext(entry)[1].lower() in IMAGE_EXTS:
                            paths.append(full)
                elif os.path.splitext(local)[1].lower() in IMAGE_EXTS:
                    paths.append(local)
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class ProcessWorker(QThread):
    progress = Signal(int, int, str)
    fileDone = Signal(str, str, object)
    finished_all = Signal()

    def __init__(self, files, out_dir, options, parent=None):
        super().__init__(parent)
        self.files = files
        self.out_dir = out_dir
        self.options = options

    def run(self):
        total = len(self.files)
        for i, src in enumerate(self.files, start=1):
            self.progress.emit(i, total, os.path.basename(src))
            try:
                dst = self._dest_for(src)
                dst = md.strip_and_save(
                    src, dst,
                    preset_key=self.options.get("preset"),
                    gps_lat=self.options.get("gps_lat"),
                    gps_lon=self.options.get("gps_lon"),
                    jpeg_quality=self.options["quality"],
                    force_jpeg=self.options.get("force_jpeg", False),
                    aspect=self.options.get("aspect", "none"),
                    pixel_strength=self.options.get("pixel_strength"),
                    anti_ai=self.options.get("anti_ai", False),
                ) or dst
                self.fileDone.emit(src, dst, None)
            except Exception as exc:
                traceback.print_exc()
                self.fileDone.emit(src, "", str(exc))
        self.finished_all.emit()

    def _dest_for(self, src: str) -> str:
        base = os.path.basename(src)
        name, ext = os.path.splitext(base)
        dst_dir = self.out_dir or os.path.dirname(src)
        if os.path.abspath(dst_dir) == os.path.abspath(os.path.dirname(src)):
            return os.path.join(dst_dir, f"{name}_clean{ext}")
        os.makedirs(dst_dir, exist_ok=True)
        return os.path.join(dst_dir, base)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MetaRemover")
        self.resize(1080, 680)
        self.out_dir = ""
        self._build_ui()
        self._update_process_btn()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        left = QVBoxLayout()
        left.addWidget(_label("Images", _TIP_LIST))
        self.file_list = FileListWidget()
        self.file_list.filesDropped.connect(self._add_files)
        self.file_list.currentRowChanged.connect(self._on_selection_changed)
        self.file_list.itemSelectionChanged.connect(self._update_process_btn)
        left.addWidget(self.file_list, stretch=1)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._browse_files)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_files)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addWidget(clear_btn)
        left.addLayout(btn_row)
        left_widget = QWidget()
        left_widget.setLayout(left)

        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)
        mid = QVBoxLayout()
        mid.addWidget(QLabel("Before"))
        self.before_text = QTextEdit(readOnly=True)
        self.before_text.setFont(mono)
        mid.addWidget(self.before_text, stretch=1)
        mid.addWidget(QLabel("After"))
        self.after_text = QTextEdit(readOnly=True)
        self.after_text.setFont(mono)
        mid.addWidget(self.after_text, stretch=1)
        mid_widget = QWidget()
        mid_widget.setLayout(mid)

        right = QVBoxLayout()
        right.setSpacing(8)

        theme_row = QHBoxLayout()
        theme_row.addStretch(1)
        self.theme_btn = QPushButton()
        self.theme_btn.setFixedHeight(26)
        self.theme_btn.clicked.connect(self._toggle_theme)
        self._refresh_theme_btn()
        theme_row.addWidget(self.theme_btn)
        right.addLayout(theme_row)

        right.addWidget(_label("Camera", _TIP_CAMERA))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("None", None)
        for key, preset in pr.PRESETS.items():
            self.preset_combo.addItem(preset.label, key)
        idx = self.preset_combo.findData("iphone17")
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        right.addWidget(self.preset_combo)

        right.addWidget(_label("GPS", _TIP_GPS))
        self.gps_check = QCheckBox("Include location")
        right.addWidget(self.gps_check)
        gps_row = QHBoxLayout()
        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90, 90)
        self.lat_spin.setDecimals(6)
        self.lat_spin.setValue(37.334606)
        self.lat_spin.setPrefix("lat ")
        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180, 180)
        self.lon_spin.setDecimals(6)
        self.lon_spin.setValue(-122.009102)
        self.lon_spin.setPrefix("lon ")
        gps_row.addWidget(self.lat_spin)
        gps_row.addWidget(self.lon_spin)
        right.addLayout(gps_row)
        self.map_btn = QPushButton("Pick on map…")
        self.map_btn.clicked.connect(self._pick_geo)
        right.addWidget(self.map_btn)

        right.addWidget(_label("Pixel pass", _TIP_PIXEL))
        self.pixel_combo = QComboBox()
        self.pixel_combo.addItem("Off", None)
        self.pixel_combo.addItem("Subtle", "subtle")
        self.pixel_combo.addItem("Strong", "strong")
        self.pixel_combo.addItem("Nuclear", "nuclear")
        self.pixel_combo.setCurrentIndex(1)
        right.addWidget(self.pixel_combo)

        right.addWidget(_label("Anti-AI", _TIP_ANTIAI))
        self.anti_ai_check = QCheckBox("Enable")
        right.addWidget(self.anti_ai_check)

        right.addWidget(_label("Aspect", _TIP_ASPECT))
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItem("Original", "none")
        self.aspect_combo.addItem("4:3 phone", "4:3")
        self.aspect_combo.addItem("4:5 Instagram", "4:5")
        self.aspect_combo.addItem("9:16 story", "9:16")
        self.aspect_combo.addItem("16:9", "16:9")
        right.addWidget(self.aspect_combo)

        right.addWidget(_label("Output", _TIP_OUTPUT))
        self.out_label = QLabel("Same folder (name_clean.jpg)")
        self.out_label.setWordWrap(True)
        out_btn = QPushButton("Folder…")
        out_btn.clicked.connect(self._choose_out_dir)
        right.addWidget(self.out_label)
        right.addWidget(out_btn)

        self.process_btn = QPushButton("Process")
        self.process_btn.setMinimumHeight(36)
        self.process_btn.clicked.connect(self._process_selected)
        right.addWidget(self.process_btn)
        self.progress = QProgressBar()
        right.addWidget(self.progress)
        right.addStretch(1)

        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setFixedWidth(270)

        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(mid_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 0)
        root.addWidget(splitter)

    def _refresh_theme_btn(self) -> None:
        if theme.is_dark():
            self.theme_btn.setText("Light mode")
        else:
            self.theme_btn.setText("Dark mode")

    def _toggle_theme(self) -> None:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        theme.apply(app, not theme.is_dark())
        self._refresh_theme_btn()
        self.update()

    def _selected_paths(self) -> list[str]:
        return [item.data(Qt.UserRole) for item in self.file_list.selectedItems()]

    def _update_process_btn(self) -> None:
        n = len(self.file_list.selectedItems())
        if n == 0:
            self.process_btn.setText("Process")
            self.process_btn.setEnabled(False)
        elif n == 1:
            self.process_btn.setText("Process (1)")
            self.process_btn.setEnabled(True)
        else:
            self.process_btn.setText(f"Process ({n})")
            self.process_btn.setEnabled(True)

    def _pick_geo(self) -> None:
        from .geo_picker import GeoPickerDialog
        dlg = GeoPickerDialog(self, self.lat_spin.value(), self.lon_spin.value())
        if dlg.exec() == QDialog.Accepted:
            self.lat_spin.setValue(dlg.lat)
            self.lon_spin.setValue(dlg.lon)
            self.gps_check.setChecked(True)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select images", "",
            "Images (*.jpg *.jpeg *.png *.webp *.tif *.tiff *.bmp *.avif)",
        )
        if files:
            self._add_files(files)

    def _add_files(self, paths):
        existing = {self.file_list.item(i).data(Qt.UserRole) for i in range(self.file_list.count())}
        added = []
        for p in paths:
            if p in existing:
                continue
            item = QListWidgetItem(os.path.basename(p))
            item.setData(Qt.UserRole, p)
            pix = _thumb(p, 48)
            if not pix.isNull():
                item.setIcon(QIcon(pix))
            self.file_list.addItem(item)
            added.append(item)
        if added:
            self.file_list.clearSelection()
            for item in added:
                item.setSelected(True)
            self.file_list.setCurrentItem(added[-1])
        self._update_process_btn()

    def _clear_files(self):
        self.file_list.clear()
        self.before_text.clear()
        self.after_text.clear()
        self._update_process_btn()

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self._update_process_btn()

    def _choose_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if d:
            self.out_dir = d
            self.out_label.setText(d)

    def _on_selection_changed(self, row: int):
        if row < 0:
            return
        path = self.file_list.item(row).data(Qt.UserRole)
        self._show_before(path)
        self.after_text.clear()

    def _show_before(self, path: str):
        try:
            report = md.read_metadata(path)
            self.before_text.setPlainText("\n".join(report.summary_lines()))
        except Exception as exc:
            self.before_text.setPlainText(f"Could not read metadata: {exc}")

    def _process_selected(self):
        files = self._selected_paths()
        if not files:
            QMessageBox.information(self, "MetaRemover", "Select one or more images. Ctrl+click to add to the selection.")
            return

        preset_key = self.preset_combo.currentData()
        pixel = self.pixel_combo.currentData()
        anti = self.anti_ai_check.isChecked()
        quality = {None: 95, "subtle": 94, "strong": 93, "nuclear": 92}.get(pixel, 94)
        if anti:
            quality = min(quality, 93)
        options = {
            "preset": preset_key,
            "gps_lat": self.lat_spin.value() if (preset_key and self.gps_check.isChecked()) else None,
            "gps_lon": self.lon_spin.value() if (preset_key and self.gps_check.isChecked()) else None,
            "quality": quality,
            "force_jpeg": bool(preset_key or pixel or anti),
            "aspect": self.aspect_combo.currentData() or "none",
            "pixel_strength": pixel,
            "anti_ai": anti,
        }

        n = len(files)
        self.process_btn.setEnabled(False)
        self.progress.setMaximum(n)
        self.progress.setValue(0)
        self.worker = ProcessWorker(files, self.out_dir, options)
        self.worker.progress.connect(self._on_progress)
        self.worker.fileDone.connect(self._on_file_done)
        self.worker.finished_all.connect(self._on_all_done)
        self.worker.start()

    def _on_progress(self, i: int, total: int, name: str):
        self.progress.setValue(i)
        self.statusBar().showMessage(f"Processing {i}/{total}: {name}")

    def _on_file_done(self, src: str, dst: str, error):
        if error:
            self.after_text.setPlainText(f"FAILED: {src}\n{error}")
            return
        try:
            report = md.read_metadata(dst)
            text = f"Saved to: {dst}\n\n" + "\n".join(report.summary_lines())
            if not report.exif.get("Make") and self.preset_combo.currentData():
                text += "\n\nWARNING: camera EXIF was requested but Make is missing."
        except Exception as exc:
            text = f"Saved to: {dst}\n(could not re-read metadata: {exc})"
        current = self.file_list.currentItem()
        if current is None or current.data(Qt.UserRole) == src:
            self.after_text.setPlainText(text)

    def _on_all_done(self):
        self._update_process_btn()
        self.statusBar().showMessage("Done.", 5000)
