"""Story writing with the Gemini free tier: outline first, then scene by scene (keeps 20-30 min coherent)."""
import json, os, time
import yaml
from google import genai
from google.genai import types

LANG = {"hindi": "Hindi (Devanagari script, simple spoken Hindi)", "english": "English (simple, warm, Indian-friendly)"}
_client = None


def ask(prompt, model, tries=8):
    global _client
    _client = _client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    fb = yaml.safe_load(open("config.yaml", encoding="utf-8")).get("fallback_model")
    models = [model] + ([fb] if fb and fb != model else [])
    exhausted, waited_minute, i = set(), False, 0
    for attempt in range(tries):
        m = models[i % len(models)]
        try:
            r = _client.models.generate_content(
                model=m, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.9))
            time.sleep(13)  # your limit is 5 requests/minute
            return json.loads(r.text)
        except Exception as e:
            msg = str(e)
            if "NOT_FOUND" in msg or "API key" in msg:
                raise
            if "429" in msg:  # quota: try the other model, which has its own limit
                exhausted.add(m)
                if len(exhausted) >= len(models):
                    if waited_minute:
                        raise RuntimeError("Gemini quota used up on all models. Try after the daily reset.")
                    waited_minute = True
                    exhausted.clear()
                    print("  quota hit on all models, waiting 65s in case it is the per-minute limit")
                    time.sleep(65)
                else:
                    print(f"  {m} quota exhausted, switching model")
                i += 1
                continue
            print(f"  {m} overloaded (attempt {attempt + 1}/{tries}): {msg[:200]}")
            i += 1  # switch model on every overload
            time.sleep(min(20 * (attempt + 1), 90))
    raise RuntimeError("Gemini failed repeatedly")


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
    return ask(prompt, cfg["gemini_model"])


def write_scenes(cfg, outline):
    scenes, n = outline["scenes"], len(outline["scenes"])
    words = int(cfg["target_minutes"] * cfg["words_per_minute"] / n)
    k, batch = cfg["images_per_scene"], cfg.get("scenes_per_call", 4)
    recap, out = "", []
    for start in range(0, n, batch):
        chunk = scenes[start:start + batch]
        beats = "\n".join(f"Scene {start + i + 1}: {s['beat']}" for i, s in enumerate(chunk))
        first, last = start == 0, start + batch >= n
        prompt = f"""Write scenes {start + 1} to {start + len(chunk)} of {n} of a narrated story.
Narration language: {LANG[cfg['language']]}
Title: {outline['title']}
Characters (fixed looks): {json.dumps(outline['characters'], ensure_ascii=False)}
Story so far: {recap or '(nothing yet)'}
Scenes to write:
{beats}

For EACH scene write about {words} words of pure spoken narration: vivid, emotional, short sentences that sound natural in text-to-speech. No headings, stage directions, emojis or markdown.
{'Scene 1 must open with a powerful hook.' if first else ''}{' The final scene must end with the moral and a warm invitation to subscribe.' if last else ''}
For each scene also write {k} image_prompts in English: concrete cinematic descriptions of what is on screen. Restate the look of every character present. Never include text or letters in the image.
Return JSON: {{"scenes": [{{"narration": "...", "image_prompts": ["..."]}}], "summary": "2-3 sentence recap of these scenes"}}
The scenes list must contain exactly {len(chunk)} items."""
        data = ask(prompt, cfg["gemini_model"])
        if len(data["scenes"]) != len(chunk):
            raise RuntimeError("Gemini returned the wrong number of scenes")
        for s in data["scenes"]:
            out.append({"narration": s["narration"].strip(), "image_prompts": s["image_prompts"][:k]})
        recap = (recap + " " + data["summary"])[-1500:]
        print(f"  scenes {start + 1}-{start + len(chunk)} of {n} written")
    return out
