#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - COSMIC THEME ENGINE
================================================================================
Modern dark cosmic theme with neon accents, rounded corners, and smooth design.
================================================================================
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor, QFont, QPixmap, QCursor, QPainter, QPen, QBrush, QRadialGradient
from PyQt6.QtCore import Qt, QPoint


# ============================================================================
# COSMIC COLOR PALETTE
# ============================================================================

COLORS = {
    # Backgrounds
    'bg_darkest':     '#080c16',   # Deep space void
    'bg_dark':        '#0a0e1a',   # Deep space black
    'bg_medium':      '#141828',   # Nebula dark
    'bg_light':       '#1e2438',   # Star field
    'bg_lighter':     '#2a3248',   # Lighter panels
    'bg_input':       '#161c30',   # Input fields
    'bg_hover':       '#252d45',   # Hover state
    'bg_selected':    '#1a3050',   # Selected state

    # Accents (very muted, desaturated - truly gentle)
    'accent_cyan':    '#94b8c8',   # Muted grey-blue
    'accent_purple':  '#a8a0c0',   # Muted grey-lavender
    'accent_pink':    '#c0a0ac',   # Muted dusty rose
    'accent_orange':  '#c0b098',   # Muted warm beige
    'accent_yellow':  '#b8b090',   # Muted grey-wheat

    # Semantic (very desaturated, just enough tint to recognize)
    'success':        '#88b098',   # Muted sage green
    'warning':        '#b8a880',   # Muted tan
    'error':          '#b89090',   # Muted dusty coral
    'info':           '#90a8b8',   # Muted blue-grey

    # Text
    'text_primary':   '#c8ccd4',   # Soft grey-white
    'text_secondary': '#7a8498',   # Dim grey
    'text_disabled':  '#4a5270',   # Very dim
    'text_accent':    '#94b8c8',   # Muted accent text

    # Borders
    'border':         '#2d3550',   # Normal border
    'border_light':   '#3d4663',   # Light border
    'border_focus':   '#94b8c8',   # Focus border (muted)

    # Progress bar
    'progress_bg':    '#1a1e30',
    'progress_chunk': '#94b8c8',

    # Tab
    'tab_active':     '#94b8c8',
    'tab_inactive':   '#4a5270',

    # Scrollbar
    'scrollbar_bg':   '#0a0e1a',
    'scrollbar_handle': '#2d3550',
    'scrollbar_hover':  '#3d4663',
}

# Filter colors for charts (very muted, desaturated tones)
FILTER_COLORS = {
    'L':     '#a0a0a8',
    'R':     '#b89898',
    'G':     '#90b098',
    'B':     '#90a0b8',
    'Ha':    '#b8a0a0',
    'OIII':  '#90b0b0',
    'SII':   '#b0a890',
    'RGB':   '#a8a8a8',
    'OSC':   '#a8a090',
    'Clear': '#909098',
}


def get_mono_font(size: int = 9) -> QFont:
    """Get cross-platform monospace font with Greek character support."""
    font = QFont("Cascadia Mono", size)
    font.setFamilies(["Cascadia Mono", "Cascadia Code", "Consolas",
                      "Source Code Pro", "Fira Code", "monospace"])
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


# ============================================================================
# FILTER NAME NORMALISER & PRETTIFIER
# ============================================================================

# Greek Unicode → ASCII equivalents (for normalising FITS header values
# written by software like N.I.N.A. that embeds real Greek chars)
_GREEK_TO_ASCII = {
    'α': 'a',  'Α': 'A',  'β': 'b',  'Β': 'B',
    'γ': 'g',  'Γ': 'G',  'δ': 'd',  'Δ': 'D',
    'ε': 'e',  'Ε': 'E',  'ζ': 'z',  'Ζ': 'Z',
    'η': 'e',  'Η': 'E',  'θ': 'th', 'Θ': 'TH',
    'ι': 'i',  'Ι': 'I',  'κ': 'k',  'Κ': 'K',
    'λ': 'l',  'Λ': 'L',  'μ': 'mu', 'Μ': 'MU',
    'ν': 'n',  'Ν': 'N',  'ξ': 'x',  'Ξ': 'X',
    'ο': 'o',  'Ο': 'O',  'π': 'pi', 'Π': 'PI',
    'ρ': 'r',  'Ρ': 'R',  'σ': 's',  'Σ': 'S',
    'ς': 's',  'τ': 't',  'Τ': 'T',  'υ': 'u',
    'Υ': 'U',  'φ': 'ph', 'Φ': 'PH', 'χ': 'ch',
    'Χ': 'CH', 'ψ': 'ps', 'Ψ': 'PS', 'ω': 'o',
    'Ω': 'O',
}


