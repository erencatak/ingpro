import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field

from .agents.provider import create_chat_session
from . import lessons, nlp
from .brain import usage as brain_usage
from .brain.judge import Judge
from .brain.service import BrainService, UnknownNeuron, UnknownUnit
from .brain.store import Store
from .brain.vault import Vault
from .config import settings
from .lessons import load_lessons
from .scenario_gen import ScenarioGenError, generate as generate_scenario
from .stats import build_stats
from .voice.fillers import FillerBank
from .voice.engines import ChatterboxTTS, ClassicVoices, KokoroTTS, MacSayTurkishTTS, PiperTurkishTTS, SpeechSynth, WhisperSTT, ensure_voice_ref
from .voice.session import VoiceSession

log = logging.getLogger("ingpro")


class Engines:
    stt: WhisperSTT
    tts: SpeechSynth
    fillers: FillerBank | None = None
    # MLX / Kokoro are not safe to run concurrently from several threads
    stt_lock = asyncio.Lock()
    tts_lock = asyncio.Lock()


engines = Engines()
brain: BrainService | None = None
judge: Judge | None = None
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def load_course() -> dict:
    """The grammar course: content/grammar/yener.json (the book's units) if present, otherwise the placeholder sample."""
    folder = settings.content_dir / "grammar"
    path = next((p for p in (folder / "yener.json", folder / "sample.json") if p.is_file()), None)
    course = json.loads(path.read_text()) if path else {"source": "", "verified": False, "topics": []}
    levels_file = folder / "levels.json"
    if course.get("verified") and levels_file.is_file():  # the CEFR bands are written against the book's unit numbers
        levels = json.loads(levels_file.read_text())["levels"]
        for t in course["topics"]:
            if levels.get(str(t["id"])) in brain_usage.REQUIRED:
                t["band"] = levels[str(t["id"])]
    return course


@asynccontextmanager
async def lifespan(app: FastAPI):
    global brain, judge
    store = Store(settings.data_dir / "ingpro.db")
    brain = BrainService(store, Vault(settings.vault_dir, store) if settings.vault_dir else None, content_dir=settings.content_dir, word_vad_model=settings.judge_model)
    judge = Judge(settings.judge_model, vocab_cefr=store.vocab_cefr)
    log.info("Brain: %s", brain.seed(load_course()))
    if brain.vault:
        log.info("Brain vault: %s", await asyncio.to_thread(brain.sync_vault))
    await asyncio.to_thread(brain.consolidate_if_stale)
    await asyncio.to_thread(nlp.doc, "warm up")  # the judge and the starter picker share this spaCy pipeline: load it once, up front
    log.info("Loading speech models (first run downloads them)…")
    engines.stt = WhisperSTT(settings.stt_model)
    if settings.tts_engine == "chatterbox":
        ref = await asyncio.to_thread(ensure_voice_ref, settings.voice_ref, settings.tts_voice)
        engines.tts = SpeechSynth(await asyncio.to_thread(ChatterboxTTS, settings.chatterbox_model, ref, True, 0.3, settings.chatterbox_steps))
    else:
        use_macos = settings.tts_tr_engine == "macos" or (settings.tts_tr_engine == "auto" and sys.platform == "darwin")
        turkish = MacSayTurkishTTS() if use_macos else PiperTurkishTTS(settings.piper_tr_model)
        engines.tts = SpeechSynth(ClassicVoices(KokoroTTS(settings.tts_voice), turkish))
    await asyncio.to_thread(engines.stt.warm_up)
    await asyncio.to_thread(engines.tts.warm_up)
    if settings.fillers:
        ref = settings.voice_ref
        fingerprint = f"{settings.tts_engine}|{settings.tts_voice}|{settings.chatterbox_steps}|{ref.stat().st_mtime_ns if ref.exists() else 0}"
        engines.fillers = await asyncio.to_thread(FillerBank.load_or_build, engines.tts, settings.data_dir / "voice", fingerprint)
    log.info("Speech models ready")
    yield


app = FastAPI(title="ingpro", lifespan=lifespan)


def parse_topic_param(raw: str) -> int | None:
    """?topic=13 -> 13. Anything else (letters, superscripts, huge numbers) means no topic."""
    return int(raw) if raw.isascii() and raw.isdigit() and len(raw) <= 4 else None


def topic_focus(unit: int | None) -> dict | None:
    """The grammar unit a session is about (from the topic page's "Alex'le çalış"), or None."""
    if unit is None:
        return None
    topic = next((t for t in load_course()["topics"] if t["id"] == unit), None)
    card = load_lessons(settings.content_dir).get(unit)
    return {**topic, "lesson": card} if topic and card else topic


DEFAULT_INTERVIEW_FIELD = "office"


