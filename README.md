# Free Story-Video Automation (20-30 min, Hindi or English)

Pipeline: topic -> Gemini (outline + scene-by-scene script) -> Edge TTS (free voice) -> Pollinations (free AI images)
-> ffmpeg (zoom effect + audio) -> YouTube upload. Runs daily on GitHub Actions. Cost: Rs 0.

## One-time setup
1. **Gemini key** (free): https://aistudio.google.com/apikey
2. **YouTube API**: Google Cloud Console -> new project -> enable "YouTube Data API v3" -> OAuth consent screen
   (External, add yourself as test user) -> Credentials -> OAuth client ID (Desktop app) -> download as `client_secret.json`.
   Run `python get_refresh_token.py` once on your laptop and copy the 3 values it prints.
3. **GitHub**: push this folder to a repo (public = unlimited free Actions minutes; private = 2,000 min/month).
   Add repo secrets: `GEMINI_API_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
4. Test locally first (needs ffmpeg): `pip install -r requirements.txt`, set `GEMINI_API_KEY`, then
   `python main.py --dry-run`. Check the video in `work/`. Then run the workflow manually (Actions tab -> Run workflow).

## Customising
- `config.yaml`: language, length, voice, image style, privacy (starts as `private`).
- `topics.yaml`: your story list, one category per day in rotation. When a list is exhausted, Gemini invents a fresh story.
- `assets/music/`: drop royalty-free .mp3 files for quiet background music (optional).
- Schedule: edit the `cron` line in `.github/workflows/daily-video.yml` (UTC time).

## Things to know
- **YouTube audit**: videos uploaded through a new, unverified API project are forced to private until you apply for
  the YouTube API compliance audit. Until then, review and publish manually from YouTube Studio.
- **Quota**: each upload costs 1,600 of the 10,000 free daily units (about 6 uploads/day).
- **Monetisation**: YouTube can reject mass-produced, repetitive content. Review videos, vary the stories,
  and keep the AI-content disclosure (already set in the upload).
- Free services (Gemini limits, Pollinations, Edge TTS) can change or rate-limit; the code retries, and
  `gemini_model` is configurable.
- Original superheroes only: do not use Marvel/DC characters.
