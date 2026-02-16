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

    try:
        loc = locale.getlocale()[0]
        if loc and loc.startswith('fr'):
            _detected_lang = 'fr'
            return _detected_lang
    except (ValueError, AttributeError):
        pass

    _detected_lang = 'en'
    return _detected_lang