def build_system_prompt(
    scenario: str, mode: str, topic: dict | None = None, vocab_level: str = "A1", field: str = "", custom_prompt: str = ""
) -> str:
    prompts = settings.prompts_dir
    if scenario == "custom" and custom_prompt.strip():
        scenario_rules = custom_prompt.strip()
    else:
        scenarios = json.loads((prompts / "scenarios.json").read_text())
        entry = scenarios.get(scenario, scenarios["free"])
        scenario_rules = entry["prompt"]
        if scenario == "interview":
            scenario_rules = scenario_rules.format(field=field.strip() or DEFAULT_INTERVIEW_FIELD)
    mode_rules = (prompts / ("mode_teacher.md" if mode == "teacher" else "mode_flow.md")).read_text().strip()
    profile = settings.profile_path.read_text().strip() if settings.profile_path.is_file() else "An adult learner. Use their own interests for examples once you know them."
    return (prompts / "tutor.md").read_text().format(
        level="A2",
        learner_profile=profile,
        explain_rules=(prompts / "explain.md").read_text().strip(),
        focus_rules=(prompts / "focus.md").read_text().format(
            title=topic["title"], tr=topic.get("tr") or topic["title"], subtopics="; ".join(s["title"] for s in topic["subtopics"]), vocab_level=vocab_level,
            lesson_rules=lessons.prompt_rules(topic["lesson"]) if topic.get("lesson") else "",
        ).strip() if topic else "",
        mode_rules=mode_rules,
        scenario_rules=scenario_rules,
    )


@app.get("/api/scenarios")
async def scenarios() -> dict:
    return json.loads((settings.prompts_dir / "scenarios.json").read_text())


class ScenarioGenIn(BaseModel):
    description: str = Field(min_length=1, max_length=300)


@app.post("/api/scenarios/generate")
async def scenarios_generate(body: ScenarioGenIn) -> dict:
    try:
        gen = await generate_scenario(body.description, settings.tutor_model)
    except ScenarioGenError as exc:
        raise HTTPException(400, str(exc))
    return {"title": gen.title, "description": gen.description, "prompt": gen.prompt}


@app.get("/api/grammar")
async def grammar() -> dict:
    course = load_course()
    cards = load_lessons(settings.content_dir)
    return {**course, "topics": [{**t, "has_lesson": t["id"] in cards} for t in course["topics"]]}


@app.get("/api/grammar/lesson/{unit}")
async def grammar_lesson(unit: int) -> dict:
    card = load_lessons(settings.content_dir).get(unit)
    if not card:
        raise HTTPException(404, f"No lesson card for unit {unit}")
    return card


class ReviewIn(BaseModel):
    sub_id: str
    rating: int = Field(ge=1, le=4)  # 1 could not recall, 2 hard, 3 good, 4 easy
    confused_with: str | None = None


class ExposeIn(BaseModel):
    sub_id: str


@app.get("/api/brain/progress")
def brain_progress() -> dict:
    return brain.snapshot()


@app.post("/api/brain/review")
def brain_review(body: ReviewIn) -> dict:
    try:
        return brain.review(body.sub_id, body.rating, confused_with=body.confused_with)
    except UnknownNeuron:
        raise HTTPException(404, f"Unknown subtopic {body.sub_id}")


@app.post("/api/brain/expose")
def brain_expose(body: ExposeIn) -> dict:
    try:
        return brain.expose(body.sub_id)
    except UnknownNeuron:
        raise HTTPException(404, f"Unknown subtopic {body.sub_id}")


@app.get("/api/brain/unit/{unit}")
def brain_unit(unit: int) -> dict:
    try:
        return brain.unit_summary(unit)
    except UnknownUnit:
        raise HTTPException(404, f"Unknown unit {unit}")


@app.post("/api/brain/consolidate")
def brain_consolidate() -> dict:
    r = brain.consolidate()
    return {"decayed": r["decayed"], "pruned": len(r["pruned"]), "due": len(r["due"]), "at_risk": len(r["at_risk"])}


@app.get("/api/words/brain")
def words_brain() -> dict:
    return brain.word_network()


@app.get("/api/stats")
def stats() -> dict:
    return build_stats(brain, brain.clock())


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "stt_model": settings.stt_model, "tts_engine": settings.tts_engine, "tutor_model": settings.tutor_model}


@app.websocket("/ws/voice")
async def voice(ws: WebSocket) -> None:
    # A web page on another site must not be able to talk to the microphone pipeline or spend the Claude quota
    origin = ws.headers.get("origin")
    if origin and urlparse(origin).hostname not in LOCAL_HOSTS:
        await ws.close(code=1008)
        return
    await ws.accept()
    raw_topic = ws.query_params.get("topic", "")
    topic = topic_focus(parse_topic_param(raw_topic))
    scenario = ws.query_params.get("scenario", "free")
    field = ws.query_params.get("field", "")
    custom_prompt = ws.query_params.get("custom_prompt", "")
    system_prompt = build_system_prompt(scenario, ws.query_params.get("mode", "flow"), topic, brain.vocab_ceiling(), field, custom_prompt)
    chat = create_chat_session(settings.llm_provider, system_prompt, settings.tutor_model)
    session = VoiceSession(ws, chat, engines.stt, engines.tts, engines.stt_lock, engines.tts_lock, settings.tts_speed, engines.fillers,
                           topic=topic, brain=brain, judge=judge if topic else None, scenario=scenario)
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    finally:
        await session.close()


class WebFiles(StaticFiles):
    """The page itself must always be re-checked, otherwise a browser keeps showing the previous build after an update.
    (Its JS/CSS files have a content hash in the name, so they can't go stale.)"""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if getattr(response, "media_type", None) == "text/html":
            response.headers["Cache-Control"] = "no-cache"
        return response


# Production mode: serve the built frontend from the same port
if settings.web_dist.is_dir():
    app.mount("/", WebFiles(directory=settings.web_dist, html=True), name="web")


def run() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    uvicorn.run("ingpro.main:app", host=settings.host, port=settings.port)
