"""One process-wide spaCy pipeline, shared by anything that needs deterministic (non-LLM) English text analysis."""

from __future__ import annotations

_nlp = None


def doc(text: str):
    """A spaCy Doc for one short utterance: POS tags + lemmas. Parser and NER are disabled — not needed, and slower."""
    global _nlp
    if _nlp is None:
        import spacy

        _nlp = spacy.load("en_core_web_sm", disable=("parser", "ner"))
    return _nlp(text)
