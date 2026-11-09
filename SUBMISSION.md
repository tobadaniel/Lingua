# DoraHacks submission pack — Mozilla Otari: Devs Wilding Online

Paste-ready. Replace the two bracketed items before submitting.

## Project name

Lingua — a language-learning trainer for Hermes Agent, finished with
an Otari tutor layer

## Email (Otari signup email)

[TODO: the email used to sign up at otari.ai]

## One-line description

Lingua turns Hermes Agent into a spaced-repetition language tutor,
and its new tutor layer routes example sentences, mnemonics, and
semantic answer grading through Mozilla's Otari gateway.

## Public GitHub repository

[TODO: public repo URL for this project, e.g.
https://github.com/tobadaniel/lingua — must serve branch
`otari-hackathon`]

## Hackathon branch

`otari-hackathon`

## First commit where Otari came in

Commit `b239664a4fa632b330ac3345c8686d7efae616f9` —
"Add Otari gateway client (first Otari integration)"
(adds `otari_client.py`, the stdlib OpenAI-compatible client pointed
at `https://api.otari.ai/api/v1`, plus the `otari_*` plugin settings
in `plugin.yaml`). It is the first commit on `otari-hackathon` after
the Lingua 1.0.0 base commit `e634e1e`.

## What was built with Otari

Lingua 1.0 (the side project being finished) is an offline Hermes
plugin: SM-2 spaced repetition over local SQLite, six tools, a
due-review hook, starter decks, zero dependencies. This hackathon
added, on the branch above:

- `otari_client.py` — a pure-stdlib (urllib) client for the hosted
  Otari gateway, with friendly, specific errors (bad key, EU-region
  421 redirect, rate-limit/budget 429, unknown model 404).
- `lingua_example` — contextual example sentence + translation +
  usage note for any card.
- `lingua_mnemonic` — a vivid mnemonic hook for hard-to-keep cards.
- `lingua_check` — semantic grading of free-text answers (verdict,
  feedback, suggested SM-2 grade; never records the grade itself).
- Graceful degradation throughout: with no `OTARI_API_KEY`, the tutor
  tools explain how to enable them and the offline plugin is
  untouched. 23 automated tests (11 new) cover the client and tools
  against a fake gateway transport.

## Otari features used

Only features the code in this repo actually exercises:

- **Hosted Otari gateway (otari.ai)** — all LLM traffic goes to the
  hosted endpoint; no provider is called directly.
- **OpenAI-compatible chat completions** — `POST /api/v1/chat/completions`
  with standard OpenAI request/response shapes.
- **Multi-provider model IDs / open-weight models** — models are
  addressed in `provider/model` form (default
  `openai/gpt-oss-20b`) and are switchable purely by
  config (`OTARI_MODEL` / `otari_model`) with zero code change.
- **Workspace API key scoping** — the integration uses a single
  workspace token (`otk_...`) read from the environment, never a
  provider credential and never stored by the plugin.

Not claimed (configured in the dashboard during the demo, but not
exercised by the code, so not listed as used): budgets and the
usage/activity tracking views. TODO-VERIFY before submitting: if the
demo recording does exercise a budget stop and the activity view with
the real key, move those two items into the list above with a line
each on what was done.

## PRs or issues opened on the Otari repo

None yet. TODO: if a genuine issue is filed while verifying the live
error behaviour (see FEEDBACK.md), link it here; do not file a
placeholder issue just to fill this field.

## Demo video (3–5 minutes)

[TODO: video link] — recorded from `DEMO_SCRIPT.md` in this repo:
offline core, graceful no-key behaviour, live tutor calls, Otari
usage view, model switch by config.

## Feedback

Written feedback: `FEEDBACK.md` in this repo answers the three
DoraHacks questions (temptation to bypass Otari; what we built that
Otari should have done; whether we would keep using Otari), with
live-service claims marked TODO-VERIFY until checked with a real
workspace key.
