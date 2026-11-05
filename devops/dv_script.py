"""Writes the episode script with Gemini: one structured JSON (scenes with layouts), then a technical-accuracy review pass."""
import json, re
from dv_llm import ask

EMOJI_HINT = ("🧑‍💻 developer, 💻 laptop/code, 🛠️ tools, ⚙️ gear/automation, 🔧 config, 📦 package/artifact, 🐳 Docker, ☸️ Kubernetes, ☁️ cloud, 🗄️ database/storage, "
              "🖥️ server, 🔒 security, 🔑 key/secret, 🛡️ protection, 🐞 bug, 🧪 test, ✅ pass, ❌ fail, 🚀 deploy/release, 🔄 loop/continuous, ♾️ DevOps, 📊 metrics/dashboard, "
              "📈 growth, 🔔 alert, 📡 monitoring, 🔍 search/inspect, 📝 plan/notes, 📋 checklist, 🧱 wall/silo, 🏗️ build, 🔀 branch/merge, 🌿 branch, ⏱️ speed/time, 💡 idea, "
              "🤝 collaboration, 👥 team, 📜 logs/script, 🧩 module/plugin, 🌐 network/web, ⚖️ load balancing, 🚦 traffic control, 🔥 firewall, 📁 folder/repo, 🧰 toolbox, "
              "🎯 goal, 🏁 finish, 🤖 automation/bot, 📚 docs, 🧠 knowledge, 🐙 GitHub, 📤 upload, 📥 download, ⏳ waiting, 💰 cost, 🏢 company, 🔁 repeat, 🧯 incident, 🎛️ control panel")
LAYOUTS = {"definition", "icons", "flow", "compare", "cycle", "list", "stack", "code", "quiz"}


def _s(x, n=200):
    return re.sub(r"\s+", " ", str(x or "")).strip()[:n]


def _items(raw, lo, hi):
    out = []
    for it in (raw if isinstance(raw, list) else []):
        if isinstance(it, dict) and (it.get("label") or it.get("logo")):
            out.append({"label": _s(it.get("label") or it.get("logo"), 40), "emoji": _s(it.get("emoji"), 12) or "🔹", "cue": _s(it.get("cue"), 40),
                        "detail": _s(it.get("detail"), 70), "logo": _s(it.get("logo"), 30)})
    return out[:hi] if len(out) >= lo else None


def normalize_scene(sc):
    """Return a clean scene dict, or None when it cannot be used."""
    if not isinstance(sc, dict) or len(_s(sc.get("narration"), 2000)) < 40:
        return None
    lay = "icons" if sc.get("layout") == "tools" else (sc.get("layout") if sc.get("layout") in LAYOUTS else "list")
    out = {"layout": lay, "heading": _s(sc.get("heading"), 60) or "Key idea", "narration": _s(sc["narration"], 1500)}
    if lay == "definition":
        if not sc.get("term") or not sc.get("text"):
            return None
        out.update(term=_s(sc["term"], 30), text=_s(sc["text"], 110), emoji=_s(sc.get("emoji"), 12) or "💡", text_cue=_s(sc.get("text_cue"), 40), logo=_s(sc.get("logo"), 30))
    elif lay in ("icons", "flow", "cycle", "list", "stack"):
        lo, hi = {"icons": (2, 6), "flow": (3, 6), "cycle": (4, 8), "list": (3, 5), "stack": (3, 5)}[lay]
        items = _items(sc.get("items"), lo, hi)
        if not items:
            return None
        out["items"] = items
        if lay == "cycle":
            out["center"] = _s(sc.get("center"), 24)
    elif lay == "compare":
        sides = {}
        for k in ("left", "right"):
            d = sc.get(k)
            if not isinstance(d, dict) or not d.get("title") or not isinstance(d.get("points"), list) or len(d["points"]) < 2:
                return None
            sides[k] = {"title": _s(d["title"], 24), "emoji": _s(d.get("emoji"), 12) or "🔹", "style": d.get("style") if d.get("style") in ("bad", "good") else "neutral",
                        "points": [_s(p, 44) for p in d["points"][:4]]}
        out.update(sides)
    elif lay == "code":
        lines = [_s(l, 50) for l in (sc.get("lines") or []) if str(l).strip()][:8]
        if len(lines) < 2:
            return None
        out.update(lines=lines, caption=_s(sc.get("caption"), 70))
    elif lay == "quiz":
        opts = [_s(o, 44) for o in (sc.get("options") or [])][:4]
        try:
            ans = int(sc.get("answer"))
        except Exception:
            return None
        if len(opts) != 4 or not (0 <= ans < 4) or not sc.get("question"):
            return None
        out.update(question=_s(sc["question"], 110), options=opts, answer=ans)
    return out


