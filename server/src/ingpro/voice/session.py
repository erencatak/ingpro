"""One voice conversation over a WebSocket.

Protocol
  client → server
    binary: one finished utterance, mono float32 PCM @ 16 kHz (from the browser VAD)
    json:   {"type": "text", "text": "..."}   typed message instead of speech
            {"type": "interrupt"}              user started talking over the tutor
            {"type": "settings", "speed": 0.9, "stt_lang": "auto" | "en" | "tr"}
  server → client
    json:   {"type": "ready"}            followed by Alex's unprompted greeting (turn 1)
            {"type": "user_transcript", "turn": n, "text": "...", "lang": "en"|"tr", "words": [...], "stt_ms": ..}
            {"type": "assistant_start", "turn": n}
            {"type": "assistant_delta", "turn": n, "text": "..."}   (may start with the instant filler, e.g. "Hmm, I see. ")
            {"type": "assistant_end", "turn": n, "text": "...", "first_token_ms": ..}
            {"type": "usage", "turn": n, "valid": .., "rule": 1-4|null, "points": .., "unit_points": .., "required": .., ...}
                                          speaking points of the sentence (only in a session about a grammar unit)
            {"type": "tokens", "total_tokens": .., "cost_usd": ..}
                                          running total for the whole session (Alex + the judge), sent after every reply/score
            {"type": "starters", "turn": n, "items": [{"id", "en", "tr", "grammar"}, ...]}
                                          a few sentence-starter suggestions for what Alex just said (deterministic, see starters.py)
            {"type": "error", "message": "..."}
    binary: uint32 turn id (little endian) + int16 PCM @ 24 kHz, one frame per sentence
"""

import asyncio
import contextlib
import json
import re
import struct
import logging
import time
import wave
from dataclasses import asdict

import numpy as np
from fastapi import WebSocket

from .. import lessons, starters
from ..agents.provider import ChatSession, TokenUsage
from ..brain import usage
from ..brain.judge import Judge
from ..brain.rules import utcnow
from ..brain.service import BrainService
from .engines import SpeechSynth, WhisperSTT
from .fillers import FillerBank
from ..config import settings
from .lang import detect_lang

log = logging.getLogger("ingpro.voice")
_MAX_DEBUG_CLIPS = 30

# End of a sentence: punctuation followed by whitespace. Short fragments are held back
# so "Hi!" doesn't become its own tiny audio chunk.
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]?\s+")
_MIN_SENTENCE_CHARS = 12
# The first chunk of a reply may also end at a comma: the voice model is slow enough that waiting
# for a full sentence noticeably delays the first sound.
_FIRST_CHUNK_END = re.compile(r"(?<=[.!?,;:])[\"')\]]?\s+")
_MIN_FIRST_CHUNK_CHARS = 9
_GREETING_CUE = "(The conversation just started. Open it with one short sentence, in character if the scenario has a role, and keep it easy to answer.)"


