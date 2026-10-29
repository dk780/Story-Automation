"""Story writing with Gemini. The script is a list of SHOTS (one sentence + optionally a new picture each),
so pictures and captions change with the narration. Progress is saved after every batch (resume-safe)."""
import json, os, time
from google import genai
from google.genai import types

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


def make_outline(cfg, category, topic):
    prompt = f"""You are a master storyteller planning a {cfg['target_minutes']}-minute narrated YouTube video.
Category: {category}
Story: {topic or 'choose a fresh, lesser-known story from this category'}
Narration language: {LANG[cfg['language']]}

Return JSON with exactly these keys:
- title: catchy, under 70 characters, in the narration language
- description: 150-250 words, SEO friendly, ending with 5 relevant hashtags
- tags: list of 12 short strings
- characters: object mapping each main character name to ONE sentence describing their fixed look (English, for an image generator)
- scenes: list of exactly {cfg['scenes']} objects, each {{"beat": "1-2 sentence summary of what happens"}} (English)

Rules: scene 1 opens with a gripping hook; build tension to a climax around 80% of the story; end with a meaningful moral.
Stay faithful and respectful to the source tradition. For superhero stories invent ORIGINAL characters, never Marvel/DC ones."""
    for _ in range(3):
        data = ask(prompt, cfg)
        if isinstance(data.get("scenes"), list) and len(data["scenes"]) >= 4 and data.get("title"):
            return data
        print("  outline looked incomplete, asking again")
    raise RuntimeError("Could not get a valid outline")


def write_scenes(cfg, outline, workdir):
    part = workdir / "scenes_partial.json"
    scenes, n = outline["scenes"], len(outline["scenes"])
    S = cfg["shots_per_scene"]
    wps = max(8, int(cfg["target_minutes"] * cfg["words_per_minute"] / (n * S)))
    batch = cfg["scenes_per_call"]
    saved = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {"out": [], "recap": ""}
    out, recap = saved["out"], saved["recap"]
    if out:
        print(f"  resuming: {len(out)}/{n} scenes already written")
    for start in range(len(out), n, batch):
        chunk = scenes[start:start + batch]
        beats = "\n".join(f"Scene {start + i + 1}: {s['beat']}" for i, s in enumerate(chunk))
        first, last = start == 0, start + batch >= n
        prompt = f"""Write scenes {start + 1} to {start + len(chunk)} of {n} of a narrated story video.
Narration language: {LANG[cfg['language']]}
Title: {outline['title']}
Characters (fixed looks): {json.dumps(outline['characters'], ensure_ascii=False)}
Story so far: {recap or '(nothing yet)'}
Scenes to write:
{beats}

Each scene is a list of exactly {S} SHOTS. A shot is ONE spoken sentence of about {wps} words, plus the picture shown while it is spoken.
- Together the shots of a scene tell that scene's events in order as flowing narration, with no repetition.
- Vivid, emotional, short sentences that sound natural in text-to-speech. No headings, emojis, markdown or stage directions.
- image_prompt: an English, cinematic description of what the viewer SEES (subject, action, setting, light, camera angle). Give a NEW image_prompt only when the picture should change, roughly every second shot. Use null when the previous picture still fits; the video then shows the same picture with a new camera move.
- The first shot of every scene MUST have an image_prompt. Restate the look of every character in frame. Never include text or letters in the picture.
{'- The very first shot must be a powerful hook that makes people keep watching.' if first else ''}{'- The final scene must end with the moral and a warm invitation to subscribe.' if last else ''}
Return JSON: {{"scenes": [{{"shots": [{{"narration": "...", "image_prompt": "..." or null}}]}}], "summary": "2-3 sentence recap of these scenes"}}
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
                shots.append({"narration": x["narration"].strip(), "image_prompt": p.strip() if isinstance(p, str) and p.strip() else None})
            if not shots[0]["image_prompt"]:  # every scene starts on a fresh picture
                shots[0]["image_prompt"] = f"{outline['title']}. {b['beat']}"
            out.append({"shots": shots})
        recap = (recap + " " + str(data.get("summary", "")))[-1500:]
        part.write_text(json.dumps({"out": out, "recap": recap}, ensure_ascii=False), encoding="utf-8")
        print(f"  scenes {start + 1}-{start + len(chunk)} of {n} written")
    return out
