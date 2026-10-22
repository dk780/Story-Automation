"""python main.py [--dry-run] [--category ramayana] [--topic "..."]"""
import argparse, datetime, json, shutil, yaml
from pathlib import Path
import storygen, tts, images, render

STATE = Path("state.json")


def pick(topics, category, topic):
    used = set(json.loads(STATE.read_text())["used"]) if STATE.exists() else set()
    cats = list(topics)
    category = category or cats[datetime.date.today().toordinal() % len(cats)]
    if topic:
        return category, topic
    pool = [t for t in topics[category] if t not in used]
    return category, (pool[0] if pool else None)  # None -> Gemini invents a fresh story


def mark_used(key):
    used = json.loads(STATE.read_text())["used"] if STATE.exists() else []
    STATE.write_text(json.dumps({"used": used + [key]}, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="make the video but don't upload")
    ap.add_argument("--category"); ap.add_argument("--topic")
    a = ap.parse_args()
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    topics = yaml.safe_load(open("topics.yaml", encoding="utf-8"))
    category, topic = pick(topics, a.category, a.topic)
    print(f"Category: {category} | Topic: {topic or '(AI picks a fresh story)'}")

    work = Path("work") / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    work.mkdir(parents=True)
    print("1/5 Outline"); outline = storygen.make_outline(cfg, category, topic)
    print("2/5 Writing scenes"); scenes = storygen.write_scenes(cfg, outline)
    (work / "story.json").write_text(json.dumps({"outline": outline, "scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("3/5 Narration"); audio = tts.narrate(scenes, cfg, work)
    print("4/5 Images"); imgs = images.make_images(scenes, cfg, work)
    print("5/5 Rendering"); out = work / "video.mp4"
    secs = render.render(audio, imgs, cfg, work, out)
    print(f"Video length: {secs / 60:.1f} min")
    thumb = work / "thumb.jpg"
    render.make_thumbnail(imgs[0][0], outline["title"], cfg, thumb)

    if a.dry_run:
        print("Dry run: skipping upload. Video at", out)
    else:
        from upload_youtube import upload
        print("Uploaded:", upload(out, thumb, outline["title"], outline["description"], outline["tags"], cfg["privacy"]))
    mark_used(topic or outline["title"])
    if not a.dry_run:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
