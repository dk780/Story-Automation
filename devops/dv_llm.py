"""Gemini (free tier) with overload / quota handling and a fallback model."""
import json, os, time
from google import genai
from google.genai import types

_client = None


def ask(prompt, cfg, tries=14):
    global _client
    _client = _client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    models = [cfg["gemini_model"]] + ([cfg["fallback_model"]] if cfg.get("fallback_model") and cfg["fallback_model"] != cfg["gemini_model"] else [])
    exhausted, waited, i = set(), False, 0
    for attempt in range(tries):
        m = models[i % len(models)]
        try:
            r = _client.models.generate_content(model=m, contents=prompt,
                                                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7))
            data = json.loads(r.text)
            time.sleep(13)
            return data
        except Exception as e:
            msg = str(e)
            if "NOT_FOUND" in msg or "API key" in msg or "API_KEY" in msg:
                raise
            if "429" in msg:
                exhausted.add(m)
                if len(exhausted) >= len(models):
                    if waited:
                        raise RuntimeError("Gemini quota used up on all models. The next scheduled run will resume.")
                    waited = True; exhausted.clear()
                    print("  quota hit on all models; waiting 65s"); time.sleep(65)
                else:
                    print(f"  {m} quota exhausted, switching model")
                i += 1
                continue
            print(f"  {m} problem (attempt {attempt + 1}/{tries}): {msg[:150]}")
            i += 1
            time.sleep(min(30 * (attempt + 1), 150))
    raise RuntimeError("Gemini failed repeatedly. Progress is saved; the next run resumes.")