def normalize_filter_name(name: str) -> str:
    """Normalise a filter name to pure ASCII for consistent storage.

    Replaces Greek Unicode characters with their ASCII transliterations
    so that 'Hα' and 'Ha' both become 'HA' after ``.upper()``.
    """
    if not name:
        return name or ''
    return ''.join(_GREEK_TO_ASCII.get(ch, ch) for ch in name.strip())


# Case-insensitive mapping: uppercase key → pretty display string
_FILTER_GREEK = {
    # Hydrogen Balmer series
    'HA':       'Hα',
    'H-ALPHA':  'Hα',
    'HALPHA':   'Hα',
    'HB':       'Hβ',
    'H-BETA':   'Hβ',
    'HBETA':    'Hβ',
    'HG':       'Hγ',
    'H-GAMMA':  'Hγ',
    'HGAMMA':   'Hγ',
    'HD':       'Hδ',
    'H-DELTA':  'Hδ',
    'HDELTA':   'Hδ',
    # Ionised oxygen / sulphur / nitrogen
    'OIII':     'O\u2009III',
    'O-III':    'O\u2009III',
    'O3':       'O\u2009III',
    'SII':      'S\u2009II',
    'S-II':     'S\u2009II',
    'S2':       'S\u2009II',
    'NII':      'N\u2009II',
    'N-II':     'N\u2009II',
    'N2':       'N\u2009II',
}


_FILTER_PATTERNS = None

def _get_filter_patterns():
    """Return cached compiled regex patterns for filter name prettification."""
    global _FILTER_PATTERNS
    if _FILTER_PATTERNS is None:
        import re
        _FILTER_PATTERNS = [(re.compile(re.escape(key), re.IGNORECASE), val)
                            for key, val in sorted(_FILTER_GREEK.items(), key=lambda x: len(x[0]), reverse=True)]
    return _FILTER_PATTERNS


def prettify_filter_name(name: str) -> str:
    """Convert a filter code to a human-friendly Unicode string.

    Handles both ASCII codes *and* names that already contain Greek
    characters (normalises first, then prettifies).

    Examples:
        'Ha'      → 'Hα'
        'Hα'      → 'Hα'   (Greek alpha in input)
        'OIII'    → 'O III'
        'SII'     → 'S II'
        'H-alpha' → 'Hα'
        'Baader Ha 7nm' → 'Baader Hα 7nm'
    """
    if not name or not name.strip():
        return name or ''

    # Normalise Greek chars to ASCII first so lookup always works
    name = normalize_filter_name(name)

    # Direct match (case-insensitive)
    hit = _FILTER_GREEK.get(name.upper())
    if hit:
        return hit

    # Partial replacement: replace known tokens inside longer names
    result = name
    for pattern, replacement in _get_filter_patterns():
        if pattern.search(result):
            result = pattern.sub(replacement, result)
            break

    return result


