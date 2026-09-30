"""Cheap en/tr language guess for typed text and for routing a spoken sentence to the right TTS voice."""

import re

_TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
_TR_WORDS = {
    "ve", "bir", "bu", "şu", "için", "ne", "ben", "sen", "biz", "çok", "değil", "evet", "hayır", "merhaba",
    "nasıl", "ama", "ile", "gibi", "var", "yok", "mi", "mı", "mu", "mü", "da", "de", "ki", "bunu", "şunu",
    "bana", "sana", "olarak", "daha", "en", "her", "kadar", "sonra", "önce", "şey", "neden", "nerede", "bugün",
    "dün", "yarın", "lütfen", "teşekkürler", "tamam", "iyi", "güzel", "söylerim", "yapmak", "istiyorum",
    "nedir", "neyi", "niye", "kim", "hangi", "gramer", "hala", "hâlâ", "anlat", "açıkla", "fark", "farkı", "yanlış", "doğru",
    "peki", "yani", "işte", "böyle", "şöyle", "öyle", "mesela", "örnek", "cümle", "kelime", "anlamı", "demek",
}
# Endings that are very Turkish and rare on English words: "nedir", "yapıyor", "olmuş"
_TR_SUFFIX = re.compile(r"\w{3,}(?:dir|dır|dür|[ıiuü]yor(?:um|sun)?|miş|mış|muş|müş)$")
_EN_WORDS = {
    "the", "is", "are", "was", "were", "i", "you", "he", "she", "it", "we", "they", "to", "and", "of", "in",
    "that", "have", "has", "my", "your", "what", "how", "do", "does", "did", "not", "with", "for", "on", "at",
    "this", "but", "so", "be", "can", "will", "would", "yes", "no", "hello", "hi", "please", "thanks", "just",
}
_WORD = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü']+")


def detect_lang(text: str, default: str = "en") -> str:
    """Returns 'tr' or 'en'. Falls back to `default` when the text is too short/ambiguous to tell."""
    if any(ch in _TR_CHARS for ch in text):
        return "tr"
    words = [w.lower() for w in _WORD.findall(text)]
    tr = sum(w in _TR_WORDS or bool(_TR_SUFFIX.fullmatch(w)) for w in words)
    en = sum(w in _EN_WORDS for w in words)
    if tr > en:
        return "tr"
    if en > tr:
        return "en"
    return default


_QUOTED = re.compile(r'(["“„«‘][^"”“»’]{2,}?["”»’])')


def split_by_language(text: str, default: str = "en") -> list[tuple[str, str]]:
    """Splits e.g. 'İngilizcesi "My computer keeps freezing" demek.' into Turkish and English runs,
    so each run can be spoken with the right pronunciation. Text without quotes stays one run."""
    parts = [p for p in _QUOTED.split(text) if p.strip()]
    if len(parts) == 1:
        return [(detect_lang(text, default), text)]
    runs: list[tuple[str, str]] = []
    for part in parts:
        lang = detect_lang(part.strip("\"“”„«»‘’"), default)
        # A quote spoken in the same language as the sentence keeps the sentence language
        if runs and runs[-1][0] == lang:
            runs[-1] = (lang, runs[-1][1] + part)
        else:
            runs.append((lang, part))
    return runs
