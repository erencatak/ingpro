"""Local speech engines: mlx-whisper (STT), Kokoro (English TTS), Piper / macOS `say` (Turkish TTS)."""

import re
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

STT_SAMPLE_RATE = 16000
TTS_SAMPLE_RATE = 24000


@dataclass
class Word:
    text: str
    start: float
    end: float
    prob: float


@dataclass
class Transcript:
    text: str
    language: str = "en"
    words: list[Word] = field(default_factory=list)
    p_tr: float = 0.0
    top_langs: str = ""


class WhisperSTT:
    # Clear cases are decided from the language probabilities alone. In between (short or accented
    # speech, where the detector often puts most of its mass on unrelated languages) both languages are
    # decoded and the more confident transcript wins.
    CLEAR_EN = 0.15
    CLEAR_TR = 0.85

    def __init__(self, model: str):
        import mlx.core as mx
        import mlx_whisper
        from mlx_whisper.transcribe import ModelHolder

        self._mx = mx
        self._transcribe = mlx_whisper.transcribe
        self._holder = ModelHolder
        self._model = model

    def warm_up(self) -> None:
        self.transcribe(np.zeros(STT_SAMPLE_RATE, dtype=np.float32), "en")

    def _detect(self, audio: np.ndarray) -> tuple[float, str]:
        """P(Turkish) among {English, Turkish}, plus the top-3 languages for debugging."""
        from mlx_whisper.audio import N_FRAMES, log_mel_spectrogram, pad_or_trim

        model = self._holder.get_model(self._model, self._mx.float16)
        mel = log_mel_spectrogram(audio, n_mels=model.dims.n_mels)
        segment = pad_or_trim(mel, N_FRAMES, axis=-2).astype(self._mx.float16)
        _, probs = model.detect_language(segment)
        en, tr = probs.get("en", 0.0), probs.get("tr", 0.0)
        top = ", ".join(f"{k} {v:.2f}" for k, v in sorted(probs.items(), key=lambda kv: -kv[1])[:3])
        return (tr / (en + tr) if en + tr > 0 else 0.0), top

    # Learners mix languages ("how nasıl söylenir ingilizcede"). A bilingual prompt keeps Whisper from
    # forcing the whole utterance into one language.
    PRIMING = "Naber Alex! How are you? Ben İngilizce öğreniyorum, bunu nasıl söylerim? I want to say this."

    def _decode(self, audio: np.ndarray, lang: str) -> tuple[Transcript, float]:
        """Returns the transcript and its mean per-segment confidence (avg log-probability)."""
        # Only the Turkish decode gets the prompt: on the English decode Whisper copies it back
        # ("Nasılsın? How are you?") and the copy scores as high confidence.
        prompt = {"initial_prompt": self.PRIMING} if lang == "tr" else {}
        result = self._transcribe(audio, path_or_hf_repo=self._model, language=lang, word_timestamps=True, **prompt)
        segments = result.get("segments", [])
        words = [Word(w["word"].strip(), w["start"], w["end"], w["probability"]) for seg in segments for w in seg.get("words", [])]
        confidence = float(np.mean([seg["avg_logprob"] for seg in segments])) if segments else -10.0
        return Transcript(result["text"].strip(), lang, words), confidence

    def transcribe(self, audio: np.ndarray, lang: str = "auto") -> Transcript:
        """audio: mono float32 at 16 kHz. lang: 'auto' | 'en' | 'tr'."""
        if lang != "auto":
            return self._decode(audio, lang)[0]

        p_tr, top = self._detect(audio)
        if p_tr < self.CLEAR_EN:
            chosen, _ = self._decode(audio, "en")
        elif p_tr > self.CLEAR_TR:
            chosen, _ = self._decode(audio, "tr")
        else:
            en, en_conf = self._decode(audio, "en")
            tr, tr_conf = self._decode(audio, "tr")
            # A wrong-language decode of real speech is low-confidence gibberish; English gets a small benefit of the doubt
            chosen = tr if tr_conf > en_conf + 0.05 else en
        chosen.p_tr, chosen.top_langs = p_tr, top
        return chosen


