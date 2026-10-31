"""Story writing with Gemini. The script is a list of SHOTS (one sentence + optionally a new picture each),
so pictures and captions change with the narration. Progress is saved after every batch (resume-safe)."""
import json, os, re, time
from google import genai
from google.genai import types
from cast import ARCHETYPES, resolve_speaker
import lore

LANG = {"hindi": "Hindi (Devanagari script, simple spoken Hindi)", "english": "English (simple, warm, Indian-friendly)"}
_client = None


def ask(prompt, cfg, tries=16):
    """Call Gemini; on overload switch between the main and fallback model; stop early if quota is truly gone."""
    global _client
    _client = _client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    models = [cfg["gemini_model"]]
    if cfg.get("fallback_model") and cfg["fallback_model"] != cfg["gemini_model"]:
        models.append(cfg["fallback_model"])
    exhausted, waited_minute, i = set(), False, 0
    for attempt in range(tries):
        m = models[i % len(models)]
        try:
            r = _client.models.generate_content(
                model=m, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.9))
            data = json.loads(r.text)
            time.sleep(13)  # free tier allows about 5 requests/minute
            return data
        except Exception as e:
            msg = str(e)
            if "NOT_FOUND" in msg or "API key" in msg or "API_KEY" in msg:
                raise
            if "429" in msg:
                exhausted.add(m)
                if len(exhausted) >= len(models):
                    if waited_minute:
                        raise RuntimeError("Gemini quota used up on all models. The next scheduled run will resume.")
                    waited_minute = True
                    exhausted.clear()
                    print("  quota hit on all models; waiting 65s in case it is the per-minute limit")
                    time.sleep(65)
                else:
                    print(f"  {m} quota exhausted, switching model")
                i += 1
                continue
            print(f"  {m} problem (attempt {attempt + 1}/{tries}): {msg[:160]}")
            i += 1
            time.sleep(min(30 * (attempt + 1), 150))
    raise RuntimeError("Gemini failed repeatedly. Progress is saved; the next run resumes.")


DEV = re.compile("[\u0900-\u097F]")
MLANG = {
    "hinglish": "Hinglish: Hindi written in Roman (English) letters, natural and easy to read, for example 'Kanha ke munh mein poora brahmand?'",
    "english": "simple, engaging English",
}


def meta_lang(cfg):
    return MLANG.get(cfg.get("metadata_style", "hinglish"), MLANG["hinglish"])


def ensure_roman(outline, cfg):
    """Title, description and tags must be in Roman letters. Fixes them with one small Gemini request if needed. Returns True if changed."""
    parts = [outline.get("title", ""), outline.get("description", "")] + list(outline.get("tags") or [])
    if not any(DEV.search(str(p)) for p in parts):
        return False
    if not outline.get("title_display"):
        outline["title_display"] = outline.get("title", "")          # keep the Hindi title for the on-screen banner
    prompt = f"""Rewrite this YouTube title, description and tags in {meta_lang(cfg)}.
Use ONLY Roman letters (no Devanagari). Keep the meaning, the length and the hashtags.
Title: {outline.get('title')}
Description: {outline.get('description')}
Tags: {json.dumps(outline.get('tags') or [], ensure_ascii=False)}
Return JSON: {{"title": "...", "description": "...", "tags": ["..."]}}"""
    try:
        data = ask(prompt, cfg)
        if isinstance(data.get("title"), str) and isinstance(data.get("description"), str) \
                and not DEV.search(data["title"] + data["description"]):
            outline["title"], outline["description"] = data["title"].strip(), data["description"].strip()
            if isinstance(data.get("tags"), list):
                outline["tags"] = [str(t) for t in data["tags"] if not DEV.search(str(t))] or outline.get("tags", [])
            return True
    except Exception as e:
        print("  could not convert title/description to Roman letters:", str(e)[:120])
    return False


SAMPLE = {
    "hindi": """Style sample (for register only, never copy):
Narrator: यमुना के किनारे, गोकुल की गलियों में, एक नन्हा नीला बालक सबकी नज़रों से बचकर रसोई की ओर बढ़ रहा था।
Krishna: मैया, मैंने माखन नहीं खाया! ये तो ग्वाल-बालों ने मेरे मुँह पर लगा दिया!
Yashoda: अच्छा? तो ज़रा मुँह खोल, कान्हा।""",
    "english": """Style sample (for register only, never copy):
Narrator: Along the Yamuna, in the lanes of Gokul, a tiny blue child was tiptoeing towards the kitchen.
Krishna: Maiya, I did not eat the butter! The cowherd boys smeared it on my face!
Yashoda: Is that so? Then open your mouth, Kanha.""",
}


