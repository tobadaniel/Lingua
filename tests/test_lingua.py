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
            ["lingua_add", "lingua_check", "lingua_due", "lingua_example",
             "lingua_grade", "lingua_list", "lingua_mnemonic",
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


class FakeTransport:
    """Records requests and answers from the prompt keyword it sees."""

    def __init__(self, responder=None, status=200, raw_content=None):
        self.requests = []
        self.responder = responder
        self.status = status
        self.raw_content = raw_content

    def __call__(self, url, headers, payload, timeout):
        self.requests.append({
            "url": url, "headers": headers,
            "payload": json.loads(payload), "timeout": timeout,
        })
        if self.status >= 400:
            body = {"error": {"message": "fake failure"}}
            return self.status, {}, json.dumps(body).encode()
        if self.raw_content is not None:
            content = self.raw_content
        else:
            content = self.responder(self.requests[-1]["payload"])
        body = {
            "model": self.requests[-1]["payload"]["model"],
            "usage": {"total_tokens": 42},
            "choices": [{"message": {"content": content}}],
        }
        return 200, {}, json.dumps(body).encode()


def tutor_responder(payload):
    user = payload["messages"][-1]["content"]
    if "example sentence" in user:
        return json.dumps({
            "example": "Je mange du pain frais.",
            "example_translation": "I eat fresh bread.",
            "note": "pain is masculine: le pain.",
        })
    if "mnemonic" in user:
        return json.dumps({
            "mnemonic": "Picture a loaf shouting in pain: le pain.",
            "why_it_works": "pain sounds like the English word pain.",
        })
    if "Judge meaning" in user:
        return json.dumps({
            "verdict": "correct", "suggested_grade": "good",
            "feedback": "Exactly right.", "correct_answer": "bread",
        })
    raise AssertionError(f"unexpected prompt: {user[:60]}")


class TestOtariClient(LinguaTestCase):
    def setUp(self):
        super().setUp()
        os.environ.pop("OTARI_API_KEY", None)
        self.oc = self.plugin.tools.otari_client

    def test_request_shape_and_parsing(self):
        fake = FakeTransport(responder=lambda payload: "  Bonjour.  ")
        client = self.oc.OtariClient(api_key="otk_test123", transport=fake)
        result = client.chat([{"role": "user", "content": "say hi"}])
        self.assertEqual(result["content"], "Bonjour.")
        self.assertEqual(result["usage"], {"total_tokens": 42})
        request = fake.requests[0]
        self.assertEqual(
            request["url"], "https://api.otari.ai/api/v1/chat/completions")
        self.assertEqual(
            request["headers"]["Authorization"], "Bearer otk_test123")
        self.assertEqual(
            request["payload"]["model"], "openai/gpt-oss-20b")
        self.assertEqual(
            request["payload"]["messages"],
            [{"role": "user", "content": "say hi"}])

    def test_missing_key_raises_without_network(self):
        def forbidden(*args):
            raise AssertionError("transport must not be called")

        client = self.oc.OtariClient(api_key="", transport=forbidden)
        self.assertFalse(client.configured)
        with self.assertRaises(self.oc.OtariNotConfigured):
            client.chat_text([{"role": "user", "content": "hi"}])

    def test_error_status_mapping(self):
        cases = [
            (401, "rejected the API key"),
            (421, "eu.api.otari.ai/api/v1"),
            (429, "budget"),
            (404, "OTARI_MODEL"),
        ]
        for status, needle in cases:
            fake = FakeTransport(status=status)
            client = self.oc.OtariClient(api_key="otk_x", transport=fake)
            with self.assertRaises(self.oc.OtariError) as caught:
                client.chat_text([{"role": "user", "content": "hi"}])
            self.assertEqual(caught.exception.status, status)
            self.assertIn(needle, str(caught.exception))


class TestTutorTools(LinguaTestCase):
    CARD = {"term": "le pain", "translation": "bread", "language": "french"}

    def setUp(self):
        super().setUp()
        os.environ.pop("OTARI_API_KEY", None)
        self.tools = self.plugin.tools
        self.oc = self.tools.otari_client
        self.tools.configure_otari(enabled=True)
        self.tools.reset_otari_client()

    def tearDown(self):
        self.tools.configure_otari(enabled=True)
        self.tools.reset_otari_client()
        super().tearDown()

    def inject_fake(self, responder=tutor_responder, **kwargs):
        fake = FakeTransport(responder=responder, **kwargs)
        self.tools.set_otari_client(
            self.oc.OtariClient(api_key="otk_fake", transport=fake))
        return fake

    def test_missing_key_is_graceful_and_offline_still_works(self):
        for name, args in [
            ("lingua_example", self.CARD),
            ("lingua_mnemonic", self.CARD),
            ("lingua_check", {**self.CARD, "answer": "bread"}),
        ]:
            result = self.call(name, args)
            self.assertIn("error", result, name)
            self.assertEqual(result["otari_configured"], False, name)
            self.assertIn("OTARI_API_KEY", result["error"], name)
        added = self.call("lingua_add", self.CARD)
        self.assertIn("added", added)

    def test_disabled_tutor_is_graceful(self):
        self.tools.configure_otari(enabled=False)
        result = self.call("lingua_example", self.CARD)
        self.assertIn("disabled", result["error"])

    def test_example_tool(self):
        fake = self.inject_fake()
        result = self.call("lingua_example", self.CARD)
        self.assertEqual(result["example"], "Je mange du pain frais.")
        self.assertEqual(
            result["example_translation"], "I eat fresh bread.")
        self.assertEqual(result["via"], "otari")
        prompt = fake.requests[0]["payload"]["messages"][-1]["content"]
        self.assertIn("le pain", prompt)

    def test_mnemonic_tool(self):
        self.inject_fake()
        result = self.call("lingua_mnemonic", self.CARD)
        self.assertIn("pain", result["mnemonic"])
        self.assertEqual(result["via"], "otari")

    def test_check_tool_suggests_grade_without_recording(self):
        self.inject_fake()
        result = self.call(
            "lingua_check", {**self.CARD, "answer": "bread"})
        self.assertEqual(result["verdict"], "correct")
        self.assertEqual(result["suggested_grade"], "good")
        self.assertIn("added", self.call("lingua_add", self.CARD))
        stats = self.call("lingua_stats", {})
        self.assertEqual(stats["total_reviews"], 0)

    def test_check_tool_by_card_id(self):
        added = self.call("lingua_add", self.CARD)
        self.inject_fake()
        result = self.call(
            "lingua_check",
            {"id": added["added"]["id"], "answer": "bread"})
        self.assertEqual(result["term"], "le pain")
        self.assertEqual(result["verdict"], "correct")

    def test_check_tool_unstructured_reply_falls_back(self):
        self.inject_fake(raw_content="Looks right to me, well done.")
        result = self.call(
            "lingua_check", {**self.CARD, "answer": "bread"})
        self.assertEqual(result["verdict"], "unknown")
        self.assertIsNone(result["suggested_grade"])
        self.assertIn("parse_warning", result)

    def test_tutor_rejects_incomplete_card_ref(self):
        self.inject_fake()
        result = self.call("lingua_example", {"term": "solo"})
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
