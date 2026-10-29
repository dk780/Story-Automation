"""python main.py [--dry-run] [--force] [--category ramayana] [--topic "..."]
Resumable: progress lives in work/current, so a failed run continues where it stopped."""
import argparse, datetime, json, shutil, uuid, yaml
from pathlib import Path
import storygen, tts, images, render

STATE, WORK = Path("state.json"), Path("work/current")
DEFAULTS = {"scenes_per_call": 4, "fallback_model": None, "pollinations_model": "flux", "shots_per_scene": 9,
            "hf_model": "black-forest-labs/FLUX.1-schnell", "image_gen_size": [1536, 864],
            "image_providers": ["pollinations", "cloudflare", "huggingface"], "music_by_category": {}}


def load_state():
    s = json.loads(STATE.read_text()) if STATE.exists() else {}
    s.setdefault("used", []); s.setdefault("done_ids", [])
    return s


def pick(topics, category, topic, used):
    cats = list(topics)
    category = category or cats[datetime.date.today().toordinal() % len(cats)]
    if topic:
        return category, topic
    pool = [t for t in topics[category] if t not in used]
    return category, (pool[0] if pool else None)  # None -> Gemini invents a fresh story


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--category"); ap.add_argument("--topic")
    a = ap.parse_args()
    cfg = {**DEFAULTS, **yaml.safe_load(open("config.yaml", encoding="utf-8"))}
    topics = yaml.safe_load(open("topics.yaml", encoding="utf-8"))
    state, today = load_state(), datetime.date.today().isoformat()

    if not (a.dry_run or a.force) and state.get("last_success") == today:
        print("Today's video is already uploaded. Nothing to do."); return

    sc_p, meta_p = WORK / "scenes.json", WORK / "meta.json"
    if sc_p.exists():  # progress from an older version of the pipeline cannot be reused
        try:
            old = json.loads(sc_p.read_text(encoding="utf-8"))
            if not (old and "shots" in old[0]):
                shutil.rmtree(WORK)
        except Exception:
            shutil.rmtree(WORK)
    if WORK.exists():  # resume or start clean?
        stale = True
        if meta_p.exists() and not (a.topic or a.category):
            m = json.loads(meta_p.read_text())
            age = (datetime.date.today() - datetime.date.fromisoformat(m["date"])).days
            stale = m["id"] in state["done_ids"] or age > 2
        if stale:
            shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)

    if meta_p.exists():
        meta = json.loads(meta_p.read_text())
        print(f"RESUMING unfinished video: {meta['category']} | {meta['topic']}")
    else:
        category, topic = pick(topics, a.category, a.topic, state["used"])
        meta = {"id": uuid.uuid4().hex, "date": today, "category": category, "topic": topic}
        meta_p.write_text(json.dumps(meta, ensure_ascii=False))
        print(f"NEW video: {category} | {topic or '(AI picks a fresh story)'}")

    print("1/5 Outline")
    out_p = WORK / "outline.json"
    if out_p.exists():
        outline = json.loads(out_p.read_text(encoding="utf-8"))
    else:
        outline = storygen.make_outline(cfg, meta["category"], meta["topic"])
        out_p.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")

    print("2/5 Writing the script")
    if sc_p.exists():
        scenes = json.loads(sc_p.read_text(encoding="utf-8"))
    else:
        scenes = storygen.write_scenes(cfg, outline, WORK)
        sc_p.write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {sum(len(s['shots']) for s in scenes)} shots in {len(scenes)} scenes")

    print("3/5 Narration"); audio = tts.narrate(scenes, cfg, WORK)
    print("4/5 Pictures"); imgs = images.make_images(scenes, cfg, WORK)
    print("5/5 Rendering")
    plan = [[{"audio": audio[i][k], "image": imgs[i][k], "text": sh["narration"]} for k, sh in enumerate(sc["shots"])]
            for i, sc in enumerate(scenes)]
    video, thumb = WORK / "video.mp4", WORK / "thumb.jpg"
    secs = render.render(plan, cfg, WORK, video, cfg["music_by_category"].get(meta["category"]))
    print(f"Video length: {secs / 60:.1f} min")
    render.make_thumbnail(imgs[0][0], outline["title"], cfg, thumb)

    if a.dry_run:
        print("Dry run: skipping upload. Video at", video); return
    from upload_youtube import upload
    print("Uploaded:", upload(video, thumb, outline["title"], outline["description"], outline["tags"], cfg["privacy"]))
    state["used"].append(meta["topic"] or outline["title"])
    state["done_ids"].append(meta["id"]); state["last_success"] = today
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
