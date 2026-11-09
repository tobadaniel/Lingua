"""Tool handlers for the Lingua plugin.

Storage resolution order:
1. Hermes' own plugin storage (``plugins.plugin_storage.plugin_db``), so
   decks live in the active profile's plugin-data directory and survive
   plugin updates and removal.
2. A local fallback directory, used when the plugin is imported outside
   Hermes (unit tests, standalone demos). ``HERMES_LINGUA_HOME`` pins the
   fallback location; otherwise ``$HERMES_HOME/plugin-data/lingua`` or
   ``~/.hermes/plugin-data/lingua`` is used.

The six core tools are fully offline: no network access, no
subprocesses, no credential access; their only I/O is the plugin's own
SQLite database and its bundled starter deck file. The three optional
tutor tools (lingua_example, lingua_mnemonic, lingua_check) are the
sole exception: they call the Otari gateway (api.otari.ai) through
otari_client, and only when OTARI_API_KEY is set.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

try:  # Hermes loads the plugin as a package; tests may load it flat.
    from .vocab_store import VocabStore
    from . import otari_client
except ImportError:  # pragma: no cover - flat import fallback
    from vocab_store import VocabStore
    import otari_client

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


# ---------------------------------------------------------------------------
# Otari tutor layer (optional; needs OTARI_API_KEY)
#
# Settings arrive from __init__.register() via configure_otari(). The API
# key itself is never a plugin setting: otari_client reads OTARI_API_KEY
# from the environment, so the key stays out of Hermes config files.
# Tests inject a client with a fake transport via set_otari_client().
# ---------------------------------------------------------------------------

_OTARI_SETTINGS = {"enabled": True, "model": "", "base_url": ""}
_OTARI_CLIENT = None


def configure_otari(enabled=True, model="", base_url="") -> None:
    """Apply plugin settings for the tutor layer (called at register)."""
    global _OTARI_CLIENT
    _OTARI_SETTINGS["enabled"] = bool(enabled)
    _OTARI_SETTINGS["model"] = (model or "").strip()
    _OTARI_SETTINGS["base_url"] = (base_url or "").strip()
    _OTARI_CLIENT = None  # rebuild lazily with the new settings


def set_otari_client(client) -> None:
    """Inject a ready-made OtariClient (tests / demos with fakes)."""
    global _OTARI_CLIENT
    _OTARI_CLIENT = client


def reset_otari_client() -> None:
    global _OTARI_CLIENT
    _OTARI_CLIENT = None


def get_otari_client():
    global _OTARI_CLIENT
    if _OTARI_CLIENT is None:
        _OTARI_CLIENT = otari_client.OtariClient(
            model=_OTARI_SETTINGS["model"] or None,
            base_url=_OTARI_SETTINGS["base_url"] or None,
        )
    return _OTARI_CLIENT


def _tutor_client_or_error():
    """Return (client, None) or (None, error_json) for tutor handlers."""
    if not _OTARI_SETTINGS["enabled"]:
        return None, _err(
            "The Otari tutor layer is disabled (plugin setting "
            "otari_enabled is false). Lingua's offline tools still work; "
            "re-enable otari_enabled to use the tutor tools."
        )
    client = get_otari_client()
    if not client.configured:
        return None, json.dumps({
            "error": otari_client.MISSING_KEY_MESSAGE,
            "otari_configured": False,
        })
    return client, None


_TUTOR_SYSTEM = (
    "You are a precise, encouraging language tutor inside a spaced "
    "repetition app. Answer with a single JSON object only: no markdown, "
    "no code fences, no commentary outside the JSON."
)


def _parse_json_object(text: str) -> dict:
    """Best-effort parse of a JSON object from a model reply."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start:end + 1]
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("model reply was not a JSON object")
    return parsed


