"""Free neural narration via Microsoft Edge TTS (no API key)."""
import asyncio, edge_tts


async def _one(text, voice, rate, path):
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(path)
            return
        except Exception as e:
            print(f"  TTS retry {attempt + 1}: {e}")
            await asyncio.sleep(5 * (attempt + 1))
    raise RuntimeError("TTS failed")


def narrate(scenes, cfg, workdir):
    voice, rate = cfg["voice"][cfg["language"]], cfg["voice"]["rate"]
    paths = []
    for i, sc in enumerate(scenes):
        p = str(workdir / f"scene_{i:02d}.mp3")
        asyncio.run(_one(sc["narration"], voice, rate, p))
        paths.append(p)
    return paths
