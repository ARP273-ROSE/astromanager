#!/usr/bin/env python3
"""Centralized language detection for AstroManager."""

import locale
import logging

logger = logging.getLogger(__name__)

_detected_lang = None

def get_lang() -> str:
    """Get the application language ('fr' or 'en'). Cached after first call."""
    global _detected_lang
    if _detected_lang is not None:
        return _detected_lang

    try:
        from core.config import get_config
        config = get_config()
        lang_setting = config.get('application.language', 'auto')
        if lang_setting in ('fr', 'en'):
            _detected_lang = lang_setting
            return _detected_lang
    except Exception:
        pass

    _detected_lang = detect_system_language()
    return _detected_lang


def detect_system_language() -> str:
    """'fr' si la langue du système est le français, sinon 'en'.

    Qt lit la langue d'affichage correctement sur les trois systèmes ; la
    locale Python sert de repli. Sous Windows, celle-ci vaut par exemple
    « French_France » : la comparer à « fr » sans tenir compte de la casse,
    sinon un Windows français démarrait en anglais.
    """
    try:
        from PyQt6.QtCore import QLocale
        langues = QLocale.system().uiLanguages()
        if langues:
            return 'fr' if langues[0].lower().startswith('fr') else 'en'
    except Exception:
        pass
    for lire in (lambda: locale.getlocale()[0],
                 lambda: __import__('os').environ.get('LANG')):
        try:
            loc = lire()
        except (ValueError, AttributeError):
            continue
        if loc:
            return 'fr' if loc.lower().startswith(('fr', 'french')) else 'en'
    return 'en'
