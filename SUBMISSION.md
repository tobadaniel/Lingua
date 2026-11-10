# DoraHacks submission pack — Mozilla Otari: Devs Wilding Online

Paste-ready; all fields filled.

## Project name

Lingua — a language-learning trainer for Hermes Agent, finished with
an Otari tutor layer

## Email (Otari signup email)

officialtobadaniel@gmail.com (signed up at Otari.ai via GitHub account tobadaniel)

## One-line description

Lingua turns Hermes Agent into a spaced-repetition language tutor,
and its new tutor layer routes example sentences, mnemonics, and
semantic answer grading through Mozilla's Otari gateway.

## Public GitHub repository

https://github.com/tobadaniel/lingua (branch `otari-hackathon`)

## Hackathon branch

`otari-hackathon`

## First commit where Otari came in

Commit `47b435924a4a86c522b26c25e3254fae1f43e5fa` —
https://github.com/tobadaniel/lingua/commit/47b435924a4a86c522b26c25e3254fae1f43e5fa
"Add Otari gateway client (first Otari integration)"
(adds `otari_client.py`, the stdlib OpenAI-compatible client pointed
at `https://api.otari.ai/api/v1`, plus the `otari_*` plugin settings
in `plugin.yaml`). It is the first commit on `otari-hackathon` after
the Lingua 1.0.0 base commit `c9760302432469642766ea4dc3bab956a738bb4b`
(the GitHub snapshot of Lingua 1.0.0).

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

Also live-verified on 2026-11-10: the workspace key `lingua-otari`
was created with a **$5/month budget cap** (budgets feature, applied
at key level). Model scoping was attempted ("Only selected":
gpt-oss-20b + mistral-small-3) but the server rejected the
picker-offered mistralai id as an unknown provider — see FEEDBACK.md;
the key therefore inherits all models. Usage/activity tracking is
still TODO-VERIFY: promote it here only if the demo recording shows
the live calls in the Usage view.

## PRs or issues opened on the Otari repo

Filed: https://github.com/mozilla-ai/otari/issues/3069 — key
creation rejects the picker-offered model id
`mistralai/mistral-small-3` as "unknown provider or instance
'mistralai'" (found live on 2026-11-10; draft kept in
`OTARI_ISSUE.md`). The Otari repo was also starred, as the hackathon
asks.

## Demo video (3–5 minutes)

https://lingua-otari-demo.netlify.app/ (direct file:
https://lingua-otari-demo.netlify.app/demo.mp4) — 2:55, recorded
from `DEMO_SCRIPT.md` in this repo: offline core, graceful no-key
behaviour, tutor calls, budget-capped key, model switch by config.

One honest note: the gateway responses in the video are simulated
with the plugin's own test transport and are labelled as such on
screen. The workspace key is real and verified (it authenticates
against the live gateway), but the organisation wallet holds $0.00 —
the advertised $20 first-200 sign-up credit never landed and no
claim route exists — so live calls return 402 Insufficient funds.
That finding, with the exact gateway response, is documented in
FEEDBACK.md. The integration code path is identical either way: the
demo driver runs the same client and tools against the live gateway
when a funded key is present.

## Feedback

Written feedback: `FEEDBACK.md` in this repo answers the three
DoraHacks questions (temptation to bypass Otari; what we built that
Otari should have done; whether we would keep using Otari), plus
live-verified findings from a real workspace key: the model-picker
scoping bug (issue #3069) and the zero-balance 402 wall.
