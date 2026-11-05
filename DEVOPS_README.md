# DevOps Series (animated explainers)

One episode per run, in the order of `devops/series.yaml`. Each episode: intro, ~13 animated scenes (icons, handwritten text,
arrows that draw themselves, terminal typing, a quiz) and an outro. Narration: Microsoft Edge TTS (free). Script: Gemini (free tier) + a technical review pass.

Local test (needs ffmpeg or `pip install imageio-ffmpeg`):  
`pip install -r devops/requirements.txt`, set `GEMINI_API_KEY`, then `python devops/run.py --dry-run --episode 1`

Settings: `devops/config.yaml` (language, length, voice, privacy). Topics: `devops/series.yaml`.
Workflow: `.github/workflows/devops-video.yml` (uses the same four secrets as the mythology workflow).
