"""Free neural narration via Microsoft Edge TTS (no API key). Skips scenes that already exist (resume)."""
import asyncio, os, edge_tts


async def _one(text, voice, rate, path):
    for attempt in range(6):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(path)
            if os.path.getsize(path) > 2000:
                return
        except Exception as e:
            print(f"  TTS retry {attempt + 1}: {str(e)[:120]}")
        await asyncio.sleep(5 * (attempt + 1))
    raise RuntimeError("TTS failed repeatedly")


def narrate(scenes, cfg, workdir):
    voice, rate = cfg["voice"][cfg["language"]], cfg["voice"]["rate"]
    paths = []
    for i, sc in enumerate(scenes):
        p = str(workdir / f"scene_{i:02d}.mp3")
        if not (os.path.exists(p) and os.path.getsize(p) > 2000):
            asyncio.run(_one(sc["narration"], voice, rate, p))
        paths.append(p)
    print(f"  narration ready ({len(paths)} scenes)")
    return paths
