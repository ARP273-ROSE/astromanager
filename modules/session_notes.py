#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - SESSION NOTES
================================================================================
Simple CRUD for per-session text notes stored in the database.
================================================================================
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionNotes:
    """Manage per-session observation notes."""

    def __init__(self):
        from core.database import get_db
        self.db = get_db()

    def save_note(self, session_date: str, note_text: str,
                  target_name: Optional[str] = None) -> int:
        """Save or update a session note. Returns note id."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO session_notes (session_date, target_name, note_text)
                VALUES (?, ?, ?)
                ON CONFLICT(session_date, COALESCE(target_name, ''))
                DO UPDATE SET
                    note_text = excluded.note_text,
                    updated_at = CURRENT_TIMESTAMP
            """, (session_date, target_name, note_text))
            cursor.execute(
                "SELECT id FROM session_notes WHERE session_date = ? AND COALESCE(target_name, '') = COALESCE(?, '')",
                (session_date, target_name)
            )
            return cursor.fetchone()[0]

    def get_notes(self, session_date: Optional[str] = None,
                  target_name: Optional[str] = None) -> List[Dict]:
        """Get session notes, optionally filtered."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM session_notes WHERE 1=1"
            params = []
            if session_date:
                query += " AND session_date = ?"
                params.append(session_date)
            if target_name:
                query += " AND target_name = ?"
                params.append(target_name)
            query += " ORDER BY session_date DESC, created_at DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_note(self, note_id: int) -> Optional[Dict]:
        """Get a single note by id."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM session_notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_note(self, note_id: int):
        """Delete a session note."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM session_notes WHERE id = ?", (note_id,))

    def get_session_dates(self) -> List[str]:
        """Get all dates that have notes."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT session_date FROM session_notes ORDER BY session_date DESC"
            )
            return [row['session_date'] for row in cursor.fetchall()]
