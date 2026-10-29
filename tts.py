"""Free neural narration (Microsoft Edge TTS, no key). One short clip per shot so voice, picture and caption stay in sync."""
import asyncio, os, re
import edge_tts
import cast


def _clean(text):
    text = re.sub(r"[*_#`~\[\]{}<>]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _ok(path):
    return os.path.exists(path) and os.path.getsize(path) > 1500


async def _one(text, voice, rate, pitch, path, sem):
    async with sem:
        for attempt in range(6):
            try:
                kw = {"rate": rate}
                if pitch:
                    kw["pitch"] = pitch
                await edge_tts.Communicate(text, voice, **kw).save(path)
                if _ok(path):
                    return
            except Exception as e:
                print(f"  TTS retry {attempt + 1}: {str(e)[:100]}")
            await asyncio.sleep(3 * (attempt + 1))
        raise RuntimeError("TTS failed repeatedly for: " + text[:40])


async def _all(jobs):
    sem = asyncio.Semaphore(4)
    await asyncio.gather(*[_one(t, v, r, pi, p, sem) for t, v, r, pi, p in jobs])


def narrate(scenes, outline, cfg, workdir):
    jobs, paths = [], []
    for si, sc in enumerate(scenes):
        row = []
        for ki, shot in enumerate(sc["shots"]):
            p = str(workdir / f"a_{si:02d}_{ki:02d}.mp3")
            row.append(p)
            if not _ok(p):
                pr = cast.profile(shot.get("speaker"), outline, cfg)
                jobs.append((_clean(shot["narration"]), pr["voice"], pr["rate"], pr.get("pitch"), p))
        paths.append(row)
    if jobs:
        asyncio.run(_all(jobs))
    print(f"  narration ready ({sum(len(r) for r in paths)} clips)")
    return paths
