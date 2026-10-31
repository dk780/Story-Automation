"""Who is speaking: maps story characters to voice profiles (voice, pitch, speed, effect) and caption colours."""
ARCHETYPES = ["young_hero", "elder_sage", "villain", "god", "woman", "queen", "child", "animal"]
NARRATOR_NAMES = {"narrator", "सूत्रधार", "कथावाचक", "narration", ""}
COLORS = [(255, 170, 60), (90, 200, 255), (255, 100, 110), (150, 230, 120), (210, 150, 255), (255, 215, 90), (120, 235, 215)]


def is_narrator(speaker):
    return (speaker or "").strip().lower() in NARRATOR_NAMES


def resolve_speaker(speaker, outline):
    """Return the exact character name from the cast, or 'Narrator'."""
    if is_narrator(speaker):
        return "Narrator"
    names = list((outline.get("cast") or {}).keys())
    s = speaker.strip()
    for n in names:
        if n == s or n.lower() == s.lower():
            return n
    for n, shown in (outline.get("display_names") or {}).items():   # speaker written in Devanagari
        if shown.strip() == s:
            return n
    for n in names:  # partial match ("Baby Hanuman" vs "Hanuman")
        if n.lower() in s.lower() or s.lower() in n.lower():
            return n
    return "Narrator"


def profile(speaker, outline, cfg):
    """-> dict(voice, rate, pitch, fx) for this speaker"""
    table = cfg["voices"][cfg["language"]]
    if is_narrator(speaker):
        return table["narrator"]
    arch = ((outline.get("cast") or {}).get(speaker) or {}).get("voice")
    return table.get(arch) or table["young_hero"]


def color(speaker, outline):
    names = list((outline.get("cast") or {}).keys())
    return COLORS[names.index(speaker) % len(COLORS)] if speaker in names else COLORS[0]