def make_outline(cfg, category, topic):
    ARCH = " / ".join(ARCHETYPES)
    n = cfg["scenes"]
    prompt = f"""You are a celebrated storyteller and screenwriter of devotional animated films: the emotional warmth of Amar Chitra Katha meets a Pixar short. Plan a {cfg['target_minutes']}-minute narrated animated video that people will love, watch to the end and share.
Category (deity): {category}
Story: {topic or 'choose a beloved, well-known story of this deity from the Puranas or epics'}
Narration language: {LANG[cfg['language']]}

Source fidelity: follow the traditional scriptures and puranas (Bhagavata Purana, Shiva Purana, Valmiki Ramayana, Devi Mahatmya, Mahabharata). Never invent miracles that contradict the tradition; small emotional and dialogue details are welcome. Show every deity with deep reverence, never mocking.

Return JSON with exactly these keys:
- title: the YouTube title, curiosity-driven, under 70 characters, written in {meta_lang(cfg)} using ONLY Roman letters (a question or a surprising promise, no clickbait lies)
- title_display: the same title written in the narration language script, shown on screen in the video
- hook: the single opening line that grabs attention in the first 5 seconds (a dramatic moment or a question)
- theme: the one emotional truth or moral of the story, in one sentence
- description: 150-250 words, SEO friendly, written in {meta_lang(cfg)} using ONLY Roman letters, ending with 5 hashtags
- tags: list of 12 short strings in Roman letters (e.g. "krishna katha", "hindu mythology stories", "krishna ki kahani")
- characters: object mapping each main character's ENGLISH name (e.g. "Krishna", "Yashoda", "Indra"; at most 6, deities by their plain names) to ONE sentence describing their look (English, 3D animation style)
- display_names: the SAME English names mapped to the name written in the narration language script (as shown on screen)
- cast: the SAME English names mapped to {{"voice": one of {ARCH}}}
- personalities: the SAME English names mapped to a short description of how that character TALKS and behaves (e.g. "playful, teasing, calls his mother Maiya")
- scenes: a list of exactly {n} objects, each {{"purpose": "what this scene does emotionally", "beat": "what happens (1-2 sentences, English)", "hook": "a one-line open question or surprise that makes viewers stay"}}

Story shape for the scenes: (1) gripping hook, then (2) the world and the deity's nature, (3) the problem or conflict arrives, then rising tension and escalation, a darkest moment, the divine intervention and climax, the resolution, and finally the moral with a blessing. Every scene must change something: new information, a decision, or a surprise."""
    for _ in range(3):
        data = ask(prompt, cfg)
        if isinstance(data.get("scenes"), list) and len(data["scenes"]) >= 4 and data.get("title"):
            chars = data.get("characters") if isinstance(data.get("characters"), dict) else {}
            cast = data.get("cast") if isinstance(data.get("cast"), dict) else {}
            data["characters"] = {k: lore.canonical_look(k, str(v)) for k, v in chars.items()}   # accurate deity iconography
            data["cast"] = {k: {"voice": (cast.get(k) or {}).get("voice") if (cast.get(k) or {}).get("voice") in ARCHETYPES else "young_hero"} for k in chars}
            dn = data.get("display_names") if isinstance(data.get("display_names"), dict) else {}
            data["display_names"] = {k: str(dn.get(k) or k) for k in chars}
            data["personalities"] = data.get("personalities") if isinstance(data.get("personalities"), dict) else {}
            data.setdefault("title_display", data.get("title", ""))
            ensure_roman(data, cfg)
            return data
        print("  outline looked incomplete, asking again")
    raise RuntimeError("Could not get a valid outline")