# Emoji and markdown symbols read badly when spoken
_UNSPEAKABLE = re.compile(r"[\U0001F000-\U0001FAFF☀-➿*_#`~]")


def _resample(audio: np.ndarray, src: int, dst: int = TTS_SAMPLE_RATE) -> np.ndarray:
    if src == dst or audio.size == 0:
        return audio
    n = int(len(audio) * dst / src)
    return np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)


class KokoroTTS:
    def __init__(self, voice: str):
        from kokoro import KPipeline

        self._pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        self.voice = voice

    def synthesize(self, text: str, speed: float = 1.0) -> np.ndarray:
        """Returns mono float32 at 24 kHz."""
        chunks = [np.asarray(a, dtype=np.float32) for _, _, a in self._pipeline(text, voice=self.voice, speed=speed)]
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)


class PiperTurkishTTS:
    def __init__(self, model_path: Path):
        from piper import PiperVoice

        self._voice = PiperVoice.load(str(model_path))
        self._sr = self._voice.config.sample_rate

    def synthesize(self, text: str, speed: float = 1.0) -> np.ndarray:
        from piper import SynthesisConfig

        cfg = SynthesisConfig(length_scale=1.0 / max(speed, 0.1))
        chunks = [np.frombuffer(c.audio_int16_bytes, dtype=np.int16) for c in self._voice.synthesize(text, syn_config=cfg)]
        pcm = np.concatenate(chunks).astype(np.float32) / 32768 if chunks else np.zeros(0, dtype=np.float32)
        return _resample(pcm, self._sr)


class MacSayTurkishTTS:
    """Built-in macOS 'Yelda' voice. Not open source, but free, offline and often more natural."""

    def __init__(self, voice: str = "Yelda"):
        self._voice = voice

    def synthesize(self, text: str, speed: float = 1.0) -> np.ndarray:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.wav"
            subprocess.run(
                ["say", "-v", self._voice, "-r", str(int(175 * speed)), "-o", str(out), "--data-format=LEI16@24000", "--", text],
                check=True,
            )
            with wave.open(str(out)) as w:
                pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        return pcm


def _normalize_loudness(audio: np.ndarray, target_rms: float = 0.09) -> np.ndarray:
    """The two voices come out at different volumes; bring both to the same level."""
    if audio.size == 0:
        return audio
    rms = float(np.sqrt(np.mean(audio**2)))
    if rms < 1e-4:
        return audio
    gain = min(target_rms / rms, 0.95 / max(float(np.max(np.abs(audio))), 1e-6))
    return (audio * gain).astype(np.float32)


