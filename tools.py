"""Tool handlers for the Lingua plugin.

Storage resolution order:
1. Hermes' own plugin storage (``plugins.plugin_storage.plugin_db``), so
   decks live in the active profile's plugin-data directory and survive
   plugin updates and removal.
2. A local fallback directory, used when the plugin is imported outside
   Hermes (unit tests, standalone demos). ``HERMES_LINGUA_HOME`` pins the
   fallback location; otherwise ``$HERMES_HOME/plugin-data/lingua`` or
   ``~/.hermes/plugin-data/lingua`` is used.

No network access, no subprocesses, no credential access: the only I/O is
the plugin's own SQLite database and its bundled starter deck file.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

try:  # Hermes loads the plugin as a package; tests may load it flat.
    from .vocab_store import VocabStore
except ImportError:  # pragma: no cover - flat import fallback
    from vocab_store import VocabStore

_STORE: VocabStore | None = None
_STORE_LOCK = threading.Lock()


def _fallback_db_path() -> Path:
    override = os.environ.get("HERMES_LINGUA_HOME", "").strip()
    if override:
        return Path(override) / "lingua.db"
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    base = Path(hermes_home) if hermes_home else Path.home() / ".hermes"
    return base / "plugin-data" / "lingua" / "lingua.db"


def get_store() -> VocabStore:
    """Return the shared VocabStore, creating it on first use."""
    global _STORE
    if _STORE is not None:
        return _STORE
    with _STORE_LOCK:
        if _STORE is not None:
            return _STORE
        store: VocabStore | None = None
        try:
            from plugins.plugin_storage import plugin_db

            conn = plugin_db("lingua")
            store = VocabStore(conn)
        except Exception:
            store = None
        if store is None:
            store = VocabStore.from_path(_fallback_db_path())
        _STORE = store
        return _STORE


def reset_store() -> None:
    """Drop the cached store (tests only)."""
    global _STORE
    with _STORE_LOCK:
        _STORE = None


def load_starter_deck(language: str) -> list[dict]:
    """Read a bundled starter deck (list of card dicts) by language."""
    deck_file = Path(__file__).parent / "data" / "starter_decks.json"
    with open(deck_file, encoding="utf-8") as handle:
        decks = json.load(handle)
    key = (language or "").strip().lower()
    if key not in decks:
        raise ValueError(
            f"No starter deck for '{language}'. Available: "
            f"{', '.join(sorted(decks))}."
        )
    return decks[key]


def seed_starter_deck(language: str) -> dict:
    """Add every card from a starter deck, skipping ones already present."""
    cards = load_starter_deck(language)
    store = get_store()
    added, skipped = 0, 0
    for card in cards:
        result = store.add(
            card["term"], card["translation"], language,
            example=card.get("example", ""),
        )
        if result.get("duplicate"):
            skipped += 1
        else:
            added += 1
    return {"language": language, "added": added, "skipped_existing": skipped}


def _err(message: str) -> str:
    return json.dumps({"error": message})


def lingua_add(args: dict, **kwargs) -> str:
    args = args or {}
    try:
        card = get_store().add(
            args.get("term", ""), args.get("translation", ""),
            args.get("language", ""), example=args.get("example", ""),
        )
        return json.dumps({"added": card})
    except Exception as exc:  # never raise out of a handler
        return _err(f"Could not add card: {exc}")


def lingua_due(args: dict, **kwargs) -> str:
    args = args or {}
    try:
        store = get_store()
        cards = store.due(limit=args.get("limit", 10),
                          language=args.get("language"))
        counts = store.due_counts()
        return json.dumps({
            "due_now_total": counts["total"],
            "due_by_language": counts["by_language"],
            "session_cards": cards,
        })
    except Exception as exc:
        return _err(f"Could not fetch due cards: {exc}")


def lingua_grade(args: dict, **kwargs) -> str:
    args = args or {}
    if args.get("id") is None or not args.get("grade"):
        return _err("Provide the card id and a grade: again, hard, good, or easy.")
    try:
        card = get_store().grade(int(args["id"]), args["grade"])
        return json.dumps({"graded": card})
    except Exception as exc:
        return _err(f"Could not grade card: {exc}")


def lingua_list(args: dict, **kwargs) -> str:
    args = args or {}
    try:
        cards = get_store().list_cards(
            limit=args.get("limit", 30),
            language=args.get("language"),
            query=args.get("query"),
        )
        return json.dumps({"count": len(cards), "cards": cards})
    except Exception as exc:
        return _err(f"Could not list cards: {exc}")


def lingua_remove(args: dict, **kwargs) -> str:
    args = args or {}
    if args.get("id") is None:
        return _err("Provide the numeric id of the card to remove.")
    try:
        removed = get_store().remove(int(args["id"]))
        if removed is None:
            return _err(f"No card with id {args['id']}.")
        return json.dumps({"removed": removed})
    except Exception as exc:
        return _err(f"Could not remove card: {exc}")


def lingua_stats(args: dict, **kwargs) -> str:
    try:
        return json.dumps(get_store().stats())
    except Exception as exc:
        return _err(f"Could not read learning stats: {exc}")
