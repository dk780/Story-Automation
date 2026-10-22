"""Story writing with the Gemini free tier: outline first, then scene by scene (keeps 20-30 min coherent)."""
import json, os, time
from google import genai
from google.genai import types

LANG = {"hindi": "Hindi (Devanagari script, simple spoken Hindi)", "english": "English (simple, warm, Indian-friendly)"}
_client = None


def ask(prompt, model, tries=6):
    global _client
    _client = _client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    for attempt in range(tries):
        try:
            r = _client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.9))
            time.sleep(7)  # stay under the free-tier requests-per-minute limit
            return json.loads(r.text)
        except Exception as e:
            print(f"  Gemini retry {attempt + 1}: {e}")
            time.sleep(20 * (attempt + 1))
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
    k = cfg["images_per_scene"]
    recap, out = [], []
    for i, sc in enumerate(scenes):
        nxt = scenes[i + 1]["beat"] if i + 1 < n else "(this is the final scene)"
        prompt = f"""Write scene {i + 1} of {n} of a narrated story.
Narration language: {LANG[cfg['language']]}
Title: {outline['title']}
Characters (fixed looks): {json.dumps(outline['characters'], ensure_ascii=False)}
Story so far: {' '.join(recap[-3:]) or '(nothing yet)'}
This scene: {sc['beat']}
Next scene: {nxt}

Write about {words} words of pure spoken narration: vivid, emotional, short sentences that sound natural in text-to-speech.
No headings, stage directions, emojis or markdown.
{'Open with a powerful hook.' if i == 0 else ''}{' End with the moral and a warm invitation to subscribe.' if i == n - 1 else ''}
Also write {k} image_prompts in English: concrete cinematic descriptions of what is on screen during the narration.
Restate the look of every character present. Never include text or letters in the image.
Return JSON: {{"narration": "...", "image_prompts": ["..."], "summary": "one-sentence recap"}}"""
        data = ask(prompt, cfg["gemini_model"])
        recap.append(data["summary"])
        out.append({"narration": data["narration"].strip(), "image_prompts": data["image_prompts"][:k]})
        print(f"  scene {i + 1}/{n} written ({len(data['narration'].split())} words)")
    return out