def get_cosmic_stylesheet() -> str:
    """Generate the complete cosmic dark QSS stylesheet"""
    c = COLORS
    return f"""
    /* ================================================================ */
    /* GLOBAL                                                           */
    /* ================================================================ */
    QMainWindow {{
        background-color: {c['bg_dark']};
        color: {c['text_primary']};
    }}
    QWidget {{
        background-color: {c['bg_dark']};
        color: {c['text_primary']};
        font-family: "Segoe UI", "Ubuntu", "Cantarell", sans-serif;
        font-size: 9pt;
    }}

    /* ================================================================ */
    /* LABELS                                                           */
    /* ================================================================ */
    QLabel {{
        color: {c['text_primary']};
        background: transparent;
        padding: 1px;
    }}
    QLabel[heading="true"] {{
        font-size: 12pt;
        font-weight: bold;
        color: {c['accent_cyan']};
        padding: 3px 2px;
    }}

    /* ================================================================ */
    /* BUTTONS                                                          */
    /* ================================================================ */
    QPushButton {{
        background-color: {c['bg_lighter']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 5px;
        padding: 5px 12px;
        font-weight: 500;
        min-height: 22px;
    }}
    QPushButton:hover {{
        background-color: {c['bg_hover']};
        border-color: {c['accent_cyan']};
    }}
    QPushButton:pressed {{
        background-color: {c['bg_selected']};
    }}
    QPushButton:disabled {{
        color: {c['text_disabled']};
        background-color: {c['bg_medium']};
        border-color: {c['bg_light']};
    }}
    QPushButton[accent="true"] {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #244858, stop:1 #1c3a48);
        color: {c['text_primary']};
        border: 1px solid {c['accent_cyan']};
        font-weight: bold;
    }}
    QPushButton[accent="true"]:hover {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #2e5868, stop:1 #244858);
    }}
    QPushButton[danger="true"] {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #583030, stop:1 #482828);
        color: {c['text_primary']};
        border: 1px solid {c['error']};
    }}
    QPushButton[success="true"] {{
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #184830, stop:1 #143828);
        color: {c['text_primary']};
        border: 1px solid {c['success']};
    }}

    /* ================================================================ */
    /* INPUT FIELDS                                                     */
    /* ================================================================ */
    QLineEdit {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 5px;
        padding: 4px 8px;
        selection-background-color: {c['accent_cyan']};
        selection-color: {c['bg_dark']};
    }}
    QLineEdit:focus {{
        border-color: {c['border_focus']};
    }}
    QLineEdit:disabled {{
        color: {c['text_disabled']};
        background-color: {c['bg_medium']};
    }}

    QTextEdit {{
        background-color: {c['bg_input']};
        color: {c['success']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 6px;
        font-family: "Cascadia Mono", "Cascadia Code", "Consolas", "Source Code Pro", "Fira Code", monospace;
        font-size: 9pt;
    }}
    QTextEdit:focus {{
        border-color: {c['border_focus']};
    }}

    QSpinBox, QDoubleSpinBox {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {c['border_focus']};
    }}

    /* ================================================================ */
    /* COMBO BOX                                                        */
    /* ================================================================ */
    QComboBox {{
        background-color: {c['bg_input']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 5px;
        padding: 4px 8px;
        min-width: 100px;
    }}
    QComboBox:hover {{
        border-color: {c['accent_cyan']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c['bg_medium']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        selection-background-color: {c['bg_selected']};
        selection-color: {c['accent_cyan']};
    }}

    /* ================================================================ */
    /* CHECK BOX                                                        */
    /* ================================================================ */
    QCheckBox {{
        color: {c['text_primary']};
        spacing: 6px;
        background: transparent;
        padding: 2px 0;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {c['border_light']};
        border-radius: 4px;
        background-color: {c['bg_input']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c['accent_cyan']};
        border-color: {c['accent_cyan']};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c['accent_cyan']};
    }}

    /* ================================================================ */
    /* RADIO BUTTON                                                     */
    /* ================================================================ */
    QRadioButton {{
        color: {c['text_primary']};
        spacing: 6px;
        background: transparent;
        padding: 2px 0;
    }}
    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {c['border_light']};
        border-radius: 10px;
        background-color: {c['bg_input']};
    }}
    QRadioButton::indicator:checked {{
        background-color: {c['accent_cyan']};
        border: 5px solid {c['bg_light']};
    }}
    QRadioButton::indicator:hover {{
        border-color: {c['accent_cyan']};
    }}

    /* ================================================================ */
    /* GROUP BOX                                                        */
    /* ================================================================ */
    QGroupBox {{
        background-color: {c['bg_medium']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        margin-top: 10px;
        padding: 14px 8px 6px 8px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 8px;
        color: {c['accent_cyan']};
        background-color: {c['bg_medium']};
        border-radius: 3px;
        font-size: 9pt;
    }}

    /* ================================================================ */
    /* TAB WIDGET                                                       */
    /* ================================================================ */
    QTabWidget::pane {{
        background-color: {c['bg_dark']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        top: -1px;
        padding: 2px;
    }}
    QTabBar::tab {{
        background-color: {c['bg_medium']};
        color: {c['text_secondary']};
        border: 1px solid {c['border']};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 5px 14px;
        margin-right: 2px;
        font-weight: 500;
        font-size: 9pt;
    }}
    QTabBar::tab:selected {{
        background-color: {c['bg_dark']};
        color: {c['accent_cyan']};
        border-bottom: 2px solid {c['accent_cyan']};
        font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {c['bg_light']};
        color: {c['text_primary']};
    }}

    /* ================================================================ */
    /* PROGRESS BAR                                                     */
    /* ================================================================ */
    QProgressBar {{
        background-color: {c['progress_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 5px;
        height: 20px;
        text-align: center;
        font-weight: bold;
    }}
    QProgressBar::chunk {{
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #1e4858, stop:0.5 {c['accent_cyan']}, stop:1 #1e4858);
        border-radius: 5px;
    }}

    /* ================================================================ */
    /* SCROLLBAR                                                        */
    /* ================================================================ */
    QScrollBar:vertical {{
        background: {c['scrollbar_bg']};
        width: 10px;
        margin: 0;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['scrollbar_handle']};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['scrollbar_hover']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {c['scrollbar_bg']};
        height: 10px;
        margin: 0;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['scrollbar_handle']};
        border-radius: 5px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c['scrollbar_hover']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* ================================================================ */
    /* TABLE VIEW                                                       */
    /* ================================================================ */
    QTableWidget, QTableView {{
        background-color: {c['bg_input']};
        alternate-background-color: {c['bg_medium']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        gridline-color: {c['border']};
        selection-background-color: {c['bg_selected']};
        selection-color: {c['accent_cyan']};
    }}
    QHeaderView::section {{
        background-color: {c['bg_light']};
        color: {c['accent_cyan']};
        border: 1px solid {c['border']};
        padding: 4px 4px;
        font-weight: bold;
        font-size: 8pt;
    }}

    /* ================================================================ */
    /* SPLITTER                                                         */
    /* ================================================================ */
    QSplitter::handle {{
        background-color: {c['border']};
        width: 2px;
        height: 2px;
    }}
    QSplitter::handle:hover {{
        background-color: {c['accent_cyan']};
    }}

    /* ================================================================ */
    /* MENU BAR                                                         */
    /* ================================================================ */
    QMenuBar {{
        background-color: {c['bg_darkest']};
        color: {c['text_primary']};
        border-bottom: 1px solid {c['border']};
        padding: 4px;
    }}
    QMenuBar::item {{
        padding: 6px 12px;
        border-radius: 4px;
    }}
    QMenuBar::item:selected {{
        background-color: {c['bg_hover']};
        color: {c['accent_cyan']};
    }}
    QMenu {{
        background-color: {c['bg_medium']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 24px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {c['bg_selected']};
        color: {c['accent_cyan']};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {c['border']};
        margin: 4px 8px;
    }}

    /* ================================================================ */
    /* STATUS BAR                                                       */
    /* ================================================================ */
    QStatusBar {{
        background-color: {c['bg_darkest']};
        color: {c['text_secondary']};
        border-top: 1px solid {c['border']};
        padding: 4px;
    }}

    /* ================================================================ */
    /* TOOL TIP                                                         */
    /* ================================================================ */
    QToolTip {{
        background-color: {c['bg_light']};
        color: {c['text_primary']};
        border: 1px solid {c['accent_cyan']};
        border-radius: 4px;
        padding: 6px;
        font-size: 9pt;
    }}

    /* ================================================================ */
    /* FRAME                                                            */
    /* ================================================================ */
    QFrame[frameShape="4"] {{ /* HLine */
        color: {c['border']};
        max-height: 1px;
    }}

    /* ================================================================ */
    /* DIALOG                                                           */
    /* ================================================================ */
    QDialog {{
        background-color: {c['bg_dark']};
        border-radius: 12px;
    }}
    QMessageBox {{
        background-color: {c['bg_dark']};
    }}
    """


