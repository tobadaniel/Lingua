"""Standalone tests for the Lingua plugin.

Run with plain Python, no Hermes install required:

    python3 tests/test_lingua.py

The plugin directory is loaded as a package under a synthetic name so
the relative imports in __init__.py and tools.py resolve exactly as
they do when Hermes loads the plugin.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
PKG = "lingua_under_test"
DAY = 86400.0


def load_plugin():
    spec = importlib.util.spec_from_file_location(
        PKG,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = module
    spec.loader.exec_module(module)
    return module


class FakeCtx:
    def __init__(self):
        self.tools = {}
        self.hooks = {}
        self.commands = {}
        self.skills = {}

    def get_config(self, key, default=None):
        return default

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = handler

    def register_hook(self, name, callback, **kwargs):
        self.hooks[name] = callback

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands[name] = handler

    def register_skill(self, name, path):
        self.skills[name] = path


class LinguaTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["HERMES_LINGUA_HOME"] = self.tmp.name
        self.plugin = load_plugin()
        self.plugin.tools.reset_store()
        self.ctx = FakeCtx()
        self.plugin.register(self.ctx)
        self.store = self.plugin.tools.get_store()

    def tearDown(self):
        self.plugin.tools.reset_store()
        os.environ.pop("HERMES_LINGUA_HOME", None)
        self.tmp.cleanup()

    def call(self, name, args):
        return json.loads(self.ctx.tools[name](args))


class TestRegistration(LinguaTestCase):
    def test_registers_everything(self):
        self.assertEqual(
            sorted(self.ctx.tools),
            ["lingua_add", "lingua_due", "lingua_grade", "lingua_list",
             "lingua_remove", "lingua_stats"],
        )
        self.assertIn("pre_llm_call", self.ctx.hooks)
        self.assertIn("lingua", self.ctx.commands)
        self.assertIn("lingua-learning", self.ctx.skills)


class TestScheduling(LinguaTestCase):
    T0 = 1_700_000_000.0

    def test_sm2_progression(self):
        import time

        t0 = time.time()  # add() stamps real time; anchor the schedule to it
        card = self.store.add("bonjour", "hello", "french")
        cid = card["id"]
        # New cards are due immediately.
        self.assertEqual(len(self.store.due(now=t0 + 1)), 1)

        graded = self.store.grade(cid, "good", now=t0)
        self.assertEqual(graded["next_interval_days"], 1)
        self.assertEqual(graded["repetitions"], 1)
        self.assertEqual(self.store.due(now=t0 + 3600), [])

        graded = self.store.grade(cid, "good", now=t0 + DAY)
        self.assertEqual(graded["next_interval_days"], 6)
        self.assertEqual(graded["repetitions"], 2)

        graded = self.store.grade(cid, "good", now=t0 + 7 * DAY)
        self.assertEqual(graded["next_interval_days"], 15)  # 6 * 2.5 ease
        self.assertEqual(graded["repetitions"], 3)

    def test_failed_card_returns_in_minutes(self):
        card = self.store.add("hola", "hello", "spanish")
        graded = self.store.grade(card["id"], "again", now=self.T0)
        self.assertEqual(graded["repetitions"], 0)
        self.assertEqual(graded["lapses"], 1)
        due = self.store.due(now=self.T0 + 601)
        self.assertEqual([c["id"] for c in due], [card["id"]])

    def test_ease_adjusts_with_grade(self):
        easy = self.store.add("oui", "yes", "french")
        graded = self.store.grade(easy["id"], "easy", now=self.T0)
        self.assertAlmostEqual(graded["ease"], 2.6, places=2)

        hard = self.store.add("no", "no", "spanish")
        graded = self.store.grade(hard["id"], "hard", now=self.T0)
        self.assertAlmostEqual(graded["ease"], 2.36, places=2)

    def test_unknown_grade_rejected(self):
        card = self.store.add("merci", "thanks", "french")
        with self.assertRaises(ValueError):
            self.store.grade(card["id"], "perfect", now=self.T0)


class TestTools(LinguaTestCase):
    def test_add_due_grade_flow(self):
        added = self.call("lingua_add", {
            "term": "le pain", "translation": "bread", "language": "french",
        })
        cid = added["added"]["id"]
        due = self.call("lingua_due", {})
        self.assertEqual(due["due_now_total"], 1)
        graded = self.call("lingua_grade", {"id": cid, "grade": "good"})
        self.assertEqual(graded["graded"]["next_interval_days"], 1)
        stats = self.call("lingua_stats", {})
        self.assertEqual(stats["total_cards"], 1)
        self.assertEqual(stats["total_reviews"], 1)
        self.assertEqual(stats["due_now"], 0)

    def test_duplicate_add_updates(self):
        self.call("lingua_add", {"term": "hola", "translation": "hi", "language": "spanish"})
        second = self.call("lingua_add", {"term": "Hola", "translation": "hello", "language": "spanish"})
        self.assertTrue(second["added"]["duplicate"])
        self.assertEqual(second["added"]["translation"], "hello")
        self.assertEqual(self.call("lingua_stats", {})["total_cards"], 1)

    def test_remove_and_errors(self):
        added = self.call("lingua_add", {"term": "adiós", "translation": "bye", "language": "spanish"})
        removed = self.call("lingua_remove", {"id": added["added"]["id"]})
        self.assertIn("removed", removed)
        self.assertIn("error", self.call("lingua_remove", {"id": 4242}))
        self.assertIn("error", self.call("lingua_add", {"term": "", "translation": "x", "language": "french"}))
        self.assertIn("error", self.call("lingua_grade", {"id": 1, "grade": "meh"}))


class TestHook(LinguaTestCase):
    def test_first_turn_nudge_when_cards_due(self):
        self.call("lingua_add", {"term": "bonjour", "translation": "hello", "language": "french"})
        hook = self.ctx.hooks["pre_llm_call"]
        result = hook(session_id="s1", user_message="good morning", is_first_turn=True)
        self.assertIsNotNone(result)
        self.assertIn("bonjour", result["context"])

    def test_no_nudge_mid_session_without_intent(self):
        self.call("lingua_add", {"term": "bonjour", "translation": "hello", "language": "french"})
        hook = self.ctx.hooks["pre_llm_call"]
        self.assertIsNone(hook(session_id="s1", user_message="what is the weather", is_first_turn=False))

    def test_intent_message_triggers_nudge(self):
        self.call("lingua_add", {"term": "bonjour", "translation": "hello", "language": "french"})
        hook = self.ctx.hooks["pre_llm_call"]
        result = hook(session_id="s1", user_message="quiz me please", is_first_turn=False)
        self.assertIsNotNone(result)


class TestSlashCommand(LinguaTestCase):
    def test_command_flow_and_seed(self):
        cmd = self.ctx.commands["lingua"]
        out = cmd("seed french")
        self.assertIn("20 new french cards", out)
        stats = self.call("lingua_stats", {})
        self.assertEqual(stats["total_cards"], 20)
        self.assertEqual(stats["by_language"], {"french": 20})
        out = cmd("seed french")
        self.assertIn("0 new french cards", out)
        out = cmd("add spanish | gracias | thank you")
        self.assertIn("Added card", out)
        out = cmd("due")
        self.assertIn("due", out)
        out = cmd("stats")
        self.assertIn("21 cards", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
