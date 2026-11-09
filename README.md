# Lingua: a language learning trainer for Hermes Agent

Plenty of plugins give the agent a memory. Lingua gives **you** one.

Hermes quizzes you in chat, grades your recall honestly, and uses SM-2
spaced repetition (the algorithm behind Anki) to bring each word back
right before you would forget it. Your decks live in a local SQLite
database. The core needs no API key, no Anki install, and no external
service; practice happens inside the conversations you already have
with your agent, because that is where learning actually sticks. An
optional tutor layer (below) adds an LLM through Mozilla AI's Otari
gateway when you choose to configure it.

## What it does

- **Vocabulary decks, one per language.** French, Spanish, Yoruba,
  whatever you are learning. Add words as you meet them, with example
  sentences.
- **Real spaced repetition.** Grades of again, hard, good, and easy
  drive the classic SM-2 schedule: a good card returns in 1 day, then 6,
  then stretches by its ease factor. A failed card comes back in about
  10 minutes, not tomorrow.
- **Quizzes in chat.** Ask Hermes to test you and it deals due cards one
  at a time, waits for your answer, checks it, and records the grade.
- **A nudge when reviews are due.** A `pre_llm_call` hook notices due
  cards at the start of a session (or when you mention practice) and
  offers a short review, so decks never silently rot.
- **Starter decks.** French and Spanish essentials, 20 cards each,
  loadable with one command so the first session takes ten seconds.
- **Progress you can see.** Cards per deck, due now, mastered count
  (interval of 21+ days), total reviews, and active days this week.

## Otari tutor layer (new in 1.1.0)

