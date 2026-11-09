---
name: lingua-learning
description: How to run Lingua vocabulary review sessions well: quiz one card at a time, grade honestly, mix directions, and keep practice short and encouraging.
---

# Lingua learning workflows

Lingua turns Hermes into a spaced repetition tutor. The plugin owns the
schedule; you own the teaching.

## Running a review session

1. Call `lingua_due` (optionally for one language) to get the session's
   cards.
2. Present ONE card at a time. Default direction: show the term in the
   target language and ask for the meaning. Every few cards, reverse it:
   give the meaning and ask for the term.
3. Wait for the user's answer. Never reveal the translation first.
4. Judge the answer, share the correct meaning and the example sentence,
   then call `lingua_grade` with an honest grade:
   - `again`: wrong, blank, or a lucky guess they disown.
   - `hard`: right, but slow or shaky.
   - `good`: right with normal effort.
   - `easy`: instant and certain.
5. Keep sessions short: the daily target (default 10) is a ceiling, not
   a quota. End with a one line summary: how many reviewed, how many
   again, what is due tomorrow.

## Adding vocabulary

- Add words the user meets in conversation, articles, or their study
  material with `lingua_add`, including an example sentence whenever you
  can write a correct one.
- One deck per language, named in plain lowercase: french, spanish,
  yoruba.
- If the user is starting out, offer a starter deck: `/lingua seed
  french` or `/lingua seed spanish` loads 20 essentials.

## Using the Otari tutor tools

When `OTARI_API_KEY` is configured, three extra tools are available.
If a tutor tool returns an `otari_configured: false` error, do not
retry it in the same session: explain briefly how to enable it and
continue with the offline tools.

- **Free-text answers:** when the user's answer is not obviously right
  or wrong, call `lingua_check` instead of judging by exact wording.
  Show its feedback, then record the grade it suggests with
  `lingua_grade`, adjusting only if the user disputes the verdict.
- **Stuck cards:** if a card has been graded `again` twice, offer a
  `lingua_mnemonic` hook before the next attempt, and read it aloud as
  part of the retry.
- **Examples:** prefer `lingua_example` over inventing a sentence
  yourself when the user asks for a word in context, or when a card
  has no example. Pass the setting the user cares about as `context`.
  If they like the sentence, save it on the card with `lingua_add`
  (same term and translation, example set), which updates in place.

## Tone

Encouraging, brief, no lectures. Celebrate streaks and mastered cards
when `lingua_stats` shows them. A card graded `again` is information,
not failure: it simply comes back sooner, which is the system working.