def _tutor_chat(client, user_prompt: str) -> str:
    return client.chat_text(
        [
            {"role": "system", "content": _TUTOR_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
        max_tokens=400,
    )


def _card_fields(args: dict):
    """Resolve term/translation/language from args or a stored card id."""
    term = (args.get("term") or "").strip()
    translation = (args.get("translation") or "").strip()
    language = (args.get("language") or "").strip()
    if args.get("id") is not None and not (term and translation):
        cards = get_store().list_cards(limit=200)
        card = next((c for c in cards if c["id"] == int(args["id"])), None)
        if card is None:
            raise ValueError(f"No card with id {args['id']}.")
        term = term or card["term"]
        translation = translation or card["translation"]
        language = language or card["language"]
    if not (term and translation and language):
        raise ValueError(
            "Provide term, translation and language (or the id of a card)."
        )
    return term, translation, language


def lingua_example(args: dict, **kwargs) -> str:
    """Generate a contextual example sentence for a card, via Otari."""
    args = args or {}
    client, error = _tutor_client_or_error()
    if error:
        return error
    try:
        term, translation, language = _card_fields(args)
        context = (args.get("context") or "").strip()
        prompt = (
            f"Language being learned: {language}. Word/phrase: \"{term}\" "
            f"meaning \"{translation}\"."
            + (f" Preferred context: {context}." if context else "")
            + " Write one natural, everyday example sentence using the "
            "term exactly as given, at beginner to intermediate level, "
            "plus its translation. Reply with JSON: {\"example\": "
            "\"<sentence in the target language>\", "
            "\"example_translation\": \"<its translation>\", \"note\": "
            "\"<one short usage note, or empty string>\"}"
        )
        reply = _tutor_chat(client, prompt)
        try:
            parsed = _parse_json_object(reply)
            result = {
                "example": str(parsed.get("example", "")).strip(),
                "example_translation": str(
                    parsed.get("example_translation", "")
                ).strip(),
                "note": str(parsed.get("note", "")).strip(),
            }
            if not result["example"]:
                raise ValueError("empty example")
        except ValueError:
            result = {"example": reply, "example_translation": "", "note": ""}
        return json.dumps({
            "term": term, "translation": translation,
            "language": language, "via": "otari",
            "model": client.model, **result,
        })
    except Exception as exc:
        return _err(f"Otari tutor could not write an example: {exc}")


def lingua_mnemonic(args: dict, **kwargs) -> str:
    """Generate a memory hook for a card, via Otari."""
    args = args or {}
    client, error = _tutor_client_or_error()
    if error:
        return error
    try:
        term, translation, language = _card_fields(args)
        prompt = (
            f"Language being learned: {language}. Word/phrase: \"{term}\" "
            f"meaning \"{translation}\". Invent one vivid, short mnemonic "
            "that links the sound or shape of the term to its meaning for "
            "an English speaker. Keep it under 40 words, concrete, and a "
            "little playful. Reply with JSON: {\"mnemonic\": \"<the "
            "hook>\", \"why_it_works\": \"<one short sentence, or empty>\"}"
        )
        reply = _tutor_chat(client, prompt)
        try:
            parsed = _parse_json_object(reply)
            result = {
                "mnemonic": str(parsed.get("mnemonic", "")).strip(),
                "why_it_works": str(parsed.get("why_it_works", "")).strip(),
            }
            if not result["mnemonic"]:
                raise ValueError("empty mnemonic")
        except ValueError:
            result = {"mnemonic": reply, "why_it_works": ""}
        return json.dumps({
            "term": term, "translation": translation,
            "language": language, "via": "otari", "model": client.model,
            **result,
        })
    except Exception as exc:
        return _err(f"Otari tutor could not write a mnemonic: {exc}")


_VALID_GRADES = ("again", "hard", "good", "easy")
_VALID_VERDICTS = ("correct", "close", "wrong")


def lingua_check(args: dict, **kwargs) -> str:
    """Semantically grade a learner's free-text answer, via Otari.

    Returns a verdict and a suggested SM-2 grade; it deliberately does
    NOT record the grade, so the agent can confirm with the learner and
    then call lingua_grade. Exact string matching cannot judge answers
    like 'hi there' for 'hello'; a model behind Otari can.
    """
    args = args or {}
    client, error = _tutor_client_or_error()
    if error:
        return error
    try:
        term, translation, language = _card_fields(args)
        answer = (args.get("answer") or "").strip()
        if not answer:
            return _err("Provide the learner's answer to check.")
        direction = (args.get("direction") or "term_to_translation").strip()
        prompt = (
            f"Language being learned: {language}. Card: \"{term}\" means "
            f"\"{translation}\". Quiz direction: {direction}. The learner "
            f"answered: \"{answer}\". Judge meaning, not exact wording: "
            "accept synonyms and minor typos, reject wrong meaning. "
            "Suggest an SM-2 grade: again (wrong or blank), hard "
            "(correct but shaky or partly right), good (correct, normal "
            "effort), easy (exactly right and complete). Reply with "
            "JSON: {\"verdict\": \"correct|close|wrong\", "
            "\"suggested_grade\": \"again|hard|good|easy\", \"feedback\": "
            "\"<one short sentence to the learner>\", \"correct_answer\": "
            "\"<the expected answer>\"}"
        )
        reply = _tutor_chat(client, prompt)
        try:
            parsed = _parse_json_object(reply)
            verdict = str(parsed.get("verdict", "")).strip().lower()
            grade = str(parsed.get("suggested_grade", "")).strip().lower()
            if verdict not in _VALID_VERDICTS or grade not in _VALID_GRADES:
                raise ValueError("model reply had no valid verdict/grade")
            result = {
                "verdict": verdict,
                "suggested_grade": grade,
                "feedback": str(parsed.get("feedback", "")).strip(),
                "correct_answer": str(
                    parsed.get("correct_answer", "") or translation
                ).strip(),
            }
        except ValueError:
            result = {
                "verdict": "unknown",
                "suggested_grade": None,
                "feedback": reply,
                "correct_answer": translation,
                "parse_warning": (
                    "The tutor reply was not structured; judge the answer "
                    "yourself and grade with lingua_grade."
                ),
            }
        return json.dumps({
            "term": term, "translation": translation,
            "language": language, "answer": answer, "via": "otari",
            "model": client.model, **result,
        })
    except Exception as exc:
        return _err(f"Otari tutor could not check the answer: {exc}")