def generate(cfg, ep, next_ep):
    words = int(cfg["target_minutes"] * cfg["words_per_minute"] / cfg["scenes"])
    lang = "English" if cfg["language"] == "english" else "Hindi (Devanagari script), keeping common technical words such as Docker, Kubernetes, pipeline, commit in English"
    prompt = f"""You are a senior DevOps engineer and a gifted teacher. Write the script of a {cfg['target_minutes']}-minute animated whiteboard explainer video for beginners (clean flat icons, handwritten text, arrows that draw themselves, a quiz at the end), part of a series called "{cfg['series_name']}".
Episode {ep['n']}: {ep['title']}   (level: {ep.get('level', 'beginner')})
Key points to cover: {ep.get('points', '')}
Next episode (for the outro): {next_ep['title'] if next_ep else 'more DevOps topics'}
Narration language: {lang}. ALL on-screen text is English.

Accuracy: be technically correct and current. Use the real, correctly spelled names of tools and concepts. Do not invent facts, numbers or company claims. Prefer one simple real-world analogy over jargon.

Return JSON with exactly these keys:
- title: YouTube title under 70 chars, e.g. "{ep['title']} Explained | DevOps Tutorial for Beginners | Ep {ep['n']}"
- description: 150-220 words, English, plain text, ending with 5 hashtags (do NOT include chapters, they are added automatically)
- tags: 12 short strings
- thumbnail_text: 2-4 words
- intro_narration: 1-2 spoken sentences welcoming viewers to the DevOps series, episode {ep['n']}, and what they will learn
- outro_narration: 2-3 spoken sentences: a one-line recap, a teaser of the next episode, and a friendly ask to like, share and subscribe
- scenes: EXACTLY {cfg['scenes']} scene objects

Every scene has: "heading" (max 6 words, shown on screen), "narration" (about {words} words of natural, conversational spoken English, short sentences, no lists or markdown), and "layout" plus the fields of that layout:
- "definition": "term", "text" (max 14 words), "emoji", "text_cue"
- "icons": "items": 2-6 of {{"label" (max 3 words), "emoji", "cue"}}
- "flow": "items": 3-6 of {{"label", "emoji", "cue"}} (steps left to right)
- "cycle": "items": 4-8 of {{"label", "emoji", "cue"}} (a loop), "center" (short word)
- "list": "items": 3-5 of {{"label" (max 4 words), "emoji", "detail" (max 6 words), "cue"}}
- "stack": "items": 3-5 of {{"label" (max 5 words), "emoji", "cue"}} listed from the BOTTOM layer to the TOP layer
- "compare": "left" and "right", each {{"title", "emoji", "style": "bad" | "good" | "neutral", "points": 2-4 strings of max 5 words}}
- "code": "lines": 2-7 short terminal lines (commands start with "$ "), "caption" (max 8 words). Use it only if the topic has real commands.
- "quiz": "question", "options": 4 short strings, "answer": index 0-3 (exactly one clearly correct answer)
"cue" is a word or short phrase copied EXACTLY from that scene's narration, at the moment the item should appear on screen.
Use ONLY emojis from this list: {EMOJI_HINT}.
LOGOS: any item of "icons", "flow", "cycle", "list" or "stack" (and the "definition" layout) may have an optional "logo": the exact product or company name, for example Git, GitHub, Docker, Kubernetes, Jenkins, Terraform, Ansible, Azure, AWS, Prometheus, Grafana, Maven, Selenium, Netflix. Its real logo is then shown instead of the emoji. Add "logo" whenever an item IS a specific tool, product or company (for a tools scene use "icons" or "list" with a "logo" on every item). Never add it for generic ideas such as "build" or "test".

Structure: scene 1 = a relatable problem or hook; scene 2 = the clear definition ("definition" layout); then build understanding step by step with at least 5 different layouts including one "flow" or "cycle"; the second to last scene = a quick recap ("icons" or "list"); the LAST scene = a "quiz" whose narration reads the question and options, tells the viewer to pause, and then reveals the answer with a one-line reason."""
    for _ in range(3):
        data = ask(prompt, cfg)
        scenes = [normalize_scene(s) for s in (data.get("scenes") or [])]
        scenes = [s for s in scenes if s]
        if len(scenes) >= max(6, cfg["scenes"] - 3) and data.get("title"):
            data["scenes"] = scenes
            break
        print(f"  script had only {len(scenes)} usable scenes, asking again")
    else:
        raise RuntimeError("Could not get a usable script from Gemini")
    if cfg.get("review", True):
        data = review(cfg, ep, data)
    # make sure the episode ends with the quiz
    data["scenes"].sort(key=lambda s: s["layout"] == "quiz")
    for k, d in (("intro_narration", f"Welcome to the {cfg['series_name']}. In episode {ep['n']} we learn {ep['title']}."),
                 ("outro_narration", "Thanks for watching. Like, share and subscribe to keep learning DevOps.")):
        data[k] = _s(data.get(k), 600) or d
    data["tags"] = [_s(t, 40) for t in (data.get("tags") or []) if str(t).strip()][:15]
    data["title"], data["description"] = _s(data["title"], 95), str(data.get("description") or "").strip()
    data["thumbnail_text"] = _s(data.get("thumbnail_text"), 40) or ep["title"]
    return data


def review(cfg, ep, data):
    """Second opinion on technical accuracy; keeps the original if the reviewed JSON is unusable."""
    prompt = f"""You are a meticulous senior DevOps/SRE reviewer. Check this video script for technical errors, outdated advice, wrong tool descriptions and misleading simplifications.
Fix only what is wrong or unclear. Keep every key, the layouts, the number of scenes, the quiz structure and the style unchanged. Keep each "cue" an exact phrase from its scene's narration.
Return the COMPLETE corrected JSON with the same structure.
{json.dumps({'title': data['title'], 'scenes': data['scenes'], 'intro_narration': data.get('intro_narration'), 'outro_narration': data.get('outro_narration')}, ensure_ascii=False)}"""
    try:
        fixed = ask(prompt, cfg)
        scenes = [normalize_scene(s) for s in (fixed.get("scenes") or [])]
        scenes = [s for s in scenes if s]
        if len(scenes) >= len(data["scenes"]) - 1:
            data["scenes"] = scenes
            for k in ("intro_narration", "outro_narration"):
                if fixed.get(k):
                    data[k] = fixed[k]
            print("  technical review applied")
    except Exception as e:
        print("  review skipped:", str(e)[:100])
    return data
