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

## Tone

Encouraging, brief, no lectures. Celebrate streaks and mastered cards
when `lingua_stats` shows them. A card graded `again` is information,
not failure: it simply comes back sooner, which is the system working.
