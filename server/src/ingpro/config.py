from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGPRO_", env_file=REPO_ROOT / ".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8765

    # STT — multilingual small ~0.6s per utterance on M4 (English + Turkish); large-v3-turbo is more accurate but ~2.7s
    stt_model: str = "mlx-community/whisper-small-mlx"
    # TTS engine: "chatterbox" = one cloned voice for English and Turkish (default);
    # "classic" = Kokoro (English) + a separate Turkish voice (lighter, but two different speakers)
    tts_engine: str = "chatterbox"
    chatterbox_model: str = "mlx-community/chatterbox-multilingual-v3"
    chatterbox_steps: int = 5  # flow-matching steps: 10 = best quality, 5 = 2x faster, 3 = audible degradation
    voice_ref: Path = REPO_ROOT / "data" / "voice" / "alex_ref.wav"
    # Classic engine only. Kokoro (female) for English. Turkish: "auto" = macOS built-in Yelda (female, natural) on a Mac,
    # otherwise Piper (open source, but its only Turkish voice is male and rather robotic)
    tts_voice: str = "af_heart"
    tts_speed: float = 0.9
    tts_tr_engine: str = "auto"  # auto | macos | piper
    piper_tr_model: Path = REPO_ROOT / "data" / "models" / "piper" / "tr_TR-dfki-medium.onnx"

    # Short spoken reactions ("Hmm, I see.") played right after the user stops talking, while the LLM thinks
    fillers: bool = True

    # LLM
    llm_provider: str = "claude_code"
    tutor_model: str = "claude-sonnet-5"
    # The judge scores the learner's spoken sentences (grammar, vocabulary) for the speaking points; runs in the background
    judge_model: str = "claude-sonnet-5"

    prompts_dir: Path = REPO_ROOT / "prompts"
    # Free-form notes about the learner (name, interests, how they like things explained). Kept out of git (data/).
    profile_path: Path = REPO_ROOT / "data" / "profile.md"
    content_dir: Path = REPO_ROOT / "content"
    data_dir: Path = REPO_ROOT / "data"
    web_dist: Path = REPO_ROOT / "web" / "dist"
    vault_dir: Path | None = None


settings = Settings()
