# Lingua: a language learning trainer for Hermes Agent

Plenty of plugins give the agent a memory. Lingua gives **you** one.

Hermes quizzes you in chat, grades your recall honestly, and uses SM-2
spaced repetition (the algorithm behind Anki) to bring each word back
right before you would forget it. Your decks live in a local SQLite
database. No API key, no Anki install, no external service, nothing
leaves your machine. Practice happens inside the conversations you
already have with your agent, because that is where learning actually
sticks.

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

## Settings

Under `plugins.entries.lingua.settings` (or the Desktop plugin
settings form):

| Key | Default | Meaning |
| --- | --- | --- |
| `daily_target` | `10` | How many due cards a review session aims for. |
| `nudge_on_first_turn` | `true` | Mention due reviews at the start of a new session. |

## Where your data lives

Decks are stored in Hermes' plugin data directory for the active
profile (`plugin-data/lingua/` under your Hermes home), in a single
SQLite database that survives plugin updates and removal. Delete the
database file and every deck is gone.

## Disclosure

- **Network calls:** none. Lingua never phones home.
- **Shell commands:** none.
- **Background processes:** none.
- **Credentials:** none read, none needed, none stored.
- **Reads outside its own data:** none, beyond the plugin's own bundled
  starter deck file.
- **Telemetry:** none.

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