class VoiceSession:
    def __init__(self, ws: WebSocket, chat: ChatSession, stt: WhisperSTT, tts: SpeechSynth, stt_lock: asyncio.Lock, tts_lock: asyncio.Lock, speed: float, fillers: FillerBank | None = None,
                 topic: dict | None = None, brain: BrainService | None = None, judge: Judge | None = None, scenario: str = "free"):
        self.ws = ws
        self.chat = chat
        self.stt = stt
        self.tts = tts
        self.stt_lock = stt_lock
        self.tts_lock = tts_lock
        self.speed = speed
        self.fillers = fillers
        self.topic, self.brain, self.judge = topic, brain, judge  # a session about one grammar unit scores the learner's spoken sentences
        self.scenario = scenario
        self.session_id = f"s{int(time.time())}"
        self._started = self._last_activity = utcnow()  # practice time = first moment to the last turn, so an idle open tab does not count
        self._judge_usage = TokenUsage()  # chat.usage already totals Alex's own turns
        self._shown_starters: set[str] = set()  # ids already suggested this session, so the cheat sheet rotates
        self._scoring: set[asyncio.Task] = set()
        self.turn = 0
        self.stt_lang = "auto"
        self._lang = "en"  # language of the user's last message; replies and TTS follow it
        self._reply_task: asyncio.Task | None = None
        self._spoke_in_reply = False

    async def run(self) -> None:
        await self.chat.start()
        await self.ws.send_json({"type": "ready"})
        # Alex speaks first: feels natural and hides the slow first turn of a fresh CLI session
        self.turn += 1
        self._reply_task = asyncio.create_task(self._reply(self.turn, lessons.greeting_cue((self.topic or {}).get("lesson")) or _GREETING_CUE, tag=False))
        while True:
            msg = await self.ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                await self._on_audio(msg["bytes"])
            elif msg.get("text") is not None:
                await self._on_control(msg["text"])

    async def close(self) -> None:
        if self.brain and self.turn > 1:  # turn 1 is Alex's greeting: a session the learner never spoke in is not practice
            self.brain.store.log_session(self._started, self._last_activity, (self._last_activity - self._started).total_seconds(), self.turn - 1)
        await self._cancel_reply()
        await self.chat.close()  # the judge does not need Alex's process
        if self._scoring:  # a sentence spoken right before leaving still gets its points, but not for ever
            _, pending = await asyncio.wait(self._scoring, timeout=30)
            for task in pending:
                task.cancel()

    async def _on_control(self, raw: str) -> None:
        data = json.loads(raw)
        match data.get("type"):
            case "text":
                text = data.get("text", "").strip()
                if text:
                    await self._start_turn(text, detect_lang(text, self._lang), None, 0)
            case "interrupt":
                await self._cancel_reply()
            case "settings":
                self.speed = float(data.get("speed", self.speed))
                if data.get("stt_lang") in ("auto", "en", "tr"):
                    self.stt_lang = data["stt_lang"]

    async def _on_audio(self, payload: bytes) -> None:
        await self._cancel_reply()
        audio = np.frombuffer(payload, dtype=np.float32)
        started = time.perf_counter()
        async with self.stt_lock:
            transcript = await asyncio.to_thread(self.stt.transcribe, audio, self.stt_lang)
        stt_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "STT %dms mode=%s -> lang=%s p_tr=%.2f (top: %s) text=%r",
            stt_ms, self.stt_lang, transcript.language, transcript.p_tr, transcript.top_langs, transcript.text,
        )
        self._save_debug_clip(audio, transcript.language)
        if transcript.text:
            await self._start_turn(transcript.text, transcript.language, [asdict(w) for w in transcript.words], stt_ms)

    @staticmethod
    def _save_debug_clip(audio: np.ndarray, lang: str) -> None:
        """Keeps the last few utterances (data/debug/) so recognition problems can be replayed."""
        folder = settings.data_dir / "debug"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"utt_{time.strftime('%H%M%S')}_{lang}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
        for old in sorted(folder.glob("utt_*.wav"))[:-_MAX_DEBUG_CLIPS]:
            old.unlink(missing_ok=True)

    async def _start_turn(self, text: str, lang: str, words: list[dict] | None, stt_ms: int) -> None:
        await self._cancel_reply()
        self.turn += 1
        self._last_activity = utcnow()
        self._lang = lang
        await self.ws.send_json({"type": "user_transcript", "turn": self.turn, "text": text, "lang": lang, "words": words or [], "stt_ms": stt_ms})
        self._reply_task = asyncio.create_task(self._reply(self.turn, text))
        if self.topic and self.brain and self.judge:
            task = asyncio.create_task(self._score(self.turn, text, lang, words))
            self._scoring.add(task)
            task.add_done_callback(self._scoring.discard)

    async def _score(self, turn: int, text: str, lang: str, words: list[dict] | None) -> None:
        """Speaking points for one utterance. Runs beside Alex's reply and never slows it down."""
        unit = self.topic["id"]
        probs = [w["prob"] for w in words if isinstance(w.get("prob"), (int, float))] if words else []
        speech = usage.Speech(
            spoken=words is not None, lang=lang,
            pron_conf=(sum(probs) / len(probs)) if probs else None,
            weak_share=(sum(p < usage.WEAK_WORD for p in probs) / len(probs)) if probs else 0.0,
        )
        result = None
        try:
            reason = usage.precheck(speech)
            if reason:  # not valid: no need to ask the judge
                if speech.spoken:  # kept in the log so the pronunciation threshold can be tuned later
                    log.info("Unit %s: not clear enough (conf=%s, weak=%.2f, lang=%s): %r", unit, speech.pron_conf, speech.weak_share, lang, text[:60])
                result = {**self.brain.unit_summary(unit), "valid": False, "rule": None, "points": 0, "reason": reason, "new_words": [], "spoken": speech.spoken}
            elif not usage.normalize(text):
                result = {**self.brain.unit_summary(unit), "valid": False, "rule": None, "points": 0, "reason": "Cümle anlaşılamadı.", "new_words": [], "spoken": True}
            else:
                judgement, tokens = await self.judge.evaluate(self.topic, text)
                self._judge_usage.add(tokens)
                result = await asyncio.to_thread(self.brain.record_usage, unit, judgement, speech, text, self.session_id)
                needs_vad = result.pop("words_needing_vad", None)  # internal signal only: never sent over the wire
                if needs_vad:
                    vad_task = asyncio.create_task(self.brain.enrich_word_vad(needs_vad))
                    self._scoring.add(vad_task)
                    vad_task.add_done_callback(self._scoring.discard)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Scoring failed")
            result = {"valid": False, "points": 0, "rule": None, "reason": "Puanlama şu an yapılamadı.", "spoken": speech.spoken}
        with contextlib.suppress(Exception):  # the socket may be gone: the points are already recorded
            await self.ws.send_json({"type": "usage", "turn": turn, **result})
        await self._send_tokens()

    async def _cancel_reply(self) -> None:
        task, self._reply_task = self._reply_task, None
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.chat.interrupt()

    async def _reply(self, turn: int, text: str, tag: bool = True) -> None:
        await self.ws.send_json({"type": "assistant_start", "turn": turn})
        started = time.perf_counter()
        first_token_ms = None
        self._spoke_in_reply = False
        full, pending = "", ""
        message = f"[{self._lang}] {text}" if tag else text
        try:
            # Instant reaction from the cache: covers the LLM's first-token wait. The LLM is told about it so it doesn't repeat it.
            filler = self.fillers.pick(text, self._lang, self.speed) if tag and self.fillers else None
            if filler:
                message += f'\n(Already said aloud: "{filler.text}" — do not react again with a similar phrase; go straight to your real reply)'
                await self.ws.send_json({"type": "assistant_delta", "turn": turn, "text": filler.text + " "})
                await self._send_audio(turn, filler.audio)
            async for delta in self.chat.send(message):
                if first_token_ms is None:
                    first_token_ms = int((time.perf_counter() - started) * 1000)
                full += delta
                pending += delta
                await self.ws.send_json({"type": "assistant_delta", "turn": turn, "text": delta})
                pending = await self._speak_complete_sentences(turn, pending)
            if pending.strip():
                await self._speak(turn, pending)
            await self.ws.send_json({"type": "assistant_end", "turn": turn, "text": full, "first_token_ms": first_token_ms})
            await self._send_tokens()
            await self._send_starters(turn, full)
            self._last_activity = utcnow()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # surface provider failures instead of dying silently
            await self.ws.send_json({"type": "error", "message": str(exc)})

    async def _send_starters(self, turn: int, alex_text: str) -> None:
        """A few sentence-starter suggestions for what Alex just said: deterministic, no LLM call (see starters.py)."""
        level = self.brain.vocab_ceiling() if self.brain else "A1"
        items = await asyncio.to_thread(starters.pick, alex_text, self.scenario, level, settings.content_dir, self._shown_starters)
        if not items:
            return
        self._shown_starters.update(s["id"] for s in items)
        with contextlib.suppress(Exception):  # the socket may already be gone by the time this trails in
            await self.ws.send_json({
                "type": "starters", "turn": turn,
                "items": [{"id": s["id"], "en": s["en"], "tr": s["tr"], "grammar": s["grammar"]} for s in items],
            })

    async def _send_tokens(self) -> None:
        """Deterministic total: summed straight from the SDK's per-call usage, Alex's turns plus the judge's."""
        total = TokenUsage()
        total.add(self.chat.usage)
        total.add(self._judge_usage)
        with contextlib.suppress(Exception):
            await self.ws.send_json({"type": "tokens", "total_tokens": total.total_tokens, "cost_usd": round(total.cost_usd, 4)})

    async def _speak_complete_sentences(self, turn: int, pending: str) -> str:
        while True:
            if self._spoke_in_reply:
                boundary, min_chars = _SENTENCE_END, _MIN_SENTENCE_CHARS
            else:
                boundary, min_chars = _FIRST_CHUNK_END, _MIN_FIRST_CHUNK_CHARS
            match = next((m for m in boundary.finditer(pending) if m.start() >= min_chars), None)
            if not match:
                return pending
            await self._speak(turn, pending[: match.start()])
            pending = pending[match.end():]

    async def _speak(self, turn: int, sentence: str) -> None:
        self._spoke_in_reply = True
        async with self.tts_lock:
            audio = await asyncio.to_thread(self.tts.synthesize, sentence, self._lang, self.speed)
        log.info("TTS %r -> %.1fs audio", sentence[:40], audio.size / 24000)
        await self._send_audio(turn, audio)

    async def _send_audio(self, turn: int, audio: np.ndarray) -> None:
        if audio.size:
            pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
            await self.ws.send_bytes(struct.pack("<I", turn) + pcm)
