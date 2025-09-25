import unicodedata
from typing import Dict, Iterable, Tuple

from django.conf import settings


def get_base_language() -> str:
    """Return the base language configured in settings (defaults to 'en')."""
    code = (
        getattr(settings, "RANKED_SEARCH_LANGUAGE", None)
        or getattr(settings, "HAYSTACK_LANGUAGE", None)
        or getattr(settings, "LANGUAGE_CODE", "en")
    )
    base = str(code or "en").split("-")[0].split("_")[0].lower() or "en"
    return base


def _merge_profile(base_lang: str) -> Tuple[Iterable[str], Dict[str, str]]:
    """Combine the default and language-specific folding profile."""
    prof = getattr(settings, "RANKED_SEARCH_FOLDING_PROFILE", {}) or {}
    default = prof.get("default", {}) or {}
    lang = prof.get(base_lang, {}) or {}

    preserve = set(default.get("preserve", []) or [])
    preserve |= set(lang.get("preserve", []) or [])
    replace = dict(default.get("replace", {}) or {})
    replace.update(lang.get("replace", {}) or {})

    # Optional overrides
    keep_enye = getattr(settings, "RANKED_SEARCH_KEEP_ENYE", None)
    if keep_enye is True:
        preserve.update({"ñ", "Ñ"})
    elif keep_enye is False:
        preserve.difference_update({"ñ", "Ñ"})

    return preserve, replace


def build_charset_map(base_lang: str):
    """Build the whoosh charset map based on the configured profile."""
    from whoosh.support.charset import accent_map

    preserve, replace = _merge_profile(base_lang)
    cmap = dict(accent_map)

    for ch in preserve:
        cmap[ord(ch)] = ch

    for src, dst in replace.items():
        if not src:
            continue
        cmap[ord(src)] = dst or ""

    return cmap


def normalize_text(s: str, base_lang: str = None) -> str:
    """Normalize text to fold accents while honoring the language profile."""
    if not s:
        return ""

    base_lang = base_lang or get_base_language()
    preserve, replace = _merge_profile(base_lang)

    text = s.lower()

    # Apply replacements first (e.g., ß->ss, œ->oe)
    if replace:
        for src, dst in replace.items():
            if src:
                text = text.replace(src.lower(), (dst or "").lower())

    if preserve:
        # Assign deterministic placeholders for each preserved character
        # Use private use area to avoid collisions
        placeholders = {
            ch.lower(): chr(0xE000 + idx)
            for idx, ch in enumerate(sorted(preserve))
        }
        for ch, ph in placeholders.items():
            text = text.replace(ch, ph)
    else:
        placeholders = {}

    # Decompose and remove combining marks
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = unicodedata.normalize("NFC", text)

    # Restore preserved characters
    for ch, ph in placeholders.items():
        text = text.replace(ph, ch)

    return text