def create_cosmic_cursor(size: int = 24) -> QCursor:
    """
    Create a custom Saturn-themed cursor.
    Draws a small ringed planet with a cosmic glow.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    cx, cy = size // 2, size // 2
    planet_r = size // 6

    # Outer glow
    glow = QRadialGradient(cx, cy, size // 3)
    glow.setColorAt(0.0, QColor(148, 184, 200, 40))
    glow.setColorAt(1.0, QColor(148, 184, 200, 0))
    painter.setBrush(QBrush(glow))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPoint(cx, cy), size // 3, size // 3)

    # Ring (ellipse behind & in front of planet)
    ring_pen = QPen(QColor(200, 180, 140, 180), 1.5)
    painter.setPen(ring_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(cx - planet_r * 2, cy - planet_r // 2,
                        planet_r * 4, planet_r)

    # Planet body
    planet_gradient = QRadialGradient(cx - 1, cy - 1, planet_r)
    planet_gradient.setColorAt(0.0, QColor(220, 200, 160))
    planet_gradient.setColorAt(0.5, QColor(180, 150, 100))
    planet_gradient.setColorAt(1.0, QColor(120, 90, 60))
    painter.setBrush(QBrush(planet_gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPoint(cx, cy), planet_r, planet_r)

    # Arrow pointer (top-left)
    arrow_pen = QPen(QColor(255, 255, 255, 220), 1.5)
    painter.setPen(arrow_pen)
    painter.drawLine(0, 0, 6, 3)
    painter.drawLine(0, 0, 3, 6)
    painter.drawLine(0, 0, cx - planet_r, cy - planet_r)

    painter.end()

    return QCursor(pixmap, 0, 0)


def apply_cosmic_theme(app: QApplication):
    """Apply the cosmic dark theme to the application"""
    app.setStyleSheet(get_cosmic_stylesheet())

    # Set palette for any widgets that don't use stylesheets
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS['bg_dark']))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS['bg_input']))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS['bg_medium']))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS['bg_lighter']))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS['accent_cyan']))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS['bg_dark']))
    palette.setColor(QPalette.ColorRole.Link, QColor(COLORS['accent_cyan']))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(COLORS['accent_purple']))
    app.setPalette(palette)

    # Apply custom cosmic cursor
    try:
        cursor = create_cosmic_cursor()
        app.setOverrideCursor(cursor)
        # Restore normal cursor for text inputs
        app.restoreOverrideCursor()
        # Set as default cursor instead (via stylesheet won't work, set per-window)
    except Exception:
        pass  # Fallback to system cursor if QPainter fails
