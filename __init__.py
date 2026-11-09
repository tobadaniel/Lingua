"""Lingua: a language learning trainer for Hermes Agent.

Vocabulary cards with SM-2 spaced repetition, stored locally. Hermes
quizzes you in chat, grades your recall honestly, and brings each word
back right before you would forget it. A pre_llm_call hook nudges you
when reviews are due, so practice happens inside the conversations you
already have with your agent.

Optional Otari tutor layer: when OTARI_API_KEY is set, three extra
tools route through Mozilla AI's Otari gateway to generate example
sentences and mnemonics and to semantically check free-text answers.
The six core tools stay fully offline either way.
"""

from __future__ import annotations

import logging
from pathlib import Path

try:  # Hermes loads the plugin as a package; tests may load it flat.
    from . import schemas, tools
except ImportError:  # pragma: no cover - flat import fallback
    import schemas
    import tools

logger = logging.getLogger(__name__)

_SETTINGS = {"daily_target": 10, "nudge_on_first_turn": True}

_REVIEW_WORDS = ("quiz", "review", "vocab", "practice", "practise",
                 "revise", "learn", "flashcard", "test me")

_USAGE = (
    "Lingua commands:\n"
    "  /lingua add <language> | <term> | <translation> [| <example>]\n"
    "  /lingua due            cards due for review now\n"
    "  /lingua list [language]  list your cards\n"
    "  /lingua seed <language>  load a starter deck (french, spanish)\n"
    "  /lingua remove <id>    delete a card\n"
    "  /lingua stats          progress and due counts"
)


def _format_card(card: dict) -> str:
    example = f"\n    {card['example']}" if card.get("example") else ""
    return (f"#{card['id']} [{card['language']}] {card['term']} = "
            f"{card['translation']}{example}")


def _due_nudge(session_id, user_message, is_first_turn=False, **kwargs):
    """pre_llm_call hook: surface due reviews at the right moment.

    Fires on the first turn of a session (when the user can act on it)
    or whenever the message sounds like learning intent. Returns a
    {"context": ...} dict or None. Never raises.
    """
    try:
        store = tools.get_store()
        counts = store.due_counts()
        if counts["total"] == 0:
            return None
        message = (user_message or "").lower()
        wants_review = any(word in message for word in _REVIEW_WORDS)
        if not (wants_review or (is_first_turn and _SETTINGS.get("nudge_on_first_turn", True))):
            return None
        limit = int(_SETTINGS.get("daily_target", 10) or 10)
        cards = store.due(limit=limit)
        by_lang = ", ".join(
            f"{lang}: {n}" for lang, n in counts["by_language"].items()
        )
        lines = [
            f"Lingua: the user has {counts['total']} vocabulary card(s) due "
            f"for review ({by_lang}). If they are up for it, run a short "
            f"review session now: quiz one card at a time from lingua_due, "
            f"wait for their answer, then grade honestly with lingua_grade "
            f"(again/hard/good/easy). Due cards, answers included for "
            f"grading only, do not reveal a translation before the user "
            f"attempts the card:"
        ]
        for card in cards:
            lines.append(
                f"- #{card['id']} [{card['language']}] {card['term']} = "
                f"{card['translation']}"
            )
        return {"context": "\n".join(lines)[:4000]}
    except Exception:
        logger.debug("Lingua due-nudge hook failed", exc_info=True)
        return None