Lingua 1.0 deliberately had no LLM: decks, scheduling, and grading by
exact judgement all worked offline. What it could not do was judge a
*free-text* answer the way a person would ("hi there" for "hello"),
invent a fresh example sentence in a context you care about, or come
up with a mnemonic for the word you keep missing. That is the finish
this release adds, routed through [Otari](https://otari.ai), Mozilla
AI's open-source, OpenAI-compatible LLM gateway, instead of a direct
provider integration:

- **`lingua_example`** writes one contextual example sentence for a
  card, with its translation and a short usage note. Ask for a context
  ("at a bakery") and the sentence follows it.
- **`lingua_mnemonic`** invents a vivid memory hook linking the term's
  sound or shape to its meaning, for cards that keep coming back
  `again`.
- **`lingua_check`** semantically grades a free-text answer: verdict
  (correct, close, wrong), one line of feedback, and a suggested SM-2
  grade. It never records the grade itself; the agent confirms and
  calls `lingua_grade`, so the human stays in the loop.

Why a gateway rather than a provider SDK: one OpenAI-compatible
endpoint and one workspace key (`otk_...`) can serve any model Otari
routes to, so switching models (or providers) is a config change, not
a code change; the workspace key is scoped and revocable, separate
from any provider credential; and every tutor call shows up in Otari's
usage/activity view under the workspace budget, which matters when an
agent can call tools in a loop.

### Configure it

1. Create a free account at [otari.ai](https://otari.ai) and create a
   workspace API key (starts with `otk_`).
2. Set the key where Hermes runs. Never put it in plugin settings or
   source control:

   ```bash
   export OTARI_API_KEY=otk_...
   # Optional: pick any model your workspace can use, provider/model form
   export OTARI_MODEL=openai/gpt-oss-20b
   # Optional: EU-region keys use the EU host
   # export OTARI_BASE_URL=https://eu.api.otari.ai/api/v1
   ```

3. Optional plugin settings: `otari_enabled` (default `true`),
   `otari_model`, `otari_base_url` (settings override nothing about
   the key; empty settings fall back to the env vars above).

Without a key, the three tutor tools return a short explanation of how
to enable them and **everything else in Lingua works exactly as
before**. With `otari_enabled: false` they decline cleanly instead.

## Install

```bash
hermes plugins install tobadaniel/lingua
hermes plugins enable lingua
```

Or from the plugin catalog, once listed:

```bash
hermes plugins install lingua
```

## Usage

Talk to Hermes:

- "Teach me the French word for bread, and add it to my deck."
  (`lingua_add`)
- "Quiz me on my Spanish." (`lingua_due`, then `lingua_grade` after
  each answer)
- "How many cards do I have due today?" (`lingua_stats`)

Or drive it yourself with the slash command, in the CLI or any gateway
chat:

```
/lingua seed french
/lingua add spanish | gracias | thank you | Muchas gracias por todo.
/lingua due
/lingua list french
/lingua remove 4
/lingua stats
```

The plugin also bundles a `lingua-learning` skill that teaches the
agent how to run a good session: one card at a time, mixed directions,
honest grades, short sessions, no lectures.

## Tools

| Tool | What it does |
| --- | --- |
| `lingua_add` | Add or update a vocabulary card (term, translation, language, optional example). New cards are due immediately. |
| `lingua_due` | Fetch cards due for review now, optionally for one deck. |
| `lingua_grade` | Record a grade (again, hard, good, easy) and reschedule the card with SM-2. |
| `lingua_list` | List cards, filter by deck or search text. |
| `lingua_remove` | Permanently delete one card by id. |
| `lingua_stats` | Deck sizes, due counts, mastered cards, review totals, active days. |
| `lingua_example` | Otari: fresh contextual example sentence + translation + usage note for a card. |
| `lingua_mnemonic` | Otari: a vivid mnemonic hook for a hard-to-keep card. |
| `lingua_check` | Otari: semantic check of a free-text answer, verdict + suggested SM-2 grade (does not record it). |

## Settings

Under `plugins.entries.lingua.settings` (or the Desktop plugin
settings form):

| Key | Default | Meaning |
| --- | --- | --- |
| `daily_target` | `10` | How many due cards a review session aims for. |
| `nudge_on_first_turn` | `true` | Mention due reviews at the start of a new session. |
| `otari_enabled` | `true` | Enable the Otari tutor tools (they still need `OTARI_API_KEY`). |
| `otari_model` | _(env/default)_ | Otari model id in provider/model form. |
| `otari_base_url` | _(env/default)_ | Otari gateway base URL; EU keys use `https://eu.api.otari.ai/api/v1`. |

## Where your data lives

Decks are stored in Hermes' plugin data directory for the active
profile (`plugin-data/lingua/` under your Hermes home), in a single
SQLite database that survives plugin updates and removal. Delete the
database file and every deck is gone.

## Disclosure

- **Network calls:** the six core tools make none. The three tutor
  tools call only the Otari gateway (`https://api.otari.ai/api/v1` by
  default, or your `OTARI_BASE_URL`), and only when you invoke them
  with `OTARI_API_KEY` set. They send the card being studied (term,
  translation, language) plus, for `lingua_check`, the learner's
  answer. Decks are never uploaded wholesale.
- **Shell commands:** none.
- **Background processes:** none.
- **Credentials:** the tutor layer reads `OTARI_API_KEY` (and optional
  `OTARI_MODEL` / `OTARI_BASE_URL`) from the environment only. The key
  is never stored, logged, or put in the database.
- **Reads outside its own data:** none, beyond the plugin's own bundled
  starter deck file.
- **Telemetry:** none of Lingua's own; tutor requests are visible in
  your own Otari workspace usage/activity view, which is the point.

## Development

The plugin is pure Python standard library (Python 3.11+), so there is
nothing to install and dependency resolution cannot fail.

```bash
# Standalone tests (no Hermes install needed)
python3 tests/test_lingua.py

# The same validation the plugin catalog CI runs
hermes plugins validate /path/to/lingua --install-deps
hermes plugins doctor /path/to/lingua --ci
```

## License

MIT, see [LICENSE](LICENSE).
