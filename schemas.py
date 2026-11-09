"""Tool schemas for the Lingua plugin: what the model sees."""

LINGUA_ADD = {
    "name": "lingua_add",
    "description": (
        "Add a vocabulary card to the user's Lingua deck: a word or phrase "
        "in the language they are learning, its translation, and an optional "
        "example sentence. New cards are due immediately, so they enter the "
        "review rotation right away. Use this whenever the user teaches you "
        "a word, asks to learn vocabulary, or corrects a translation. Adding "
        "the same term twice updates the existing card instead of "
        "duplicating it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "term": {
                "type": "string",
                "description": "The word or phrase in the target language, e.g. 'bonjour' or 'je voudrais'.",
            },
            "translation": {
                "type": "string",
                "description": "What the term means in the user's language, e.g. 'hello' or 'I would like'.",
            },
            "language": {
                "type": "string",
                "description": "The language being learned, e.g. 'french', 'spanish', 'yoruba'. Each language is its own deck.",
            },
            "example": {
                "type": "string",
                "description": "Optional example sentence using the term, with its translation if helpful.",
            },
        },
        "required": ["term", "translation", "language"],
    },
}

LINGUA_DUE = {
    "name": "lingua_due",
    "description": (
        "Get the vocabulary cards that are due for review right now, "
        "scheduled by spaced repetition. Call this to start a review "
        "session: quiz the user ONE card at a time, show only the term "
        "(or only the translation, to vary direction), wait for their "
        "answer, then judge it and record the result with lingua_grade "
        "before showing the next card. Never show a card's translation "
        "before the user has attempted it. Optionally restrict to one "
        "language deck."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum cards to fetch for the session (default 10, max 50).",
            },
            "language": {
                "type": "string",
                "description": "Only fetch cards from this language deck.",
            },
        },
        "required": [],
    },
}

LINGUA_GRADE = {
    "name": "lingua_grade",
    "description": (
        "Record how well the user remembered a card during review and "
        "reschedule it with spaced repetition. Grades: 'again' (no recall, "
        "or wrong), 'hard' (correct but with real effort), 'good' (correct "
        "with normal effort), 'easy' (instant, certain recall). Be honest: "
        "grade what the user actually did, not what they hoped. A failed "
        "card returns in about 10 minutes; good cards stretch from 1 day "
        "to 6 days and then multiply by the card's ease factor."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "description": "The id of the card being graded, from lingua_due.",
            },
            "grade": {
                "type": "string",
                "enum": ["again", "hard", "good", "easy"],
                "description": "How well the user recalled the card.",
            },
        },
        "required": ["id", "grade"],
    },
}

LINGUA_LIST = {
    "name": "lingua_list",
    "description": (
        "List the user's Lingua vocabulary cards, ordered by language and "
        "due date. Optionally filter by language deck or by a search string "
        "matching the term or translation. Use this when the user asks what "
        "words they are learning, or to find a card id before removing it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "description": "Only list cards from this language deck.",
            },
            "query": {
                "type": "string",
                "description": "Only list cards whose term or translation contains this text.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum cards to list (default 30, max 200).",
            },
        },
        "required": [],
    },
}

LINGUA_REMOVE = {
    "name": "lingua_remove",
    "description": (
        "Permanently delete one Lingua vocabulary card by its numeric id. "
        "Use lingua_list first to find the id. Use this when a card is "
        "wrong, a duplicate the user rejects, or the user simply does not "
        "want to learn that word."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "description": "The numeric id of the card to delete.",
            },
        },
        "required": ["id"],
    },
}

LINGUA_STATS = {
    "name": "lingua_stats",
    "description": (
        "Show Lingua learning statistics: cards per language, how many are "
        "due right now, how many are mastered (interval of 21 days or "
        "more), total reviews completed, and how many of the last 7 days "
        "included at least one review. Use this to report progress or to "
        "decide whether to suggest a review session."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


_CARD_REF = {
    "id": {
        "type": "integer",
        "description": "Id of an existing card; term, translation and language are read from it when not given directly.",
    },
    "term": {
        "type": "string",
        "description": "The word or phrase in the target language, e.g. 'le pain'.",
    },
    "translation": {
        "type": "string",
        "description": "What the term means in the user's language, e.g. 'bread'.",
    },
    "language": {
        "type": "string",
        "description": "The language being learned, e.g. 'french', 'spanish', 'yoruba'.",
    },
}

LINGUA_EXAMPLE = {
    "name": "lingua_example",
    "description": (
        "Generate one fresh, contextual example sentence for a vocabulary "
        "card using the Otari LLM gateway, with its translation and a "
        "short usage note. Use this when a card has no example, when the "
        "stored example feels stale, or when the user asks to see a word "
        "used in a real sentence or in a specific context. Requires the "
        "Otari tutor layer (OTARI_API_KEY set); without a key it returns "
        "a clear explanation instead of an example, and the offline "
        "tools keep working."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            **_CARD_REF,
            "context": {
                "type": "string",
                "description": "Optional setting for the sentence, e.g. 'at a bakery', 'travel', 'work'.",
            },
        },
        "required": [],
    },
}

LINGUA_MNEMONIC = {
    "name": "lingua_mnemonic",
    "description": (
        "Generate a vivid mnemonic hook that links the sound or shape of "
        "a vocabulary term to its meaning, using the Otari LLM gateway. "
        "Use this when the user keeps missing a card (graded again more "
        "than once) or asks for a memory trick. Requires the Otari tutor "
        "layer (OTARI_API_KEY set); without a key it returns a clear "
        "explanation instead of a mnemonic."
    ),
    "parameters": {
        "type": "object",
        "properties": dict(_CARD_REF),
        "required": [],
    },
}

LINGUA_CHECK = {
    "name": "lingua_check",
    "description": (
        "Semantically check a learner's free-text answer to a quiz card "
        "using the Otari LLM gateway: it judges meaning rather than "
        "exact string match, accepts synonyms and minor typos, and "
        "returns a verdict (correct, close, wrong), short feedback, and "
        "a suggested SM-2 grade. It does NOT record the grade: show the "
        "feedback, then call lingua_grade with the suggested grade "
        "(adjusting if the learner disputes it). Use this during review "
        "sessions whenever an answer is not obviously right or wrong. "
        "Requires the Otari tutor layer (OTARI_API_KEY set); without a "
        "key, judge the answer yourself as before."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            **_CARD_REF,
            "answer": {
                "type": "string",
                "description": "The learner's free-text answer to check.",
            },
            "direction": {
                "type": "string",
                "enum": ["term_to_translation", "translation_to_term"],
                "description": "Which way the card was quizzed (default term_to_translation).",
            },
        },
        "required": ["answer"],
    },
}