def _handle_lingua_command(raw_args: str, **kwargs) -> str:
    """Slash command: /lingua add|due|list|seed|remove|stats."""
    try:
        store = tools.get_store()
        parts = (raw_args or "").strip().split(None, 1)
        if not parts:
            return _USAGE
        action = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if action == "help":
            return _USAGE
        if action == "add":
            fields = [f.strip() for f in rest.split("|")]
            if len(fields) < 3 or not all(fields[:3]):
                return "Usage: /lingua add <language> | <term> | <translation> [| <example>]"
            card = store.add(
                fields[1], fields[2], fields[0],
                example=fields[3] if len(fields) > 3 else "",
            )
            verb = "Updated" if card.get("duplicate") else "Added"
            return f"{verb} card #{card['id']}: {card['term']} = {card['translation']} ({card['language']})"
        if action == "due":
            counts = store.due_counts()
            if counts["total"] == 0:
                return "Nothing due. You are all caught up."
            cards = store.due(limit=int(_SETTINGS.get("daily_target", 10) or 10))
            return (f"{counts['total']} card(s) due:\n"
                    + "\n".join(_format_card(c) for c in cards)
                    + "\nAsk me to quiz you, and I will grade each answer.")
        if action == "list":
            cards = store.list_cards(limit=50, language=rest or None)
            if not cards:
                return "No cards yet. Try: /lingua seed french"
            return "Your cards:\n" + "\n".join(_format_card(c) for c in cards)
        if action == "seed":
            if not rest:
                return "Usage: /lingua seed <language> (french, spanish)"
            result = tools.seed_starter_deck(rest.lower())
            return (f"Starter deck loaded: {result['added']} new "
                    f"{result['language']} cards added, "
                    f"{result['skipped_existing']} already present. "
                    f"They are due now, ask me to quiz you.")
        if action == "remove":
            if not rest.isdigit():
                return "Usage: /lingua remove <id>"
            removed = store.remove(int(rest))
            if removed is None:
                return f"No card with id {rest}."
            return f"Removed card #{removed['id']}: {removed['term']}"
        if action == "stats":
            stats = store.stats()
            decks = ", ".join(
                f"{lang} ({n})" for lang, n in stats["by_language"].items()
            ) or "none"
            return (
                f"Lingua: {stats['total_cards']} cards ({decks}), "
                f"{stats['due_now']} due now, {stats['mastered']} mastered, "
                f"{stats['total_reviews']} reviews done, active "
                f"{stats['active_days_last_7']} of the last 7 days."
            )
        return _USAGE
    except Exception as exc:
        return f"Lingua command failed: {exc}"


def register(ctx):
    """Wire schemas to handlers, register the hook, command, and skill."""
    try:
        _SETTINGS["daily_target"] = int(ctx.get_config("daily_target", default=10) or 10)
        _SETTINGS["nudge_on_first_turn"] = bool(
            ctx.get_config("nudge_on_first_turn", default=True)
        )
        tools.configure_otari(
            enabled=bool(ctx.get_config("otari_enabled", default=True)),
            model=str(ctx.get_config("otari_model", default="") or ""),
            base_url=str(ctx.get_config("otari_base_url", default="") or ""),
        )
    except Exception:
        logger.debug("Lingua: could not read plugin settings", exc_info=True)

    ctx.register_tool(
        name="lingua_add", toolset="lingua",
        schema=schemas.LINGUA_ADD, handler=tools.lingua_add,
    )
    ctx.register_tool(
        name="lingua_due", toolset="lingua",
        schema=schemas.LINGUA_DUE, handler=tools.lingua_due,
    )
    ctx.register_tool(
        name="lingua_grade", toolset="lingua",
        schema=schemas.LINGUA_GRADE, handler=tools.lingua_grade,
    )
    ctx.register_tool(
        name="lingua_list", toolset="lingua",
        schema=schemas.LINGUA_LIST, handler=tools.lingua_list,
    )
    ctx.register_tool(
        name="lingua_remove", toolset="lingua",
        schema=schemas.LINGUA_REMOVE, handler=tools.lingua_remove,
    )
    ctx.register_tool(
        name="lingua_stats", toolset="lingua",
        schema=schemas.LINGUA_STATS, handler=tools.lingua_stats,
    )
    ctx.register_tool(
        name="lingua_example", toolset="lingua",
        schema=schemas.LINGUA_EXAMPLE, handler=tools.lingua_example,
    )
    ctx.register_tool(
        name="lingua_mnemonic", toolset="lingua",
        schema=schemas.LINGUA_MNEMONIC, handler=tools.lingua_mnemonic,
    )
    ctx.register_tool(
        name="lingua_check", toolset="lingua",
        schema=schemas.LINGUA_CHECK, handler=tools.lingua_check,
    )

    ctx.register_hook("pre_llm_call", _due_nudge)

    ctx.register_command(
        "lingua",
        handler=_handle_lingua_command,
        description="Learn vocabulary with spaced repetition: add, review, seed, stats",
        args_hint="[add|due|list|seed <language>|remove <id>|stats]",
    )

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)