def write_scenes(cfg, outline, workdir):
    part = workdir / "scenes_partial.json"
    scenes, n = outline["scenes"], len(outline["scenes"])
    S = cfg["shots_per_scene"]
    wps = max(8, int(cfg["target_minutes"] * cfg["words_per_minute"] / (n * S)))
    batch = cfg["scenes_per_call"]
    saved = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {"out": [], "recap": "", "last": ""}
    out, recap, last_lines = saved["out"], saved["recap"], saved.get("last", "")
    if out:
        print(f"  resuming: {len(out)}/{n} scenes already written")
    bible = json.dumps({"theme": outline.get("theme"), "characters": list(outline["characters"].keys()),
                        "how_they_speak": outline.get("personalities", {})}, ensure_ascii=False)
    deity = outline["title"]
    for start in range(len(out), n, batch):
        chunk = scenes[start:start + batch]
        beats = "\n".join(f"Scene {start + i + 1}: purpose: {s.get('purpose', '')} | what happens: {s['beat']} | end-of-scene hook: {s.get('hook', '')}"
                          for i, s in enumerate(chunk))
        first, last = start == 0, start + batch >= n
        prompt = f"""Write scenes {start + 1} to {start + len(chunk)} of {n} of a narrated animated mythology film.
Narration language: {LANG[cfg['language']]}
Title: {deity}
Opening hook line (use its idea in the very first shot): {outline.get('hook', '')}
Story bible: {bible}
Story so far: {recap or '(nothing yet)'}
Last lines already spoken: {last_lines or '(none)'}
Scenes to write:
{beats}

Each scene is a list of exactly {S} SHOTS. A shot is ONE spoken sentence of about {wps} words, said by ONE speaker, plus the picture shown while it is spoken.
- speaker: "Narrator" or the exact ENGLISH name of a character from the story bible. About half of the shots are DIALOGUE in first person (no quotation marks, no "he said"); the Narrator links the story between dialogues.

SCREENPLAY CRAFT (this is what makes people love it):
- Make viewers FEEL: show reactions, small gestures, wonder, fear, laughter and tears. Use concrete sensory details instead of abstract praise.
- Dialogue sounds like real people talking, not a lecture: short, emotional, in each character's own way of speaking (see how_they_speak). Characters react to each other (questions, teasing, interruptions). Gods speak with warmth and calm authority, children with playful curiosity, demons with arrogance and rage.
- The Narrator is a vivid, flowing, slightly poetic storyteller. He never explains what the dialogue already showed.
- Every scene moves the story forward. Never repeat an idea. Vary sentence length and never start consecutive shots with the same word.
- End each scene on its end-of-scene hook (except the last scene), so viewers want the next scene.
- Natural, melodic, spoken language, simple words; traditional words ("प्रभु", "मैया", "हे नारायण") only where they fit; do not mix English words into Hindi.
- Faithful to the scriptures; reverent toward every deity.
{'- The very first shot is a powerful hook that makes people keep watching.' if first else ''}{'- The last shots: the moral in one warm line, then a short devotional blessing naming the deity (for example "जय श्री कृष्ण"), then a friendly request to like, share and subscribe for more divine stories.' if last else ''}
- image_prompt: an English, cinematic description of what the viewer SEES (subject, action, setting, light, camera angle). For a dialogue shot show THAT character in a medium or close shot, face clearly visible, with a clear emotion. Give a NEW image_prompt only when the picture should change, roughly every second shot; use null when the previous picture still fits (the video then keeps the picture with a new camera move). The first shot of every scene MUST have an image_prompt. Name the characters in the picture by their English names. Never include text or letters in the picture.

{SAMPLE[cfg['language']]}

Return JSON: {{"scenes": [{{"shots": [{{"speaker": "...", "narration": "...", "image_prompt": "..." or null}}]}}], "summary": "2-3 sentence recap of these scenes"}}
The scenes list must contain exactly {len(chunk)} items."""
        for _ in range(3):
            data = ask(prompt, cfg)
            sc = data.get("scenes")
            ok = isinstance(sc, list) and len(sc) == len(chunk) and all(
                isinstance(s.get("shots"), list) and len(s["shots"]) >= 4 and
                all(isinstance(x.get("narration"), str) and len(x["narration"].strip()) > 8 for x in s["shots"]) for s in sc)
            if ok:
                break
            print("  batch came back malformed, asking again")
        else:
            raise RuntimeError("Gemini returned malformed scenes 3 times")
        for s, b in zip(sc, chunk):
            shots = []
            for x in s["shots"]:
                p = x.get("image_prompt")
                shots.append({"speaker": resolve_speaker(str(x.get("speaker", "")), outline), "narration": x["narration"].strip(),
                              "image_prompt": p.strip() if isinstance(p, str) and p.strip() else None})
            if not shots[0]["image_prompt"]:  # every scene starts on a fresh picture
                shots[0]["image_prompt"] = f"{outline['title']}. {b['beat']}"
            out.append({"shots": shots})
        recap = (recap + " " + str(data.get("summary", "")))[-1500:]
        last_lines = " / ".join(x["narration"] for x in out[-1]["shots"][-2:])
        part.write_text(json.dumps({"out": out, "recap": recap, "last": last_lines}, ensure_ascii=False), encoding="utf-8")
        print(f"  scenes {start + 1}-{start + len(chunk)} of {n} written")
    return out
