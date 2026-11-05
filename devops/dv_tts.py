"""Narration with Microsoft Edge TTS (free). One clip per scene; clips that already exist are reused on a resumed run."""
import asyncio, os, re
import edge_tts


def clean(t):
    return re.sub(r"\s+", " ", re.sub(r"[*_#`~\[\]{}<>]", "", t)).strip()


def ok(p):
    return os.path.exists(p) and os.path.getsize(p) > 1500


async def _one(text, voice, rate, pitch, path, sem):
    async with sem:
        for attempt in range(6):
            try:
                kw = {"rate": rate}
                if pitch:
                    kw["pitch"] = pitch
                await edge_tts.Communicate(text, voice, **kw).save(path)
                if ok(path):
                    return
            except Exception as e:
                print(f"  TTS retry {attempt + 1}: {str(e)[:100]}")
            await asyncio.sleep(3 * (attempt + 1))
        raise RuntimeError("TTS failed for: " + text[:40])


async def _all(jobs):
    sem = asyncio.Semaphore(3)
    await asyncio.gather(*[_one(*j, sem) for j in jobs])


def narrate(texts, cfg, workdir):
    v = cfg["voice"][cfg["language"]]
    paths, jobs = [], []
    for i, t in enumerate(texts):
        p = str(workdir / f"n_{i:02d}.mp3")
        paths.append(p)
        if not ok(p):
            jobs.append((clean(t), v["voice"], v["rate"], v.get("pitch"), p))
    if jobs:
        asyncio.run(_all(jobs))
    print(f"  narration ready ({len(paths)} clips)")
    return paths
