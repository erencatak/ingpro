"""Short spoken reactions ("Hmm, I see.") that play the moment the user stops talking.

They are synthesized once with the tutor's own voice and cached on disk, so they cost no TTS time at
runtime. They cover the LLM's first-token wait and make the exchange feel like a person listening.
All of them are emotionally neutral: they are chosen without understanding what the user said.
"""

import hashlib
import logging
import random
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .engines import SpeechSynth, time_stretch

log = logging.getLogger("ingpro.voice")

FILLERS: dict[str, dict[str, list[str]]] = {
    "en": {
        "statement": ["Hmm, I see.", "Okay, right.", "Ah, I got it.", "Mm, okay.", "Oh, okay.", "Right, right.", "Ah, I see."],
        "question": ["Well, let me think.", "Good question.", "Hmm, okay.", "Ooh, let me think."],
    },
    "tr": {
        "statement": ["Hmm, anladım.", "Tamam, evet.", "Ha, tamam.", "Aa, anlıyorum.", "Evet, evet.", "Tamamdır."],
        "question": ["Hmm, bir düşüneyim.", "İyi soru.", "Bakalım, tamam."],
    },
}

_QUESTION = re.compile(r"\?\s*$|^(what|why|how|when|where|who|which|can|could|do|does|did|is|are|will|would)\b|\bm[iıuü]\b", re.IGNORECASE)
_MIN_WORDS = 2  # a single word ("Yes.") deserves a real answer, not an "I see"
_SKIP_CHANCE = 0.15  # a reaction on every single turn sounds like a script
# Greetings and thanks get a real reply; "Hmm, I see." after "Hello." would be odd
_SOCIAL = {
    "hello", "hi", "hey", "yo", "bye", "goodbye", "thanks", "thank", "you", "please", "sorry", "very", "much", "so", "many", "lot", "a", "yes", "no", "ok", "okay",
    "selam", "merhaba", "naber", "nasılsın", "günaydın", "teşekkürler", "teşekkür", "ederim", "çok", "sağol", "sağ", "ol", "evet", "hayır", "tamam", "hoşça", "kal",
}
_SAMPLE_RATE = 24000
_CACHE_VERSION = 2  # bump when the way clips are produced changes


def _trim_silence(audio: np.ndarray, threshold: float = 0.01, tail_s: float = 0.08) -> np.ndarray:
    """Chatterbox pads its clips with silence; the filler should hand over to the reply immediately."""
    loud = np.flatnonzero(np.abs(audio) > threshold)
    if loud.size == 0:
        return audio
    return audio[max(loud[0] - int(0.03 * _SAMPLE_RATE), 0) : loud[-1] + int(tail_s * _SAMPLE_RATE)]


def _synth_clip(synth: SpeechSynth, lang: str, text: str) -> np.ndarray:
    # The voice model sometimes rambles on after a very short text; a take much longer than the words need is bad
    max_seconds = 0.45 * len(text.split()) + 0.8
    best = None
    for _ in range(5):
        audio = _trim_silence(synth.synthesize(text, lang, 1.0))
        if 0.3 < audio.size / _SAMPLE_RATE < max_seconds:
            return audio
        if best is None or audio.size < best.size:
            best = audio
    return best


def is_question(text: str) -> bool:
    return bool(_QUESTION.search(text.strip()))


@dataclass
class Filler:
    text: str
    audio: np.ndarray  # mono float32, 24 kHz


class FillerBank:
    def __init__(self, clips: dict[tuple[str, str, str], np.ndarray]):
        self._clips = clips  # (lang, kind, text) -> audio
        self._stretched: dict[tuple[str, str, str, float], np.ndarray] = {}
        self._last: str | None = None

    @classmethod
    def load_or_build(cls, synth: SpeechSynth, cache_dir: Path, fingerprint: str) -> "FillerBank":
        """fingerprint: anything that changes how the voice sounds (engine, reference clip, steps)."""
        texts = [(lang, kind, t) for lang, kinds in FILLERS.items() for kind, ts in kinds.items() for t in ts]
        key = hashlib.sha1((f"{_CACHE_VERSION}|{fingerprint}" + repr(texts)).encode()).hexdigest()[:12]
        cache = cache_dir / f"fillers_{key}.npz"
        if cache.exists():
            data = np.load(cache)
            return cls({t: data[str(i)] for i, t in enumerate(texts)})
        log.info("Building %d filler clips (first run only)…", len(texts))
        clips = {t: _synth_clip(synth, t[0], t[2]) for t in texts}
        cache_dir.mkdir(parents=True, exist_ok=True)
        for old in cache_dir.glob("fillers_*.npz"):
            old.unlink(missing_ok=True)
        np.savez(cache, **{str(i): clips[t] for i, t in enumerate(texts)})
        return cls(clips)

    def pick(self, text: str, lang: str, speed: float) -> Filler | None:
        """A reaction for this user message, or None when silence is the better answer."""
        words = re.findall(r"[\w']+", text.lower())
        if len(words) < _MIN_WORDS or all(w in _SOCIAL for w in words) or random.random() < _SKIP_CHANCE:
            return None
        kind = "question" if is_question(text) else "statement"
        lang = lang if lang in FILLERS else "en"
        chosen = random.choice([t for t in FILLERS[lang][kind] if t != self._last])
        self._last = chosen
        cache_key = (lang, kind, chosen, round(speed, 2))
        if cache_key not in self._stretched:
            self._stretched[cache_key] = time_stretch(self._clips[(lang, kind, chosen)], speed)
        log.info("Filler %r (%s, %s)", chosen, lang, kind)
        return Filler(chosen, self._stretched[cache_key])
