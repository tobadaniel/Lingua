"""SQLite vocabulary store with SM-2 spaced repetition for Lingua.

Pure standard library. Each card is a term in the language being learned,
its translation, and an optional example sentence. Scheduling follows the
classic SM-2 algorithm (the one Anki is based on): grades adjust an ease
factor and an interval in days, and a card you fail comes back in minutes
instead of days.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time

DAY = 86400.0
RELEARN_SECONDS = 600.0  # a failed card returns in 10 minutes
MIN_EASE = 1.3
START_EASE = 2.5
MASTERED_INTERVAL_DAYS = 21

# Grade name -> SM-2 quality score (0-5).
GRADES = {"again": 0, "hard": 3, "good": 4, "easy": 5}


def normalize_language(language: str) -> str:
    lang = re.sub(r"[^a-z0-9 \-]", "", (language or "").strip().lower())
    return re.sub(r"\s+", "-", lang)[:40] or "general"


class VocabStore:
    """Thread-safe card store backed by one SQLite connection."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        # RLock: stats() composes due_counts() while already holding it.
        self._lock = threading.RLock()
        self._init_schema()

    @classmethod
    def from_path(cls, path) -> "VocabStore":
        from pathlib import Path

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.Error:
            pass
        return cls(conn)

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term TEXT NOT NULL,
                    term_key TEXT NOT NULL,
                    translation TEXT NOT NULL,
                    language TEXT NOT NULL,
                    example TEXT NOT NULL DEFAULT '',
                    ease REAL NOT NULL DEFAULT 2.5,
                    interval_days REAL NOT NULL DEFAULT 0,
                    repetitions INTEGER NOT NULL DEFAULT 0,
                    lapses INTEGER NOT NULL DEFAULT 0,
                    reviews INTEGER NOT NULL DEFAULT 0,
                    due_at REAL NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_grade TEXT
                )
                """
            )
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_lang_term "
                "ON cards(language, term_key)"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER NOT NULL,
                    grade TEXT NOT NULL,
                    reviewed_at REAL NOT NULL
                )
                """
            )
            self._conn.commit()

    def _row_to_dict(self, row: sqlite3.Row, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        return {
            "id": row["id"],
            "term": row["term"],
            "translation": row["translation"],
            "language": row["language"],
            "example": row["example"],
            "ease": round(row["ease"], 2),
            "interval_days": row["interval_days"],
            "repetitions": row["repetitions"],
            "lapses": row["lapses"],
            "reviews": row["reviews"],
            "due_at": row["due_at"],
            "due": row["due_at"] <= now,
            "mastered": row["interval_days"] >= MASTERED_INTERVAL_DAYS,
            "last_grade": row["last_grade"],
        }

    # -- cards ------------------------------------------------------------

    def add(self, term: str, translation: str, language: str,
            example: str = "") -> dict:
        term = (term or "").strip()
        translation = (translation or "").strip()
        if not term or not translation:
            raise ValueError("Both a term and its translation are required.")
        language = normalize_language(language)
        term_key = re.sub(r"\s+", " ", term.lower())
        now = time.time()
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM cards WHERE language = ? AND term_key = ?",
                (language, term_key),
            ).fetchone()
            if existing is not None:
                self._conn.execute(
                    "UPDATE cards SET translation = ?, example = ?, "
                    "updated_at = ? WHERE id = ?",
                    (translation, (example or "").strip() or existing["example"],
                     now, existing["id"]),
                )
                self._conn.commit()
                row = self._conn.execute(
                    "SELECT * FROM cards WHERE id = ?", (existing["id"],)
                ).fetchone()
                result = self._row_to_dict(row, now)
                result["duplicate"] = True
                return result
            cur = self._conn.execute(
                "INSERT INTO cards (term, term_key, translation, language, "
                "example, due_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (term, term_key, translation, language,
                 (example or "").strip(), now, now, now),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM cards WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            result = self._row_to_dict(row, now)
            result["duplicate"] = False
            return result

    def due(self, limit: int = 10, language: str | None = None,
            now: float | None = None) -> list[dict]:
        now = time.time() if now is None else now
        limit = max(1, min(int(limit or 10), 50))
        with self._lock:
            if language:
                rows = self._conn.execute(
                    "SELECT * FROM cards WHERE due_at <= ? AND language = ? "
                    "ORDER BY due_at ASC LIMIT ?",
                    (now, normalize_language(language), limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM cards WHERE due_at <= ? "
                    "ORDER BY due_at ASC LIMIT ?",
                    (now, limit),
                ).fetchall()
            return [self._row_to_dict(r, now) for r in rows]

    def due_counts(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        with self._lock:
            rows = self._conn.execute(
                "SELECT language, COUNT(*) AS n FROM cards "
                "WHERE due_at <= ? GROUP BY language ORDER BY n DESC",
                (now,),
            ).fetchall()
            by_language = {r["language"]: r["n"] for r in rows}
            return {"total": sum(by_language.values()), "by_language": by_language}

    def grade(self, card_id: int, grade: str,
              now: float | None = None) -> dict:
        grade = (grade or "").strip().lower()
        if grade not in GRADES:
            raise ValueError(
                f"Unknown grade '{grade}'. Use one of: {', '.join(GRADES)}."
            )
        quality = GRADES[grade]
        now = time.time() if now is None else now
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cards WHERE id = ?", (int(card_id),)
            ).fetchone()
            if row is None:
                raise ValueError(f"No card with id {card_id}.")
            ease = row["ease"]
            interval = row["interval_days"]
            reps = row["repetitions"]
            lapses = row["lapses"]
            if quality < 3:
                # Failed: relearn shortly, keep the ease penalty small.
                reps = 0
                lapses += 1
                ease = max(MIN_EASE, ease - 0.2)
                interval = 0
                due_at = now + RELEARN_SECONDS
            else:
                if reps == 0:
                    interval = 1
                elif reps == 1:
                    interval = 6
                else:
                    interval = round(interval * ease, 2)
                reps += 1
                ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
                ease = max(MIN_EASE, round(ease, 4))
                due_at = now + interval * DAY
            self._conn.execute(
                "UPDATE cards SET ease = ?, interval_days = ?, repetitions = ?, "
                "lapses = ?, reviews = reviews + 1, due_at = ?, updated_at = ?, "
                "last_grade = ? WHERE id = ?",
                (ease, interval, reps, lapses, due_at, now, grade, int(card_id)),
            )
            self._conn.execute(
                "INSERT INTO review_log (card_id, grade, reviewed_at) "
                "VALUES (?, ?, ?)",
                (int(card_id), grade, now),
            )
            self._conn.commit()
            updated = self._conn.execute(
                "SELECT * FROM cards WHERE id = ?", (int(card_id),)
            ).fetchone()
            result = self._row_to_dict(updated, now)
            result["next_interval_days"] = interval
            result["graded"] = grade
            return result

    def list_cards(self, limit: int = 30, language: str | None = None,
                   query: str | None = None) -> list[dict]:
        limit = max(1, min(int(limit or 30), 200))
        clauses, params = [], []
        if language:
            clauses.append("language = ?")
            params.append(normalize_language(language))
        if query:
            clauses.append("(term LIKE ? OR translation LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM cards {where} ORDER BY language, due_at ASC "
                f"LIMIT ?",
                (*params, limit),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def remove(self, card_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cards WHERE id = ?", (int(card_id),)
            ).fetchone()
            if row is None:
                return None
            removed = self._row_to_dict(row)
            self._conn.execute("DELETE FROM cards WHERE id = ?", (int(card_id),))
            self._conn.commit()
            return removed

    def stats(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            rows = self._conn.execute(
                "SELECT language, COUNT(*) AS n FROM cards "
                "GROUP BY language ORDER BY n DESC"
            ).fetchall()
            by_language = {r["language"]: r["n"] for r in rows}
            mastered = self._conn.execute(
                "SELECT COUNT(*) FROM cards WHERE interval_days >= ?",
                (MASTERED_INTERVAL_DAYS,),
            ).fetchone()[0]
            total_reviews = self._conn.execute(
                "SELECT COUNT(*) FROM review_log"
            ).fetchone()[0]
            week_ago = now - 7 * DAY
            active_days = self._conn.execute(
                "SELECT COUNT(DISTINCT CAST(reviewed_at / 86400 AS INTEGER)) "
                "FROM review_log WHERE reviewed_at >= ?",
                (week_ago,),
            ).fetchone()[0]
            due = self.due_counts(now)
            return {
                "total_cards": total,
                "by_language": by_language,
                "due_now": due["total"],
                "due_by_language": due["by_language"],
                "mastered": mastered,
                "total_reviews": total_reviews,
                "active_days_last_7": active_days,
            }
