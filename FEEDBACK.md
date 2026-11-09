# Feedback on building with Otari — Lingua tutor layer

Written feedback for the Mozilla Otari "Devs Wilding Online"
hackathon, answering the three DoraHacks questions. Everything marked
**TODO-VERIFY** is a claim about the live hosted service that still
needs a real workspace key to confirm; the rest is from integrating
against the documented API and the public docs.

## What was built

Lingua is a language-learning plugin for Hermes Agent (SM-2 spaced
repetition, local SQLite, zero dependencies). Version 1.0 deliberately
had no LLM. For this hackathon, on branch `otari-hackathon`, it gained
an optional tutor layer routed entirely through the hosted Otari
gateway: `lingua_example` (contextual example sentences),
`lingua_mnemonic` (memory hooks), and `lingua_check` (semantic grading
of free-text answers with a suggested SM-2 grade). The client is one
stdlib-only module (`otari_client.py`) speaking the OpenAI-compatible
`POST /api/v1/chat/completions` endpoint with an `otk_` workspace key.

## 1. When were you most tempted to skip Otari and call the provider directly? What happened?

Twice, both early.

First, at the model-name step. A direct provider integration has one
obvious default model; Otari makes you pick a `provider/model` id from
a catalog, and the quickstart's example
(`deepseek/deepseek-v4-pro-0813`) is not obviously "the cheap sensible
default" a plugin should ship. The temptation was to hardcode a
familiar provider model and move on. What stopped it: the whole point
of the tutor layer is that the learner, not the plugin, owns the
model choice, so the client ships the quickstart model only as a
fallback and exposes `OTARI_MODEL` / an `otari_model` setting. That is
arguably the right design, but the docs could say plainly which
open-weight models are good cheap defaults for small chat calls.

Second, when writing error handling. A direct SDK gives typed errors;
through the gateway I had to map raw HTTP statuses myself, including
discovering from the docs (not from an error I could reproduce without
a key) that an EU-region key gets a 421 Misdirected Request naming the
EU host. I implemented the mapping (401/403 key problems, 421 EU hint,
429 rate-limit/budget, 404 model unavailable), but every one of those
mappings is currently covered only by tests with a fake transport:
**TODO-VERIFY** each against the live gateway, especially that the
421 response really is returned for a non-EU host call and that a 429
is what a spent budget produces, rather than a distinct status.

What never tempted me: the request shape itself. Because the endpoint
is OpenAI-compatible, the integration was a base-URL change from what
I would have written for a direct provider, plus the workspace token.
That part worked exactly as advertised.

## 2. What did you end up building yourself that Otari should've done for you?

- **Structured-output discipline.** The tutor tools need JSON back (a
  verdict, a grade, an example split from its translation). I built
  prompt-level "reply with a single JSON object only" instructions
  plus a defensive parser (strip code fences, extract the first
  object, validate enums, fall back to returning the raw text with a
  parse warning). A gateway-level structured-output or JSON-mode
  guarantee that survives model switching would remove most of that:
  the parser exists precisely because behaviour varies by the model
  behind the gateway.
- **Status-to-action error mapping.** As above: a small piece of
  client code (and these feedback notes) is devoted to turning HTTP
  statuses into "check your key / your key is EU / your budget is
  spent / that model is not in your workspace". Machine-readable error
  codes with a documented remediation field would make this a lookup
  instead of folklore.
- **A fake gateway for tests.** To keep Lingua's zero-dependency,
  runs-anywhere test suite meaningful, I built a fake transport and
  canned responses rather than testing against the real service. A
  lightweight official mock/sandbox endpoint (or a documented
  recorded-response fixture) would let every hackathon project test
  against realistic gateway behaviour, including the 421 and budget
  cases, without spending tokens. **TODO-VERIFY**: check whether the
  self-hosted Otari image is light enough to serve as that test
  double in CI; if it is, this complaint shrinks to a docs request.

Nothing else needed building around the gateway: auth, routing, and
usage recording are exactly the parts I did *not* have to write, and
did not.

## 3. If the rules hadn't required Otari, would you have continued using Otari? Why or why not?

Yes, for this project, with one reservation.

The honest counterfactual: without the hackathon I would probably
have written Lingua's tutor layer directly against one provider,
because that is the path of least resistance for a solo plugin, and
Lingua would then have shipped with that provider's key handling,
model names, and failure modes baked in. Having been pushed through
the gateway, the plugin is better for it in ways that persist after
the deadline: the API key in play is a scoped, revocable workspace
token rather than a raw provider credential; learners can point the
same build at a cheap open-weight model today and a stronger model
later by changing one string; and the usage view gives a budget
ceiling over an agent that calls tools autonomously, which is a real
safety property for a plugin that runs inside a personal agent, not a
nice-to-have.

The reservation is operational, not architectural: the tutor layer's
value depends on hosted-gateway behaviour I could not fully exercise
without spending from a real workspace (error shapes, budget
enforcement, activity-view fidelity). **TODO-VERIFY** after a live
session: (1) a tutor call appears in the Usage/Activity view with the
right model and token counts; (2) a deliberately tiny budget actually
stops a call, and with what status; (3) switching `OTARI_MODEL` to a
second provider's model works with no code change. If those three
hold, there is no reason for Lingua to grow a direct provider path,
and the Otari layer stays the only network code in the plugin.