def time_stretch(audio: np.ndarray, rate: float, n_fft: int = 1024, hop: int = 256) -> np.ndarray:
    """Phase-vocoder time stretch: rate < 1 slows speech down, > 1 speeds it up, pitch stays the same."""
    if abs(rate - 1.0) < 0.02 or audio.size < n_fft * 2:
        return audio
    win = np.hanning(n_fft)
    padded = np.pad(audio, (n_fft // 2, n_fft // 2))
    n_frames = 1 + (len(padded) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n_frames)[:, None]
    spec = np.fft.rfft(padded[idx] * win, axis=1)
    omega = 2 * np.pi * hop * np.arange(spec.shape[1]) / n_fft
    steps = np.arange(0, n_frames - 1, rate)
    out = np.empty((len(steps), spec.shape[1]), dtype=np.complex128)
    phase = np.angle(spec[0])
    for k, t in enumerate(steps):
        i = int(t)
        frac = t - i
        mag = (1 - frac) * np.abs(spec[i]) + frac * np.abs(spec[i + 1])
        out[k] = mag * np.exp(1j * phase)
        dphi = np.angle(spec[i + 1]) - np.angle(spec[i]) - omega
        dphi -= 2 * np.pi * np.round(dphi / (2 * np.pi))
        phase += omega + dphi
    frames = np.fft.irfft(out, axis=1) * win
    length = hop * (len(steps) - 1) + n_fft
    y = np.zeros(length)
    weight = np.zeros(length)
    for k in range(len(steps)):
        y[k * hop : k * hop + n_fft] += frames[k]
        weight[k * hop : k * hop + n_fft] += win**2
    y /= np.maximum(weight, 1e-6)
    return y[n_fft // 2 : -(n_fft // 2)].astype(np.float32)


def ensure_voice_ref(path: Path, kokoro_voice: str) -> Path:
    """Alex's voice is cloned from a short reference clip. The default clip is generated with Kokoro;
    drop your own 6-15 s mono wav at `path` (or set INGPRO_VOICE_REF) to change how Alex sounds."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "Hi there, I'm Alex. I'm happy to practice English with you today. Tell me about your day, and don't worry about mistakes."
    audio = KokoroTTS(kokoro_voice).synthesize(text, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TTS_SAMPLE_RATE)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
    return path


class ChatterboxTTS:
    """One voice for both languages: Chatterbox Multilingual (MIT) cloning a reference clip.
    The T3 language model is quantized to 4 bit in memory and the flow-matching stage runs 5 steps instead of 10:
    together ~2x faster than real time on an M4."""

    def __init__(self, model: str, voice_ref: Path, quantize: bool = True, exaggeration: float = 0.3, steps: int = 5):
        import mlx.core as mx
        import mlx.nn as nn
        import soundfile as sf
        from mlx_audio.tts.utils import load_model

        self._model = load_model(model)
        if quantize:
            nn.quantize(self._model.t3.tfmr, group_size=64, bits=4)
            mx.eval(self._model.parameters())
        # Fewer flow-matching steps halve the synthesis time (the vocoder stage dominates it) at little quality cost
        self._model.s3gen.flow.n_timesteps = steps
        ref, sr = sf.read(str(voice_ref), dtype="float32")
        self._conds = self._model.prepare_conditionals(mx.array(ref), sr, exaggeration=exaggeration)

    def synthesize(self, text: str, lang: str, speed: float = 1.0) -> np.ndarray:
        chunks = [
            np.array(r.audio, dtype=np.float32)
            for r in self._model.generate(text, conds=self._conds, lang_code=lang, cfg_weight=0.0, verbose=False)
        ]
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        return time_stretch(audio, speed)


class ClassicVoices:
    """Fallback: Kokoro (English) + Piper/macOS (Turkish). Two different voices, but no heavy model."""

    def __init__(self, english: KokoroTTS, turkish: PiperTurkishTTS | MacSayTurkishTTS):
        self._en = english
        self._tr = turkish

    def synthesize(self, text: str, lang: str, speed: float = 1.0) -> np.ndarray:
        return (self._tr if lang == "tr" else self._en).synthesize(text, speed)


class SpeechSynth:
    """Cleans text, speaks each language run with the right pronunciation, returns 24 kHz mono float32."""

    def __init__(self, backend: ChatterboxTTS | ClassicVoices):
        self._backend = backend

    def warm_up(self) -> None:
        self.synthesize("Hello.", "en")
        self.synthesize("Merhaba.", "tr")

    def synthesize(self, text: str, default_lang: str, speed: float = 1.0) -> np.ndarray:
        from .lang import split_by_language

        text = _UNSPEAKABLE.sub("", text).strip()
        if not text:
            return np.zeros(0, dtype=np.float32)
        gap = np.zeros(int(0.12 * TTS_SAMPLE_RATE), dtype=np.float32)
        pieces: list[np.ndarray] = []
        for lang, run in split_by_language(text, default_lang):
            run = run.strip()
            if not re.search(r"\w", run):
                continue
            if pieces:
                pieces.append(gap)
            pieces.append(self._backend.synthesize(run, lang, speed))
        return _normalize_loudness(np.concatenate(pieces)) if pieces else np.zeros(0, dtype=np.float32)
