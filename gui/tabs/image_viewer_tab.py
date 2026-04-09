#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - IMAGE VIEWER TAB
================================================================================
Advanced FITS/XISF image viewer with:
- GPU-accelerated display (pyqtgraph, fallback matplotlib)
- STF autostretch (PixInsight-style)
- FWHM heatmap overlay with contour lines
- 3x3 corner inspector with per-cell FWHM stats
- Star overlay with FWHM labels
- LRU cache with neighbor prefetching
- Header viewer dialog
- Pixel info under cursor
================================================================================
"""

import logging
import os
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QTableWidget, QTableWidgetItem,
    QFileDialog, QHeaderView, QSplitter, QGroupBox,
    QGridLayout, QSizePolicy, QCheckBox, QSlider,
    QListWidget, QListWidgetItem, QDialog, QStatusBar,
    QScrollArea, QToolBar, QSpinBox, QAbstractItemView
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QSize, QRectF, QPointF
)
from PyQt6.QtGui import (
    QFont, QImage, QPixmap, QPainter, QColor, QPen, QBrush,
    QKeySequence, QShortcut, QAction, QWheelEvent
)

from core.config import get_config
from core.i18n import get_lang
from core.signals import signals
from gui.theme import COLORS, get_mono_font
from gui.tooltips import get_tip

logger = logging.getLogger(__name__)

# Feature gates
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from astropy.io import fits as astropy_fits
    HAS_ASTROPY = True
except ImportError:
    HAS_ASTROPY = False


# ─────────────────────────────────────────────────────────────────────────────
# LRU Image Cache
# ─────────────────────────────────────────────────────────────────────────────
class ImageCache:
    """Simple LRU cache for loaded image data."""

    def __init__(self, max_size=5):
        self._cache = OrderedDict()
        self._max_size = max_size

    def get(self, path):
        if path in self._cache:
            self._cache.move_to_end(path)
            return self._cache[path]
        return None

    def put(self, path, data):
        if path in self._cache:
            self._cache.move_to_end(path)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
        self._cache[path] = data

    def clear(self):
        self._cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Background Workers
# ─────────────────────────────────────────────────────────────────────────────
class ImageLoadWorker(QThread):
    """Load and preprocess an image in background."""
    loaded = pyqtSignal(str, object, dict)  # path, data_array, header_dict
    error = pyqtSignal(str, str)  # path, error_message

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            data, header = self._load_image(self.file_path)
            self.loaded.emit(self.file_path, data, header)
        except Exception as e:
            self.error.emit(self.file_path, str(e))

    def _load_image(self, path):
        """Load FITS or XISF image data and header."""
        ext = path.lower()
        header = {}
        data = None

        if ext.endswith('.fits') or ext.endswith('.fit') or ext.endswith('.fts'):
            if not HAS_ASTROPY:
                raise ImportError("astropy required for FITS files")
            with astropy_fits.open(path, memmap=False) as hdul:
                for hdu in hdul:
                    if hdu.data is not None:
                        data = hdu.data.astype(np.float32)
                        header = dict(hdu.header)
                        break
        elif ext.endswith('.fits.fz'):
            if not HAS_ASTROPY:
                raise ImportError("astropy required for FITS.FZ files")
            with astropy_fits.open(path, memmap=False) as hdul:
                for hdu in hdul:
                    if hdu.data is not None:
                        data = hdu.data.astype(np.float32)
                        header = dict(hdu.header)
                        break
        elif ext.endswith('.xisf'):
            data, header = self._load_xisf(path)
        else:
            raise ValueError(f"Unsupported format: {os.path.splitext(path)[1]}")

        if data is None:
            raise ValueError("No image data found in file")

        return data, header

    def _load_xisf(self, path):
        """Load XISF file (simplified parser for image data)."""
        import struct
        header = {}

        with open(path, 'rb') as f:
            magic = f.read(8)
            if magic != b'XISF0100':
                raise ValueError("Invalid XISF file")

            header_len = struct.unpack('<I', f.read(4))[0]
            f.read(4)  # reserved
            xml_data = f.read(header_len).rstrip(b'\x00')

            try:
                try:
                    from defusedxml.ElementTree import fromstring
                except ImportError:
                    from xml.etree.ElementTree import fromstring

                root = fromstring(xml_data.decode('utf-8'))
                ns = {'xisf': 'http://www.pixinsight.com/xisf'}

                img_elem = root.find('.//xisf:Image', ns)
                if img_elem is None:
                    img_elem = root.find('.//Image')

                if img_elem is not None:
                    geom = img_elem.get('geometry', '').split(':')
                    sample_format = img_elem.get('sampleFormat', 'Float32')
                    loc = img_elem.get('location', '')

                    # Parse FITS keywords
                    for prop in img_elem.findall('.//xisf:FITSKeyword', ns):
                        name = prop.get('name', '')
                        value = prop.get('value', '').strip().strip("'").strip()
                        header[name] = value
                    for prop in img_elem.findall('.//FITSKeyword'):
                        name = prop.get('name', '')
                        value = prop.get('value', '').strip().strip("'").strip()
                        header[name] = value

                    if loc.startswith('attachment:'):
                        parts = loc.split(':')
                        offset = int(parts[1])
                        size = int(parts[2])

                        dims = [int(x) for x in geom if x]
                        dtype_map = {
                            'Float32': np.float32,
                            'Float64': np.float64,
                            'UInt16': np.uint16,
                            'UInt32': np.uint32,
                            'UInt8': np.uint8,
                        }
                        dtype = dtype_map.get(sample_format, np.float32)

                        f.seek(offset)
                        raw = f.read(size)
                        data = np.frombuffer(raw, dtype=dtype)

                        if len(dims) == 3:
                            data = data.reshape(dims[2], dims[1], dims[0])
                        elif len(dims) == 2:
                            data = data.reshape(dims[1], dims[0])

                        return data.astype(np.float32), header

            except Exception as e:
                logger.warning("XISF XML parse error: %s", e)

        raise ValueError("Could not extract image data from XISF")


class FWHMAnalysisWorker(QThread):
    """Run FWHM map analysis in background."""
    completed = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, data, pixel_scale=None, parent=None):
        super().__init__(parent)
        self.data = data
        self.pixel_scale = pixel_scale

    def run(self):
        try:
            from modules.fwhm_map import FWHMMapAnalyzer
            analyzer = FWHMMapAnalyzer()
            result = analyzer.analyze(self.data, pixel_scale=self.pixel_scale)

            # Also run corner inspector in the same background thread
            try:
                from modules.corner_inspector import CornerInspector
                inspector = CornerInspector()
                stars = result.get('stars', [])
                corner_data = inspector.analyze(self.data, stars=stars)
                result['corner_data'] = corner_data
            except Exception as ce:
                logger.warning("Corner inspector error in worker: %s", ce)

            self.completed.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Header Viewer Dialog
# ─────────────────────────────────────────────────────────────────────────────
class HeaderViewerDialog(QDialog):
    """Modal dialog showing FITS/XISF header keywords."""

    def __init__(self, header_dict, file_path="", lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(
            f"{self._tr('Header', 'En-tête')} — {os.path.basename(file_path)}"
        )
        self.setMinimumSize(700, 500)
        self._init_ui(header_dict)

    def _tr(self, en, fr):
        return fr if self.lang == "fr" else en

    def _init_ui(self, header_dict):
        layout = QVBoxLayout(self)

        table = QTableWidget(len(header_dict), 2)
        table.setHorizontalHeaderLabels(
            [self._tr("Keyword", "Mot-clé"), self._tr("Value", "Valeur")])
        table.setToolTip(self._tr(
            "FITS/XISF header keywords and their values",
            "Mots-clés d'en-tête FITS/XISF et leurs valeurs"))
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        for row, (key, val) in enumerate(sorted(header_dict.items())):
            table.setItem(row, 0, QTableWidgetItem(str(key)))
            table.setItem(row, 1, QTableWidgetItem(str(val)))

        layout.addWidget(table)

        close_btn = QPushButton(self._tr("Close", "Fermer"))
        close_btn.setToolTip(self._tr("Close this dialog", "Fermer cette fenêtre"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


# ─────────────────────────────────────────────────────────────────────────────
# Image Viewer Widget (pyqtgraph or matplotlib)
# ─────────────────────────────────────────────────────────────────────────────
class ImageViewWidget(QWidget):
    """Image display with zoom/pan, using pyqtgraph or matplotlib fallback."""
    pixel_info = pyqtSignal(int, int, str)  # x, y, value_str

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self._display_data = None
        self._overlay_heatmap = None
        self._overlay_stars = None
        self._show_heatmap = False
        self._show_stars = False
        self._zoom_level = 1.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if HAS_PYQTGRAPH:
            self._backend = 'pyqtgraph'
            self._view = pg.GraphicsLayoutWidget()
            self._plot = self._view.addPlot()
            self._plot.setAspectLocked(True)
            self._plot.invertY(True)
            self._img_item = pg.ImageItem()
            self._plot.addItem(self._img_item)
            self._heatmap_item = pg.ImageItem()
            self._heatmap_item.setZValue(10)
            self._heatmap_item.setOpacity(0.4)
            self._plot.addItem(self._heatmap_item)
            self._heatmap_item.hide()
            # Star scatter
            self._star_scatter = pg.ScatterPlotItem(
                pen=pg.mkPen('g', width=1), brush=None, size=12, symbol='o')
            self._star_scatter.setZValue(20)
            self._plot.addItem(self._star_scatter)
            self._star_scatter.hide()
            # Mouse tracking
            self._img_item.hoverEvent = self._on_hover_pg
            layout.addWidget(self._view)
        elif HAS_MATPLOTLIB:
            self._backend = 'matplotlib'
            self._fig = Figure(figsize=(8, 6), facecolor='#1a1a2e')
            self._canvas = FigureCanvasQTAgg(self._fig)
            self._ax = self._fig.add_subplot(111)
            self._ax.set_facecolor('#1a1a2e')
            self._ax.tick_params(colors='white')
            self._fig.tight_layout(pad=0.5)
            self._canvas.mpl_connect('motion_notify_event', self._on_hover_mpl)
            layout.addWidget(self._canvas)
        else:
            self._backend = 'none'
            lbl = QLabel("numpy + (pyqtgraph ou matplotlib) requis" if get_lang() == "fr"
                         else "numpy + (pyqtgraph or matplotlib) required")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)

    def set_image(self, data):
        """Display image data (2D mono or 3D color)."""
        if not HAS_NUMPY or data is None:
            return
        self._data = data
        self._apply_stretch()

    def _apply_stretch(self):
        """Apply current stretch settings and update display."""
        if self._data is None:
            return

        try:
            from modules.stf_stretch import STFAutostretch
            stretcher = STFAutostretch()
            display = stretcher.stf_autostretch(self._data)
        except (ImportError, Exception):
            # Manual fallback stretch
            d = self._data.astype(np.float32)
            vmin, vmax = np.nanpercentile(d, [0.5, 99.5])
            if vmax <= vmin:
                vmax = vmin + 1
            display = np.clip((d - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)

        self._display_data = display
        self._update_view()

    def _update_view(self):
        """Push display data to backend widget."""
        if self._display_data is None:
            return

        if self._backend == 'pyqtgraph':
            img = self._display_data
            if img.ndim == 3:
                # Color: (C, H, W) → (H, W, C) for pyqtgraph
                if img.shape[0] in (3, 4):
                    img = np.transpose(img, (1, 2, 0))
            self._img_item.setImage(img, autoLevels=False, levels=[0, 255])
            self._plot.autoRange()
        elif self._backend == 'matplotlib':
            self._ax.clear()
            img = self._display_data
            if img.ndim == 3:
                if img.shape[0] in (3, 4):
                    img = np.transpose(img, (1, 2, 0))
                self._ax.imshow(img, origin='upper')
            else:
                self._ax.imshow(img, cmap='gray', origin='upper', vmin=0, vmax=255)
            self._ax.set_axis_off()
            self._canvas.draw_idle()

    def set_heatmap(self, heatmap_data, shape):
        """Set FWHM heatmap overlay."""
        if not HAS_NUMPY:
            return
        self._overlay_heatmap = heatmap_data

        if self._backend == 'pyqtgraph':
            if heatmap_data is not None:
                # Create RGBA heatmap: green (good) → red (bad)
                h = heatmap_data
                vmin, vmax = np.nanmin(h), np.nanmax(h)
                if vmax <= vmin:
                    vmax = vmin + 1
                norm = (h - vmin) / (vmax - vmin)
                rgba = np.zeros((*h.shape, 4), dtype=np.uint8)
                # Green to red gradient
                rgba[..., 0] = (norm * 255).astype(np.uint8)   # R
                rgba[..., 1] = ((1 - norm) * 255).astype(np.uint8)  # G
                rgba[..., 3] = 100  # Alpha

                # Scale heatmap to image size
                from scipy.ndimage import zoom as ndimage_zoom
                sy = shape[0] / h.shape[0]
                sx = shape[1] / h.shape[1]
                rgba_scaled = ndimage_zoom(rgba, (sy, sx, 1), order=1)

                self._heatmap_item.setImage(rgba_scaled, autoLevels=False)
                if self._show_heatmap:
                    self._heatmap_item.show()

    def set_stars(self, stars_list):
        """Set star overlay positions."""
        self._overlay_stars = stars_list
        if self._backend == 'pyqtgraph' and stars_list:
            spots = [{'pos': (s['x'], s['y']),
                      'size': max(8, min(20, s.get('fwhm', 3) * 3)),
                      'pen': pg.mkPen(self._fwhm_color(s.get('fwhm', 3)), width=1.5),
                      'brush': None}
                     for s in stars_list]
            self._star_scatter.setData(spots)
            if self._show_stars:
                self._star_scatter.show()

    def toggle_heatmap(self, visible):
        self._show_heatmap = visible
        if self._backend == 'pyqtgraph':
            if visible and self._overlay_heatmap is not None:
                self._heatmap_item.show()
            else:
                self._heatmap_item.hide()
            self._update_view_overlays_mpl() if self._backend == 'matplotlib' else None

    def toggle_stars(self, visible):
        self._show_stars = visible
        if self._backend == 'pyqtgraph':
            if visible:
                self._star_scatter.show()
            else:
                self._star_scatter.hide()

    @staticmethod
    def _fwhm_color(fwhm):
        """Color by FWHM: green (good) → yellow → red (bad)."""
        if fwhm < 2.5:
            return QColor(0, 200, 0)
        elif fwhm < 4.0:
            t = (fwhm - 2.5) / 1.5
            return QColor(int(200 * t), int(200 * (1 - t)), 0)
        else:
            return QColor(200, 0, 0)

    def _on_hover_pg(self, event):
        if event.isExit():
            return
        pos = event.pos()
        x, y = int(pos.x()), int(pos.y())
        if self._data is not None and 0 <= y < self._data.shape[-2] and 0 <= x < self._data.shape[-1]:
            if self._data.ndim == 2:
                val = f"{self._data[y, x]:.1f}"
            elif self._data.ndim == 3:
                if self._data.shape[0] == 3:
                    r, g, b = self._data[0, y, x], self._data[1, y, x], self._data[2, y, x]
                    val = f"R={r:.1f} G={g:.1f} B={b:.1f}"
                else:
                    val = f"{self._data[0, y, x]:.1f}"
            else:
                val = "?"
            self.pixel_info.emit(x, y, val)

    def _on_hover_mpl(self, event):
        if event.inaxes and self._data is not None:
            x, y = int(event.xdata), int(event.ydata)
            if 0 <= y < self._data.shape[-2] and 0 <= x < self._data.shape[-1]:
                if self._data.ndim == 2:
                    val = f"{self._data[y, x]:.1f}"
                else:
                    val = "multi"
                self.pixel_info.emit(x, y, val)

    def _update_view_overlays_mpl(self):
        """Redraw matplotlib with overlays."""
        if self._backend != 'matplotlib' or self._display_data is None:
            return
        self._ax.clear()
        img = self._display_data
        if img.ndim == 3 and img.shape[0] in (3, 4):
            img = np.transpose(img, (1, 2, 0))
        if img.ndim == 2:
            self._ax.imshow(img, cmap='gray', origin='upper', vmin=0, vmax=255)
        else:
            self._ax.imshow(img, origin='upper')

        if self._show_heatmap and self._overlay_heatmap is not None:
            self._ax.imshow(self._overlay_heatmap, cmap='RdYlGn_r',
                            alpha=0.3, origin='upper',
                            extent=[0, img.shape[-1] if img.ndim == 2 else img.shape[1],
                                    img.shape[-2] if img.ndim == 2 else img.shape[0], 0])

        if self._show_stars and self._overlay_stars:
            xs = [s['x'] for s in self._overlay_stars]
            ys = [s['y'] for s in self._overlay_stars]
            self._ax.scatter(xs, ys, s=50, facecolors='none',
                             edgecolors='lime', linewidths=1)

        self._ax.set_axis_off()
        self._canvas.draw_idle()


# ─────────────────────────────────────────────────────────────────────────────
# Corner Inspector Widget
# ─────────────────────────────────────────────────────────────────────────────
class CornerInspectorWidget(QWidget):
    """3x3 grid showing corner crops with FWHM statistics."""

    def __init__(self, lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self._init_ui()

    def _tr(self, en, fr):
        return fr if self.lang == "fr" else en

    def _init_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(4)
        self._cells = {}
        positions = [
            ('TL', 0, 0), ('T', 0, 1), ('TR', 0, 2),
            ('L', 1, 0), ('C', 1, 1), ('R', 1, 2),
            ('BL', 2, 0), ('B', 2, 1), ('BR', 2, 2),
        ]
        for name, row, col in positions:
            cell = QFrame()
            cell.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
            cell.setStyleSheet(f"background: {COLORS.get('bg_dark', '#0d0d1a')};")
            cell.setMinimumSize(140, 120)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(4, 4, 4, 4)

            title = QLabel(name)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("color: #9ca3af; font-weight: bold;")
            cell_layout.addWidget(title)

            img_label = QLabel()
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setMinimumSize(120, 80)
            img_label.setStyleSheet("border: 1px solid #333;")
            cell_layout.addWidget(img_label)

            stats_label = QLabel("—")
            stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stats_label.setStyleSheet("color: #e5e7eb; font-size: 10px;")
            cell_layout.addWidget(stats_label)

            self._cells[name] = {
                'frame': cell,
                'image': img_label,
                'stats': stats_label,
            }
            layout.addWidget(cell, row, col)

    def update_data(self, corner_data):
        """Update corner inspector with analysis results."""
        if not corner_data:
            return

        for name, cell in self._cells.items():
            if name in corner_data:
                cdata = corner_data[name]
                stats = cdata.get('stats', {})

                # Update thumbnail
                crop = cdata.get('crop_data')
                if crop is not None and HAS_NUMPY:
                    qimg = self._array_to_qimage(crop)
                    pix = QPixmap.fromImage(qimg).scaled(
                        120, 80, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                    cell['image'].setPixmap(pix)

                # Update stats
                med = stats.get('median_fwhm', 0)
                count = stats.get('star_count', 0)
                grade = self._quality_grade(med)
                color = self._grade_color(grade)
                cell['stats'].setText(f"FWHM: {med:.2f}px  ({count}★)")
                cell['stats'].setStyleSheet(
                    f"color: {color}; font-size: 10px; font-weight: bold;")

    @staticmethod
    def _array_to_qimage(data):
        """Convert numpy array to QImage for display.
        Returns a deep-copied QImage so the numpy buffer can be freed safely."""
        if data.ndim == 2:
            vmin, vmax = np.nanpercentile(data, [1, 99])
            if vmax <= vmin:
                vmax = vmin + 1
            d = np.clip((data - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
            h, w = d.shape
            d = np.ascontiguousarray(d)
            qimg = QImage(d.data, w, h, w, QImage.Format.Format_Grayscale8)
            return qimg.copy()  # Deep copy — detach from numpy buffer
        elif data.ndim == 3:
            if data.shape[0] == 3:
                data = np.transpose(data, (1, 2, 0))
            h, w = data.shape[:2]
            vmin, vmax = np.nanpercentile(data, [1, 99])
            if vmax <= vmin:
                vmax = vmin + 1
            d = np.clip((data - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
            if d.shape[2] == 3:
                d = np.ascontiguousarray(d)
                qimg = QImage(d.data, w, h, 3 * w, QImage.Format.Format_RGB888)
                return qimg.copy()  # Deep copy — detach from numpy buffer
        return QImage()

    @staticmethod
    def _quality_grade(fwhm):
        if fwhm <= 0:
            return 'N/A'
        if fwhm < 2.5:
            return 'Excellent'
        if fwhm < 3.5:
            return 'Good'
        if fwhm < 5.0:
            return 'Fair'
        return 'Poor'

    @staticmethod
    def _grade_color(grade):
        return {
            'Excellent': '#22c55e',
            'Good': '#84cc16',
            'Fair': '#eab308',
            'Poor': '#ef4444',
            'N/A': '#6b7280',
        }.get(grade, '#6b7280')


# ─────────────────────────────────────────────────────────────────────────────
# Main Image Viewer Tab
# ─────────────────────────────────────────────────────────────────────────────
class ImageViewerTab(QWidget):
    """Main image viewer tab with FWHM analysis and corner inspection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lang = get_lang()
        self.cfg = get_config()

        self._image_cache = ImageCache(
            max_size=self.cfg.get('image_viewer', {}).get('cache_size', 5))
        self._current_path = None
        self._current_data = None
        self._current_header = {}
        self._file_list = []
        self._file_index = -1
        self._fwhm_result = None
        self._corner_result = None

        self._load_worker = None
        self._fwhm_worker = None

        self._init_ui()
        self._connect_signals()

    def _tr(self, en, fr):
        return fr if self.lang == "fr" else en

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ── Left panel: file browser ──
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_panel.setMaximumWidth(280)

        browse_btn = QPushButton(self._tr("📂 Browse Folder", "📂 Parcourir Dossier"))
        browse_btn.setToolTip(get_tip('iv_browse'))
        browse_btn.clicked.connect(self._browse_folder)
        left_layout.addWidget(browse_btn)

        # Sort combo
        sort_layout = QHBoxLayout()
        sort_layout.addWidget(QLabel(self._tr("Sort:", "Tri :")))
        self._sort_combo = QComboBox()
        self._sort_combo.addItems([
            self._tr("Name", "Nom"),
            self._tr("Date", "Date"),
            self._tr("FWHM", "FWHM"),
        ])
        self._sort_combo.setToolTip(get_tip('iv_sort'))
        self._sort_combo.currentIndexChanged.connect(self._sort_files)
        sort_layout.addWidget(self._sort_combo)
        left_layout.addLayout(sort_layout)

        self._file_list_widget = QListWidget()
        self._file_list_widget.setToolTip(self._tr(
            "FITS/XISF files found in the selected folder",
            "Fichiers FITS/XISF trouvés dans le dossier sélectionné"))
        self._file_list_widget.setStyleSheet(
            f"background: {COLORS.get('bg_dark', '#0d0d1a')}; color: #e5e7eb;")
        self._file_list_widget.currentRowChanged.connect(self._on_file_selected)
        left_layout.addWidget(self._file_list_widget)

        file_count_layout = QHBoxLayout()
        self._file_count_label = QLabel(self._tr("0 files", "0 fichiers"))
        self._file_count_label.setStyleSheet("color: #9ca3af;")
        file_count_layout.addWidget(self._file_count_label)
        left_layout.addLayout(file_count_layout)

        main_layout.addWidget(left_panel)

        # ── Center: splitter with viewer and corner inspector ──
        center_splitter = QSplitter(Qt.Orientation.Vertical)

        # Viewer + controls
        viewer_container = QWidget()
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()

        self._stf_check = QCheckBox(self._tr("STF Autostretch", "STF Auto-etirement"))
        self._stf_check.setToolTip(get_tip('iv_stf'))
        self._stf_check.setChecked(True)
        self._stf_check.toggled.connect(self._on_stretch_changed)
        toolbar.addWidget(self._stf_check)

        toolbar.addWidget(self._make_separator())

        self._fwhm_check = QCheckBox(self._tr("FWHM Map", "Carte FWHM"))
        self._fwhm_check.setToolTip(get_tip('iv_fwhm_map'))
        self._fwhm_check.toggled.connect(self._on_fwhm_toggled)
        toolbar.addWidget(self._fwhm_check)

        self._stars_check = QCheckBox(self._tr("Stars", "Etoiles"))
        self._stars_check.setToolTip(get_tip('iv_stars'))
        self._stars_check.toggled.connect(self._on_stars_toggled)
        toolbar.addWidget(self._stars_check)

        self._corner_check = QCheckBox(self._tr("Corners", "Coins"))
        self._corner_check.setToolTip(get_tip('iv_corners'))
        self._corner_check.toggled.connect(self._on_corners_toggled)
        toolbar.addWidget(self._corner_check)

        toolbar.addWidget(self._make_separator())

        header_btn = QPushButton(self._tr("📋 Header", "📋 En-tete"))
        header_btn.setToolTip(self._tr(
            "View FITS/XISF header keywords (Ctrl+H)",
            "Voir les mots-cles de l'en-tete FITS/XISF (Ctrl+H)"))
        header_btn.clicked.connect(self._show_header_dialog)
        toolbar.addWidget(header_btn)

        toolbar.addStretch()

        # Pixel info
        self._pixel_label = QLabel(self._tr("Pixel: —", "Pixel : —"))
        self._pixel_label.setStyleSheet("color: #9ca3af; font-family: monospace;")
        toolbar.addWidget(self._pixel_label)

        viewer_layout.addLayout(toolbar)

        # Image viewer widget
        self._viewer = ImageViewWidget()
        self._viewer.pixel_info.connect(self._update_pixel_info)
        viewer_layout.addWidget(self._viewer)

        center_splitter.addWidget(viewer_container)

        # Corner inspector (hidden by default)
        self._corner_inspector = CornerInspectorWidget(lang=self.lang)
        self._corner_inspector.setVisible(False)
        center_splitter.addWidget(self._corner_inspector)

        center_splitter.setStretchFactor(0, 3)
        center_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(center_splitter, stretch=1)

        # ── Right panel: stats ──
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_panel.setMaximumWidth(260)

        # Image info group
        info_group = QGroupBox(self._tr("Image Info", "Info Image"))
        info_layout = QGridLayout(info_group)
        self._info_labels = {}
        info_fields = [
            ('object', self._tr("Object", "Objet")),
            ('dimensions', self._tr("Size", "Taille")),
            ('filter', self._tr("Filter", "Filtre")),
            ('exposure', self._tr("Exposure", "Exposition")),
            ('camera', self._tr("Camera", "Camera")),
            ('telescope', self._tr("Telescope", "Telescope")),
            ('date', self._tr("Date", "Date")),
        ]
        for i, (key, label) in enumerate(info_fields):
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #9ca3af; font-weight: bold;")
            val = QLabel("—")
            val.setStyleSheet("color: #e5e7eb;")
            val.setWordWrap(True)
            info_layout.addWidget(lbl, i, 0)
            info_layout.addWidget(val, i, 1)
            self._info_labels[key] = val
        right_layout.addWidget(info_group)

        # FWHM stats group
        fwhm_group = QGroupBox(self._tr("FWHM Statistics", "Statistiques FWHM"))
        fwhm_layout = QGridLayout(fwhm_group)
        self._fwhm_labels = {}
        fwhm_fields = [
            ('star_count', self._tr("Stars", "Etoiles")),
            ('median', self._tr("Median", "Mediane")),
            ('mean', self._tr("Mean", "Moyenne")),
            ('std', self._tr("StdDev", "Ecart-type")),
            ('min', self._tr("Min", "Min")),
            ('max', self._tr("Max", "Max")),
        ]
        for i, (key, label) in enumerate(fwhm_fields):
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #9ca3af;")
            val = QLabel("—")
            val.setStyleSheet("color: #e5e7eb;")
            fwhm_layout.addWidget(lbl, i, 0)
            fwhm_layout.addWidget(val, i, 1)
            self._fwhm_labels[key] = val
        right_layout.addWidget(fwhm_group)

        # Analysis button
        analyze_btn = QPushButton(self._tr("🔍 Run FWHM Analysis",
                                           "🔍 Lancer Analyse FWHM"))
        analyze_btn.setToolTip(self._tr(
            "Detect stars and compute FWHM heatmap",
            "Detecter les etoiles et calculer la carte FWHM"))
        analyze_btn.clicked.connect(self._run_fwhm_analysis)
        right_layout.addWidget(analyze_btn)

        self._analysis_status = QLabel("")
        self._analysis_status.setStyleSheet("color: #9ca3af; font-size: 11px;")
        right_layout.addWidget(self._analysis_status)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+H"), self, self._show_header_dialog)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._prev_image)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._next_image)

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #333;")
        return sep

    def _connect_signals(self):
        signals.image_loaded.connect(self._on_image_loaded_signal)
        signals.image_analysis_completed.connect(self._on_analysis_signal)

    # ── File browsing ──
    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("Select Image Folder", "Selectionner Dossier Images"))
        if not folder:
            return
        self._scan_folder(folder)

    def _scan_folder(self, folder):
        """Scan folder for FITS/XISF files."""
        extensions = {'.fits', '.fit', '.fts', '.xisf'}
        files = []
        for root, dirs, filenames in os.walk(folder):
            # Skip excluded folders
            base = os.path.basename(root).lower()
            if any(base.startswith(p) for p in
                   ('extracted_', 'duplicates', 'astronomical_analysis_')):
                continue
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                full = fn.lower()
                if ext in extensions or full.endswith('.fits.fz'):
                    files.append(os.path.join(root, fn))

        files.sort(key=lambda x: os.path.basename(x).lower())
        self._file_list = files
        self._file_list_widget.clear()
        for f in files:
            self._file_list_widget.addItem(os.path.basename(f))

        self._file_count_label.setText(
            self._tr(f"{len(files)} files", f"{len(files)} fichiers"))

        if files:
            self._file_list_widget.setCurrentRow(0)

    def _sort_files(self):
        """Sort file list by selected criterion."""
        idx = self._sort_combo.currentIndex()
        if idx == 0:  # Name
            self._file_list.sort(key=lambda x: os.path.basename(x).lower())
        elif idx == 1:  # Date
            self._file_list.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        # FWHM sort would need cached results — skip if no data

        current = self._current_path
        self._file_list_widget.clear()
        for f in self._file_list:
            self._file_list_widget.addItem(os.path.basename(f))

        # Restore selection
        if current and current in self._file_list:
            self._file_list_widget.setCurrentRow(self._file_list.index(current))

    def _on_file_selected(self, row):
        if row < 0 or row >= len(self._file_list):
            return
        self._file_index = row
        path = self._file_list[row]
        self._load_image(path)

        # Prefetch neighbors
        prefetch = self.cfg.get('image_viewer', {}).get('prefetch_neighbors', 2)
        for offset in range(1, prefetch + 1):
            for idx in [row + offset, row - offset]:
                if 0 <= idx < len(self._file_list):
                    neighbor = self._file_list[idx]
                    if self._image_cache.get(neighbor) is None:
                        self._prefetch_image(neighbor)

    def _load_image(self, path):
        """Load image from cache or start background worker."""
        cached = self._image_cache.get(path)
        if cached is not None:
            self._current_path = path
            self._current_data = cached['data']
            self._current_header = cached['header']
            self._display_current()
            return

        self._current_path = path
        self._analysis_status.setText(
            self._tr("Loading...", "Chargement..."))

        if self._load_worker is not None and self._load_worker.isRunning():
            self._load_worker.quit()
            self._load_worker.wait(500)

        self._load_worker = ImageLoadWorker(path)
        self._load_worker.loaded.connect(self._on_image_loaded)
        self._load_worker.error.connect(self._on_image_error)
        self._load_worker.start()

    def _prefetch_image(self, path):
        """Prefetch an image in background without displaying."""
        if not hasattr(self, '_prefetch_workers'):
            self._prefetch_workers = []
        # Limit concurrent prefetch to avoid memory pressure
        self._prefetch_workers = [w for w in self._prefetch_workers if w.isRunning()]
        if len(self._prefetch_workers) >= 3:
            return
        worker = ImageLoadWorker(path)
        worker.loaded.connect(lambda p, d, h: self._image_cache.put(p, {'data': d, 'header': h}))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self._prefetch_workers.append(worker)

    def _on_image_loaded(self, path, data, header):
        self._image_cache.put(path, {'data': data, 'header': header})
        if path == self._current_path:
            self._current_data = data
            self._current_header = header
            self._display_current()
            self._analysis_status.setText("")
            signals.image_loaded.emit(path)

    def _on_image_error(self, path, error):
        if path == self._current_path:
            self._analysis_status.setText(self._tr(f"Error: {error}", f"Erreur : {error}"))
            logger.error("Image load error %s: %s", path, error)

    def _display_current(self):
        """Display current image and update info panel."""
        if self._current_data is None:
            return
        self._viewer.set_image(self._current_data)
        self._update_info_panel()

        # Reset analysis overlays
        self._fwhm_result = None
        self._corner_result = None
        for key in self._fwhm_labels:
            self._fwhm_labels[key].setText("—")

    def _update_info_panel(self):
        """Update right panel with header info."""
        h = self._current_header
        data = self._current_data

        self._info_labels['object'].setText(
            str(h.get('OBJECT', h.get('TARGET', '—'))))
        if data is not None:
            shape = data.shape
            if data.ndim == 2:
                self._info_labels['dimensions'].setText(f"{shape[1]}x{shape[0]}")
            elif data.ndim == 3:
                self._info_labels['dimensions'].setText(
                    f"{shape[2]}x{shape[1]} ({shape[0]}ch)")
        self._info_labels['filter'].setText(str(h.get('FILTER', '—')))
        exp = h.get('EXPTIME', h.get('EXPOSURE', '—'))
        self._info_labels['exposure'].setText(f"{exp}s" if exp != '—' else '—')
        self._info_labels['camera'].setText(
            str(h.get('INSTRUME', h.get('CAMERA', '—'))))
        self._info_labels['telescope'].setText(
            str(h.get('TELESCOP', '—')))
        self._info_labels['date'].setText(
            str(h.get('DATE-OBS', '—'))[:19])

    # ── Navigation ──
    def _prev_image(self):
        if self._file_index > 0:
            self._file_list_widget.setCurrentRow(self._file_index - 1)

    def _next_image(self):
        if self._file_index < len(self._file_list) - 1:
            self._file_list_widget.setCurrentRow(self._file_index + 1)

    # ── Stretch ──
    def _on_stretch_changed(self, checked):
        if self._current_data is not None:
            self._viewer._apply_stretch()

    # ── FWHM Analysis ──
    def _run_fwhm_analysis(self):
        if self._current_data is None:
            return

        data = self._current_data
        if data.ndim == 3:
            # Convert to mono for analysis
            if data.shape[0] == 3:
                data = 0.2126 * data[0] + 0.7152 * data[1] + 0.0722 * data[2]
            else:
                data = data[0]

        self._analysis_status.setText(
            self._tr("Analyzing FWHM...", "Analyse FWHM en cours..."))

        # Get pixel scale from header
        pixel_scale = None
        ps = self._current_header.get('CDELT2') or self._current_header.get('SECPIX')
        if ps:
            try:
                pixel_scale = abs(float(ps)) * 3600  # deg to arcsec
            except (ValueError, TypeError):
                pass

        if self._fwhm_worker is not None and self._fwhm_worker.isRunning():
            self._fwhm_worker.quit()
            self._fwhm_worker.wait(500)

        self._fwhm_worker = FWHMAnalysisWorker(data, pixel_scale)
        self._fwhm_worker.completed.connect(self._on_fwhm_completed)
        self._fwhm_worker.error.connect(self._on_fwhm_error)
        self._fwhm_worker.start()

    def _on_fwhm_completed(self, result):
        self._fwhm_result = result
        stats = result.get('stats', {})

        # Update FWHM stats labels
        self._fwhm_labels['star_count'].setText(str(stats.get('star_count', 0)))
        self._fwhm_labels['median'].setText(f"{stats.get('median_fwhm', 0):.2f} px")
        self._fwhm_labels['mean'].setText(f"{stats.get('mean_fwhm', 0):.2f} px")
        self._fwhm_labels['std'].setText(f"{stats.get('std_fwhm', 0):.2f} px")
        self._fwhm_labels['min'].setText(f"{stats.get('min_fwhm', 0):.2f} px")
        self._fwhm_labels['max'].setText(f"{stats.get('max_fwhm', 0):.2f} px")

        # Set overlays
        heatmap = result.get('heatmap')
        stars = result.get('stars', [])
        if heatmap is not None and self._current_data is not None:
            shape = self._current_data.shape[-2:]  # (H, W)
            self._viewer.set_heatmap(heatmap, shape)
        if stars:
            self._viewer.set_stars(stars)

        # Update corner inspector from worker results (already computed in background)
        corner_data = result.get('corner_data')
        if corner_data:
            self._corner_result = corner_data
            self._corner_inspector.update_data(corner_data)

        n_stars = stats.get('star_count', 0)
        self._analysis_status.setText(
            self._tr(f"Done — {n_stars} stars detected",
                     f"Termine — {n_stars} etoiles detectees"))
        signals.image_analysis_completed.emit(result)

    def _on_fwhm_error(self, error):
        self._analysis_status.setText(self._tr(f"Error: {error}", f"Erreur : {error}"))
        logger.error("FWHM analysis error: %s", error)

    # ── Toggle overlays ──
    def _on_fwhm_toggled(self, checked):
        self._viewer.toggle_heatmap(checked)

    def _on_stars_toggled(self, checked):
        self._viewer.toggle_stars(checked)

    def _on_corners_toggled(self, checked):
        self._corner_inspector.setVisible(checked)

    # ── Header viewer ──
    def _show_header_dialog(self):
        if not self._current_header:
            return
        dialog = HeaderViewerDialog(
            self._current_header, self._current_path or "", self.lang, self)
        dialog.exec()

    # ── Pixel info ──
    def _update_pixel_info(self, x, y, val_str):
        self._pixel_label.setText(f"{self._tr('Pixel', 'Pixel')} ({x}, {y}): {val_str}")

    # ── Signal handlers ──
    def _on_image_loaded_signal(self, path):
        pass  # External signal — can be used by other tabs

    def _on_analysis_signal(self, result):
        pass  # External signal — can be used by other tabs
