# Demo script — Lingua + Otari (target 4 minutes, hard cap 5)

Recording notes: one terminal with Hermes (or the standalone test
harness) and one browser tab on the Otari workspace (Usage/Activity
and Models tabs open, signed in). Have `OTARI_API_KEY` **unset** at
the start; you set it on camera in Act 3. Cards used: the French
starter deck plus `le pain` = bread.

## 0:00–0:35 — The problem (talking head / title card)

"Lingua is a language-learning plugin for Hermes Agent. It does real
spaced repetition, SM-2, the Anki algorithm, entirely offline: decks
in local SQLite, quizzes in chat, no account, no API key. That was
version 1.0, and it had one honest limitation: it could schedule a
word perfectly and still grade your answer like a string match. Real
learning needs a tutor's judgement. This hackathon is where Lingua
got one, through Mozilla's Otari gateway."

## 0:35–1:20 — The offline core, quickly (terminal)

- `/lingua seed french` → 20 cards loaded.
- `/lingua stats` → deck, due counts.
- Ask for a quiz; answer one card exactly right, one card with a
  paraphrase the offline flow cannot judge ("hi there" style).
- "That second answer is the gap. Watch what changes when the tutor
  layer is on."

## 1:20–1:50 — What Otari is, in one breath (browser, otari.ai)

- Show the workspace: API Keys tab (the `otk_` token, scoped,
  revocable), Models tab (many providers, one endpoint).
- "One OpenAI-compatible endpoint, one workspace key, every model.
  Lingua's entire integration is one stdlib module and three tools.
  The first commit on the `otari-hackathon` branch is the gateway
  client; everything tutor-shaped comes after it."

## 1:50–3:20 — The tutor layer, live (terminal)

1. First, with the key still unset, call `lingua_example` for
   `le pain`: it declines with the exact setup instructions, and a
   normal quiz still works. "Offline core intact; no key, no crash."
2. `export OTARI_API_KEY=otk_...` (key off-screen / pre-pasted),
   restart, same call: a fresh example sentence appears, in context
   if you ask ("at a bakery"), with translation and a usage note.
3. Quiz again; give the paraphrase answer. `lingua_check` returns
   verdict **correct/close**, one line of feedback, and a suggested
   SM-2 grade; the agent confirms and records it with `lingua_grade`.
   "Meaning, not string match, and the human still approves the grade."
4. Grade a card `again` twice, then `lingua_mnemonic`: a vivid hook
   for the stubborn word.

## 3:20–4:05 — The gateway view (browser, Otari Usage/Activity)

- Refresh Usage: the three tutor calls are listed with model, tokens,
  and cost.
- Point at the budget/key settings: "A personal agent calls tools in
  loops. A scoped key with a spend ceiling, and a record of every
  call, is the difference between a feature and a liability."
- Switch `OTARI_MODEL` to a different provider's model, rerun one
  tutor call, show it working unchanged. "Model choice is config,
  not code. That is the gateway earning its place."

## 4:05–4:30 — Close

"So: Lingua 1.1. Same offline spaced-repetition core, now with a
tutor that judges meaning, invents examples and mnemonics, and runs
entirely through Otari: one key, any model, every call accounted.
Repo, branch `otari-hackathon`, first Otari commit and full written
feedback are linked in the submission. Thank you."

## Fallbacks if live recording fights back

- No network on recording day: run the same script against the fake
  transport used by the test suite and **say so on camera**; the tool
  outputs are identical in shape.
- A model call is slow: cut on the request, not the response; the
  three tutor beats can each stand alone if one must be trimmed to
  stay under 5 minutes.
