#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - CROSS-SECTION COMPARISON TAB
================================================================================
Dual image viewer with:
- Side-by-side FITS/XISF comparison
- Interactive line tool for cross-section profiles
- RGB / luminance intensity curves
- Filter attenuation analysis (Welch t-test, SNR, exposure factor)
- Auto-alignment (astroalign / phase correlation)
- Histogram comparison with median markers
- CSV export of profiles and histograms
================================================================================
"""

import logging
import os
import csv
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QGroupBox, QGridLayout, QSizePolicy,
    QCheckBox, QFileDialog, QSplitter, QTabWidget, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QToolBar
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPointF, QLineF
)
from PyQt6.QtGui import (
    QFont, QImage, QPixmap, QPainter, QColor, QPen, QCursor
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
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from astropy.io import fits as astropy_fits
    HAS_ASTROPY = True
except ImportError:
    HAS_ASTROPY = False


# ─────────────────────────────────────────────────────────────────────────────
# Image Panel Widget (single image with line drawing)
# ─────────────────────────────────────────────────────────────────────────────
class ImagePanelWidget(QLabel):
    """Single image display with line drawing capability."""
    line_drawn = pyqtSignal(QPointF, QPointF)  # start, end (normalized 0-1)
    region_selected = pyqtSignal(QPointF, QPointF, str)  # start, end, region_type

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 200)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background: {COLORS.get('bg_dark', '#0d0d1a')}; border: 1px solid #333;")
        self._title = title
        self._data = None
        self._display_pixmap = None
        self._line_start = None
        self._line_end = None
        self._drawing = False
        self._mode = 'line'  # 'line' or 'region_signal' or 'region_bg'
        self._region_rects = {}  # {type: (start, end)}

    def set_image(self, data):
        """Set image from numpy array."""
        if not HAS_NUMPY or data is None:
            return
        self._data = data
        self._update_display()

    def _update_display(self):
        """Render current data to pixmap."""
        if self._data is None:
            return

        data = self._data
        # Auto-stretch
        if data.ndim == 3 and data.shape[0] in (3, 4):
            data = np.transpose(data, (1, 2, 0))

        if data.ndim == 2:
            vmin, vmax = np.nanpercentile(data, [0.5, 99.5])
            if vmax <= vmin:
                vmax = vmin + 1
            d = np.clip((data - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
            h, w = d.shape
            self._display_buffer = np.ascontiguousarray(d)
            qimg = QImage(self._display_buffer.data, w, h, w, QImage.Format.Format_Grayscale8)
        elif data.ndim == 3:
            vmin, vmax = np.nanpercentile(data, [0.5, 99.5])
            if vmax <= vmin:
                vmax = vmin + 1
            d = np.clip((data - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
            h, w = d.shape[:2]
            if d.shape[2] >= 3:
                self._display_buffer = np.ascontiguousarray(d[:, :, :3])
                qimg = QImage(self._display_buffer.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            else:
                self._display_buffer = np.ascontiguousarray(d[:, :, 0])
                qimg = QImage(self._display_buffer.data, w, h, w, QImage.Format.Format_Grayscale8)
        else:
            return

        self._display_pixmap = QPixmap.fromImage(qimg)
        self._repaint()

    def _repaint(self):
        """Repaint with overlays."""
        if self._display_pixmap is None:
            return

        pix = self._display_pixmap.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

        # Draw line overlay
        if self._line_start and self._line_end:
            painter = QPainter(pix)
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            w, h = pix.width(), pix.height()
            painter.drawLine(
                int(self._line_start.x() * w), int(self._line_start.y() * h),
                int(self._line_end.x() * w), int(self._line_end.y() * h))
            painter.end()

        # Draw region rectangles
        if self._region_rects:
            painter = QPainter(pix)
            colors = {'signal': QColor(255, 200, 0, 100), 'background': QColor(0, 150, 255, 100)}
            w, h = pix.width(), pix.height()
            for rtype, (s, e) in self._region_rects.items():
                color = colors.get(rtype, QColor(255, 255, 255, 80))
                painter.setPen(QPen(color, 2))
                painter.setBrush(QColor(color.red(), color.green(), color.blue(), 40))
                x0 = int(min(s.x(), e.x()) * w)
                y0 = int(min(s.y(), e.y()) * h)
                x1 = int(max(s.x(), e.x()) * w)
                y1 = int(max(s.y(), e.y()) * h)
                painter.drawRect(x0, y0, x1 - x0, y1 - y0)
            painter.end()

        self.setPixmap(pix)

    def set_line(self, start, end):
        """Set line from normalized coordinates."""
        self._line_start = start
        self._line_end = end
        self._repaint()

    def set_mode(self, mode):
        self._mode = mode

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._display_pixmap:
            pos = self._normalize_pos(event.position())
            if pos:
                self._drawing = True
                if self._mode == 'line':
                    self._line_start = pos
                    self._line_end = pos
                else:
                    self._line_start = pos

    def mouseMoveEvent(self, event):
        if self._drawing and self._display_pixmap:
            pos = self._normalize_pos(event.position())
            if pos:
                self._line_end = pos
                self._repaint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            pos = self._normalize_pos(event.position())
            if pos:
                self._line_end = pos
                if self._mode == 'line':
                    self.line_drawn.emit(self._line_start, self._line_end)
                elif self._mode.startswith('region_'):
                    rtype = self._mode.replace('region_', '')
                    self._region_rects[rtype] = (self._line_start, self._line_end)
                    self.region_selected.emit(
                        self._line_start, self._line_end, rtype)
                self._repaint()

    def _normalize_pos(self, pos):
        """Convert widget pixel position to normalized [0,1] coordinates."""
        if self._display_pixmap is None:
            return None
        pix = self._display_pixmap.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        # Compute offset (centered)
        ox = (self.width() - pix.width()) / 2
        oy = (self.height() - pix.height()) / 2
        x = (pos.x() - ox) / max(pix.width(), 1)
        y = (pos.y() - oy) / max(pix.height(), 1)
        if 0 <= x <= 1 and 0 <= y <= 1:
            return QPointF(x, y)
        return None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._repaint()


# ─────────────────────────────────────────────────────────────────────────────
# Image Load Worker (background I/O)
# ─────────────────────────────────────────────────────────────────────────────
class _CSImageLoadWorker(QThread):
    """Load FITS/XISF in background for cross-section tab."""
    loaded = pyqtSignal(int, str, object, dict)  # slot, path, data, header
    error = pyqtSignal(int, str, str)  # slot, path, error

    def __init__(self, slot, path, parent=None):
        super().__init__(parent)
        self.slot = slot
        self.path = path

    def run(self):
        try:
            ext = self.path.lower()
            if ext.endswith('.xisf'):
                from gui.tabs.image_viewer_tab import ImageLoadWorker
                worker = ImageLoadWorker.__new__(ImageLoadWorker)
                data, header = worker._load_xisf(self.path)
            elif HAS_ASTROPY:
                with astropy_fits.open(self.path, memmap=False) as hdul:
                    data, header = None, {}
                    for hdu in hdul:
                        if hdu.data is not None:
                            data = hdu.data.astype(np.float32)
                            header = dict(hdu.header)
                            break
                if data is None:
                    raise ValueError("No image data found")
            else:
                raise ImportError("astropy required for FITS files")
            self.loaded.emit(self.slot, self.path, data, header)
        except Exception as e:
            self.error.emit(self.slot, self.path, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Alignment Worker
# ─────────────────────────────────────────────────────────────────────────────
class AlignmentWorker(QThread):
    """Run image alignment in background."""
    completed = pyqtSignal(object, dict)  # aligned_array, transform_dict
    error = pyqtSignal(str)

    def __init__(self, source, target, method='astroalign', parent=None):
        super().__init__(parent)
        self.source = source
        self.target = target
        self.method = method

    def run(self):
        try:
            from modules.image_alignment import ImageAligner
            aligner = ImageAligner()
            if self.method == 'astroalign':
                result, info = aligner.align_astroalign(self.source, self.target)
            else:
                result, info = aligner.align_phase_correlation(self.source, self.target)

            if result is None:
                self.error.emit(str(info))
            else:
                self.completed.emit(result, info)
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Main Cross-Section Tab
# ─────────────────────────────────────────────────────────────────────────────
class CrossSectionTab(QWidget):
    """Cross-section comparison tab with dual viewer and analysis tools."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lang = get_lang()
        self.cfg = get_config()

        self._data1 = None
        self._data2 = None
        self._header1 = {}
        self._header2 = {}
        self._path1 = None
        self._path2 = None

        self._init_ui()
        self._connect_signals()

    def _tr(self, en, fr):
        return fr if self.lang == "fr" else en

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ── Top toolbar ──
        toolbar = QHBoxLayout()

        load1_btn = QPushButton(self._tr("📂 Image 1", "📂 Image 1"))
        load1_btn.setToolTip(get_tip('cs_image1'))
        load1_btn.clicked.connect(lambda: self._load_image(1))
        toolbar.addWidget(load1_btn)

        load2_btn = QPushButton(self._tr("📂 Image 2", "📂 Image 2"))
        load2_btn.setToolTip(get_tip('cs_image2'))
        load2_btn.clicked.connect(lambda: self._load_image(2))
        toolbar.addWidget(load2_btn)

        toolbar.addWidget(self._make_separator())

        # Mode selector
        toolbar.addWidget(QLabel(self._tr("Mode:", "Mode :")))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([
            self._tr("Line Profile", "Profil Ligne"),
            self._tr("Signal Region", "Region Signal"),
            self._tr("Background Region", "Region Fond"),
        ])
        self._mode_combo.setToolTip(get_tip('cs_mode'))
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        toolbar.addWidget(self._mode_combo)

        toolbar.addWidget(self._make_separator())

        # Color mode
        toolbar.addWidget(QLabel(self._tr("Color:", "Couleur :")))
        self._color_combo = QComboBox()
        self._color_combo.addItems([
            "Luminance",
            self._tr("Red", "Rouge"),
            self._tr("Green", "Vert"),
            self._tr("Blue", "Bleu"),
            "RGB"
        ])
        self._color_combo.setToolTip(get_tip('cs_color'))
        toolbar.addWidget(self._color_combo)

        toolbar.addWidget(self._make_separator())

        # Align button
        align_btn = QPushButton(self._tr("🔄 Auto-Align", "🔄 Alignement Auto"))
        align_btn.setToolTip(get_tip('cs_align'))
        align_btn.clicked.connect(self._auto_align)
        toolbar.addWidget(align_btn)

        # Export button
        export_btn = QPushButton(self._tr("💾 Export CSV", "💾 Exporter CSV"))
        export_btn.setToolTip(get_tip('cs_export'))
        export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(export_btn)

        toolbar.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #9ca3af;")
        toolbar.addWidget(self._status_label)

        main_layout.addLayout(toolbar)

        # ── Main content: splitter ──
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top: dual image panels
        images_widget = QWidget()
        images_layout = QHBoxLayout(images_widget)
        images_layout.setContentsMargins(0, 0, 0, 0)

        self._panel1 = ImagePanelWidget(self._tr("Image 1", "Image 1"))
        self._panel1.line_drawn.connect(self._on_line_drawn)
        self._panel1.region_selected.connect(self._on_region_selected)
        images_layout.addWidget(self._panel1)

        self._panel2 = ImagePanelWidget(self._tr("Image 2", "Image 2"))
        images_layout.addWidget(self._panel2)

        main_splitter.addWidget(images_widget)

        # Bottom: analysis tabs
        analysis_tabs = QTabWidget()

        # Profile chart tab
        profile_widget = QWidget()
        profile_layout = QVBoxLayout(profile_widget)
        profile_layout.setContentsMargins(4, 4, 4, 4)

        if HAS_MATPLOTLIB:
            self._profile_fig = Figure(figsize=(10, 3), facecolor='#1a1a2e')
            self._profile_canvas = FigureCanvasQTAgg(self._profile_fig)
            self._profile_ax = self._profile_fig.add_subplot(111)
            self._profile_ax.set_facecolor('#1a1a2e')
            self._profile_ax.tick_params(colors='white', labelsize=8)
            self._profile_fig.tight_layout(pad=0.5)
            profile_layout.addWidget(self._profile_canvas)
        else:
            profile_layout.addWidget(QLabel(self._tr("matplotlib required", "matplotlib requis")))

        analysis_tabs.addTab(profile_widget,
            self._tr("📈 Profile", "📈 Profil"))

        # Histogram tab
        hist_widget = QWidget()
        hist_layout = QVBoxLayout(hist_widget)
        hist_layout.setContentsMargins(4, 4, 4, 4)

        if HAS_MATPLOTLIB:
            self._hist_fig = Figure(figsize=(10, 3), facecolor='#1a1a2e')
            self._hist_canvas = FigureCanvasQTAgg(self._hist_fig)
            self._hist_ax = self._hist_fig.add_subplot(111)
            self._hist_ax.set_facecolor('#1a1a2e')
            self._hist_ax.tick_params(colors='white', labelsize=8)
            self._hist_fig.tight_layout(pad=0.5)
            hist_layout.addWidget(self._hist_canvas)
        else:
            hist_layout.addWidget(QLabel(self._tr("matplotlib required", "matplotlib requis")))

        analysis_tabs.addTab(hist_widget,
            self._tr("📊 Histogram", "📊 Histogramme"))

        # Attenuation tab
        atten_widget = QWidget()
        atten_layout = QVBoxLayout(atten_widget)
        atten_layout.setContentsMargins(4, 4, 4, 4)

        self._atten_table = QTableWidget(0, 2)
        self._atten_table.setHorizontalHeaderLabels([
            self._tr("Metric", "Metrique"),
            self._tr("Value", "Valeur")])
        self._atten_table.horizontalHeader().setStretchLastSection(True)
        self._atten_table.setAlternatingRowColors(True)
        self._atten_table.setStyleSheet(
            f"background: {COLORS.get('bg_dark', '#0d0d1a')}; color: #e5e7eb;")
        self._atten_table.setToolTip(self._tr("Filter attenuation analysis results", "Résultats de l'analyse d'atténuation du filtre"))
        atten_layout.addWidget(self._atten_table)

        compute_btn = QPushButton(
            self._tr("🧮 Compute Attenuation", "🧮 Calculer Attenuation"))
        compute_btn.setToolTip(self._tr(
            "Compute filter attenuation between the two images using selected regions",
            "Calculer l'attenuation du filtre entre les deux images avec les regions selectionnees"))
        compute_btn.clicked.connect(self._compute_attenuation)
        atten_layout.addWidget(compute_btn)

        analysis_tabs.addTab(atten_widget,
            self._tr("🔬 Attenuation", "🔬 Attenuation"))

        main_splitter.addWidget(analysis_tabs)

        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(main_splitter)

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #333;")
        return sep

    def _connect_signals(self):
        signals.cross_section_loaded.connect(self._on_external_load)
        signals.cross_section_result.connect(self._on_external_result)

    # ── Image loading ──
    def _load_image(self, slot):
        """Open file dialog and load image into slot 1 or 2 (background I/O)."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr(f"Select Image {slot}", f"Selectionner Image {slot}"),
            "",
            "FITS/XISF (*.fits *.fit *.fts *.xisf *.fits.fz);;All (*)")
        if not path:
            return

        self._status_label.setText(self._tr("Loading...", "Chargement..."))
        worker = _CSImageLoadWorker(slot, path)
        worker.loaded.connect(self._on_cs_image_loaded)
        worker.error.connect(self._on_cs_image_error)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        # Keep reference to prevent GC
        if not hasattr(self, '_load_workers'):
            self._load_workers = []
        self._load_workers = [w for w in self._load_workers if w.isRunning()]
        self._load_workers.append(worker)

    def _on_cs_image_loaded(self, slot, path, data, header):
        """Handle background image load completion."""
        if slot == 1:
            self._data1 = data
            self._header1 = header
            self._path1 = path
            self._panel1.set_image(data)
        else:
            self._data2 = data
            self._header2 = header
            self._path2 = path
            self._panel2.set_image(data)

        self._status_label.setText(
            self._tr(f"Loaded: {os.path.basename(path)}",
                     f"Charge : {os.path.basename(path)}"))

        if self._data1 is not None and self._data2 is not None:
            self._update_histograms()
            signals.cross_section_loaded.emit(
                self._path1 or "", self._path2 or "")

    def _on_cs_image_error(self, slot, path, error):
        self._status_label.setText(self._tr(f"Error: {error}", f"Erreur : {error}"))
        logger.error("Cross-section load error slot %d: %s", slot, error)

    # ── Mode switching ──
    def _on_mode_changed(self, idx):
        modes = ['line', 'region_signal', 'region_background']
        mode = modes[idx] if idx < len(modes) else 'line'
        self._panel1.set_mode(mode)
        self._panel2.set_mode(mode)

    # ── Line profile ──
    def _on_line_drawn(self, start, end):
        """Handle line drawn on image 1 — mirror on image 2 and compute profiles."""
        self._panel2.set_line(start, end)

        if self._data1 is None:
            return

        try:
            from modules.cross_section import CrossSectionAnalyzer
            analyzer = CrossSectionAnalyzer()

            color_mode = self._color_combo.currentText().lower()

            # Convert normalized coords to pixel coords
            shape = self._data1.shape
            h = shape[-2] if self._data1.ndim >= 2 else shape[0]
            w = shape[-1]
            start_px = (start.x() * w, start.y() * h)
            end_px = (end.x() * w, end.y() * h)

            profile1 = analyzer.sample_line_profile(
                self._data1, start_px, end_px, mode=color_mode)

            profile2 = None
            if self._data2 is not None:
                shape2 = self._data2.shape
                h2 = shape2[-2] if self._data2.ndim >= 2 else shape2[0]
                w2 = shape2[-1]
                start_px2 = (start.x() * w2, start.y() * h2)
                end_px2 = (end.x() * w2, end.y() * h2)
                profile2 = analyzer.sample_line_profile(
                    self._data2, start_px2, end_px2, mode=color_mode)

            self._plot_profiles(profile1, profile2, color_mode)
            self._last_profiles = (profile1, profile2)

        except Exception as e:
            logger.error("Profile error: %s", e)
            self._status_label.setText(self._tr(f"Profile error: {e}", f"Erreur : {e}"))

    def _plot_profiles(self, profile1, profile2, color_mode):
        """Plot intensity profiles on the chart."""
        if not HAS_MATPLOTLIB:
            return

        self._profile_ax.clear()
        self._profile_ax.set_facecolor('#1a1a2e')

        if color_mode == 'rgb':
            # Multi-channel
            p1 = profile1.get('profile', {})
            if isinstance(p1, dict):
                for ch, color in [('red', '#ff4444'), ('green', '#44ff44'), ('blue', '#4444ff')]:
                    if ch in p1:
                        self._profile_ax.plot(
                            profile1['distances'], p1[ch],
                            color=color, alpha=0.7, linewidth=1,
                            label=f"Img1 {ch[0].upper()}")
            if profile2:
                p2 = profile2.get('profile', {})
                if isinstance(p2, dict):
                    for ch, color in [('red', '#ff8888'), ('green', '#88ff88'), ('blue', '#8888ff')]:
                        if ch in p2:
                            self._profile_ax.plot(
                                profile2['distances'], p2[ch],
                                color=color, alpha=0.5, linewidth=1, linestyle='--',
                                label=f"Img2 {ch[0].upper()}")
        else:
            # Single channel
            p1 = profile1.get('profile')
            if p1 is not None and hasattr(p1, '__len__'):
                self._profile_ax.plot(
                    profile1['distances'], p1,
                    color='#22d3ee', linewidth=1.5, label="Image 1")
            if profile2:
                p2 = profile2.get('profile')
                if p2 is not None and hasattr(p2, '__len__'):
                    self._profile_ax.plot(
                        profile2['distances'], p2,
                        color='#f472b6', linewidth=1.5, linestyle='--', label="Image 2")

        self._profile_ax.set_xlabel(self._tr("Distance (px)", "Distance (px)"), color='white', fontsize=8)
        self._profile_ax.set_ylabel(self._tr("Intensity", "Intensité"), color='white', fontsize=8)
        self._profile_ax.legend(fontsize=7, facecolor='#1a1a2e',
                                 edgecolor='#333', labelcolor='white')
        self._profile_ax.grid(True, alpha=0.2, color='white')
        self._profile_fig.tight_layout(pad=0.5)
        self._profile_canvas.draw_idle()

    # ── Histograms ──
    def _update_histograms(self):
        """Compute and display histograms for both images."""
        if not HAS_MATPLOTLIB or not HAS_NUMPY:
            return

        self._hist_ax.clear()
        self._hist_ax.set_facecolor('#1a1a2e')

        for data, color, label in [
            (self._data1, '#22d3ee', 'Image 1'),
            (self._data2, '#f472b6', 'Image 2'),
        ]:
            if data is None:
                continue
            flat = data.ravel()
            flat = flat[np.isfinite(flat)]
            self._hist_ax.hist(
                flat, bins=256, color=color, alpha=0.5,
                label=label, log=True, histtype='stepfilled')
            median = np.median(flat)
            self._hist_ax.axvline(median, color=color, linestyle='--',
                                   linewidth=1, alpha=0.8)

        self._hist_ax.set_xlabel(self._tr("Intensity", "Intensité"), color='white', fontsize=8)
        self._hist_ax.set_ylabel(self._tr("Count (log)", "Nombre (log)"), color='white', fontsize=8)
        self._hist_ax.legend(fontsize=7, facecolor='#1a1a2e',
                              edgecolor='#333', labelcolor='white')
        self._hist_ax.grid(True, alpha=0.2, color='white')
        self._hist_fig.tight_layout(pad=0.5)
        self._hist_canvas.draw_idle()

    # ── Region selection ──
    def _on_region_selected(self, start, end, region_type):
        """Handle region selection on image."""
        # Mirror region on panel 2
        self._panel2._region_rects[region_type] = (start, end)
        self._panel2._repaint()

    # ── Attenuation analysis ──
    def _compute_attenuation(self):
        """Compute filter attenuation between the two images."""
        if self._data1 is None or self._data2 is None:
            self._status_label.setText(
                self._tr("Load both images first", "Charger les deux images d'abord"))
            return

        signal_region = self._panel1._region_rects.get('signal')
        bg_region = self._panel1._region_rects.get('background')

        if not signal_region or not bg_region:
            self._status_label.setText(
                self._tr("Select signal and background regions first",
                         "Selectionner les regions signal et fond d'abord"))
            return

        try:
            from modules.filter_attenuation import FilterAttenuationAnalyzer
            analyzer = FilterAttenuationAnalyzer()

            d1 = self._data1
            d2 = self._data2
            # Convert to mono if needed
            if d1.ndim == 3:
                d1 = d1[0] if d1.shape[0] != 3 else (
                    0.2126 * d1[0] + 0.7152 * d1[1] + 0.0722 * d1[2])
            if d2.ndim == 3:
                d2 = d2[0] if d2.shape[0] != 3 else (
                    0.2126 * d2[0] + 0.7152 * d2[1] + 0.0722 * d2[2])

            h1, w1 = d1.shape
            h2, w2 = d2.shape

            # Convert normalized coords to pixel box
            s_s, s_e = signal_region
            sig_box = (
                int(min(s_s.x(), s_e.x()) * w1),
                int(min(s_s.y(), s_e.y()) * h1),
                int(max(s_s.x(), s_e.x()) * w1),
                int(max(s_s.y(), s_e.y()) * h1),
            )
            b_s, b_e = bg_region
            bg_box = (
                int(min(b_s.x(), b_e.x()) * w1),
                int(min(b_s.y(), b_e.y()) * h1),
                int(max(b_s.x(), b_e.x()) * w1),
                int(max(b_s.y(), b_e.y()) * h1),
            )

            result = analyzer.analyze(d1, d2, sig_box, bg_box)
            self._display_attenuation_results(result)
            signals.cross_section_result.emit(result)

        except Exception as e:
            self._status_label.setText(self._tr(f"Attenuation error: {e}", f"Erreur : {e}"))
            logger.error("Attenuation analysis error: %s", e)

    def _display_attenuation_results(self, result):
        """Populate attenuation results table."""
        rows = []

        atten = result.get('attenuation', {})
        rows.append((self._tr("Attenuation (%)", "Attenuation (%)"),
                      f"{atten.get('attenuation_pct', 0):.2f}%"))
        rows.append((self._tr("Attenuation (mag)", "Attenuation (mag)"),
                      f"{atten.get('attenuation_mag', 0):.3f}"))

        welch = result.get('welch_test', {})
        rows.append((self._tr("Welch t-statistic", "Welch t-statistique"),
                      f"{welch.get('t_statistic', 0):.4f}"))
        rows.append((self._tr("Welch p-value", "Welch p-valeur"),
                      f"{welch.get('p_value', 0):.6f}"))
        sig = welch.get('significant', False)
        rows.append((self._tr("Significant (p<0.05)", "Significatif (p<0.05)"),
                      self._tr("Yes", "Oui") if sig else self._tr("No", "Non")))
        rows.append(("Cohen's d", f"{welch.get('effect_size_cohen_d', 0):.3f}"))

        snr_p = result.get('snr_photon', {})
        if 'image1' in snr_p:
            rows.append((self._tr("SNR Photon (Img 1)", "SNR Photon (Img 1)"),
                          f"{snr_p['image1'].get('snr', 0):.2f}"))
        if 'image2' in snr_p:
            rows.append((self._tr("SNR Photon (Img 2)", "SNR Photon (Img 2)"),
                          f"{snr_p['image2'].get('snr', 0):.2f}"))

        snr_f = result.get('snr_flux', {})
        if 'image1' in snr_f:
            rows.append((self._tr("SNR Flux (Img 1)", "SNR Flux (Img 1)"),
                          f"{snr_f['image1'].get('snr', 0):.2f}"))
        if 'image2' in snr_f:
            rows.append((self._tr("SNR Flux (Img 2)", "SNR Flux (Img 2)"),
                          f"{snr_f['image2'].get('snr', 0):.2f}"))

        ef_p = result.get('exposure_factor_photon', 0)
        ef_f = result.get('exposure_factor_flux', 0)
        rows.append((self._tr("Exposure Factor (Photon)", "Facteur Exposition (Photon)"),
                      f"{ef_p:.2f}x"))
        rows.append((self._tr("Exposure Factor (Flux)", "Facteur Exposition (Flux)"),
                      f"{ef_f:.2f}x"))

        self._atten_table.setRowCount(len(rows))
        for i, (metric, value) in enumerate(rows):
            self._atten_table.setItem(i, 0, QTableWidgetItem(metric))
            self._atten_table.setItem(i, 1, QTableWidgetItem(value))

    # ── Auto-alignment ──
    def _auto_align(self):
        """Auto-align image 2 to image 1."""
        if self._data1 is None or self._data2 is None:
            self._status_label.setText(
                self._tr("Load both images first", "Charger les deux images d'abord"))
            return

        self._status_label.setText(
            self._tr("Aligning...", "Alignement en cours..."))

        d1 = self._data1
        d2 = self._data2
        # Convert to mono for alignment
        if d1.ndim == 3:
            d1 = d1[0] if d1.shape[0] != 3 else (
                0.2126 * d1[0] + 0.7152 * d1[1] + 0.0722 * d1[2])
        if d2.ndim == 3:
            d2 = d2[0] if d2.shape[0] != 3 else (
                0.2126 * d2[0] + 0.7152 * d2[1] + 0.0722 * d2[2])

        if hasattr(self, '_align_worker') and self._align_worker is not None and self._align_worker.isRunning():
            self._align_worker.quit()
            self._align_worker.wait(500)
        self._align_worker = AlignmentWorker(d2, d1, 'astroalign')
        self._align_worker.completed.connect(self._on_align_completed)
        self._align_worker.error.connect(self._on_align_error)
        self._align_worker.finished.connect(self._align_worker.deleteLater)
        self._align_worker.start()

    def _on_align_completed(self, aligned, info):
        """Replace image 2 with aligned version."""
        self._data2 = aligned
        self._panel2.set_image(aligned)
        self._update_histograms()

        rot = info.get('rotation_deg', 0)
        matches = info.get('n_matches', 0)
        self._status_label.setText(
            self._tr(f"Aligned — {matches} matches, {rot:.2f}° rotation",
                     f"Aligne — {matches} correspondances, {rot:.2f}° rotation"))

    def _on_align_error(self, error):
        self._status_label.setText(
            self._tr(f"Alignment failed: {error}",
                     f"Echec alignement : {error}"))

    # ── CSV Export ──
    def _export_csv(self):
        """Export profiles and histograms to CSV."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Export CSV", "Exporter CSV"),
            str(Path.home() / "cross_section_export.csv"),
            "CSV (*.csv)")
        if not path:
            return

        try:
            profiles = getattr(self, '_last_profiles', (None, None))
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['distance_px', 'image1_intensity', 'image2_intensity'])

                p1, p2 = profiles
                if p1 and 'distances' in p1:
                    profile1_vals = p1.get('profile', [])
                    profile2_vals = p2.get('profile', []) if p2 else []

                    if hasattr(profile1_vals, '__len__'):
                        for i, d in enumerate(p1['distances']):
                            v1 = profile1_vals[i] if i < len(profile1_vals) else ''
                            v2 = (profile2_vals[i]
                                  if hasattr(profile2_vals, '__len__') and i < len(profile2_vals)
                                  else '')
                            writer.writerow([f"{d:.2f}", f"{v1:.4f}" if v1 != '' else '',
                                             f"{v2:.4f}" if v2 != '' else ''])

            self._status_label.setText(
                self._tr(f"Exported to {os.path.basename(path)}",
                         f"Exporte vers {os.path.basename(path)}"))
        except Exception as e:
            self._status_label.setText(self._tr(f"Export error: {e}", f"Erreur : {e}"))

    # ── External signal handlers ──
    def _on_external_load(self, path1, path2):
        pass

    def _on_external_result(self, result):
        pass
