"""Generates 3 royalty-free, seamlessly looping background tracks (no downloads, no copyright).
Run:  python tools/make_music.py     (needs numpy and ffmpeg)  ->  assets/music/*.mp3"""
import subprocess, wave
from pathlib import Path
import numpy as np

SR, L = 44100, 120                      # 2-minute loops
N = SR * L
t = np.arange(N) / SR
rng = np.random.default_rng(11)
OUT = Path(__file__).resolve().parent.parent / "assets" / "music"
mtof = lambda m: 440.0 * 2 ** ((m - 69) / 12)
lf = lambda f: round(f * L) / L         # whole cycles per loop => no click at the loop point


def wrap_add(buf, sig, start):
    """add sig into buf at start, wrapping around the end (circular) so the loop stays seamless"""
    idx = (np.arange(len(sig)) + start) % len(buf)
    np.add.at(buf, idx, sig)


def pluck(f, dur=5.0, bright=1.0, decay=1.6):
    n = int(SR * dur); tt = np.arange(n) / SR; s = np.zeros(n)
    for h in range(1, 14):
        s += np.sin(2 * np.pi * f * h * tt + rng.uniform(0, 6.28)) / h ** (1.1 / bright) * np.exp(-tt * (decay + 0.45 * h))
    return s * np.minimum(tt / 0.01, 1)


def bell(f, dur=6.0):
    n = int(SR * dur); tt = np.arange(n) / SR; s = np.zeros(n)
    for r, a, d in [(1, 1, 1.2), (2.76, .5, 2.2), (5.4, .25, 3.5), (8.93, .12, 5)]:
        s += a * np.sin(2 * np.pi * f * r * tt) * np.exp(-tt * d)
    return s * np.minimum(tt / 0.004, 1)


def pad(chords, vol=1.0):
    """slow evolving pad; chords cross-fade with cos^2 windows that sum to 1 around the loop"""
    k, out = len(chords), np.zeros(N)
    for i, notes in enumerate(chords):
        c = (i + .5) * L / k
        d = ((t - c + L / 2) % L) - L / 2
        w = np.where(np.abs(d) < L / k, np.cos(np.pi * d / (2 * L / k)) ** 2, 0)
        sig = np.zeros(N)
        for m in notes:
            for det in (-0.25, 0.0, 0.3):
                for h, a in ((1, 1), (2, .35), (3, .15)):
                    sig += a * np.sin(2 * np.pi * lf(mtof(m) * h + det) * t + rng.uniform(0, 6.28))
        out += w * sig / (len(notes) * 3)
    out *= 1 + 0.12 * np.sin(2 * np.pi * t / (L / 20))      # gentle breathing
    return out * vol


def reverb(x, secs=2.8, mix=0.38):
    m = int(SR * secs); ir = rng.standard_normal(m) * np.exp(-np.linspace(0, 6.5, m)); ir /= np.sqrt((ir ** 2).sum())
    y = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(ir, N), N)    # circular convolution keeps the loop seamless
    y *= np.sqrt((x ** 2).mean() / ((y ** 2).mean() + 1e-12))
    return (1 - mix) * x + mix * y


def stereo(layers):
    l = sum(reverb(x) for x in layers); r = sum(reverb(x) for x in layers)   # two different reverbs = width
    return np.stack([l, r], 1)


def save(name, st):
    st = st / np.abs(st).max() * 0.85
    wav = OUT / f"{name}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-b:a", "96k", str(OUT / f"{name}.mp3")], check=True, capture_output=True)
    wav.unlink()
    print("made", name)


def tanpura(root, vol=1.0):
    b = np.zeros(N)
    for c in range(L // 6):                      # Pa - Sa - Sa - low Sa, repeating every 6 s
        for j, (m, v) in enumerate([(root + 7 - 12, 1.0), (root, .8), (root, .8), (root - 12, 1.0)]):
            wrap_add(b, pluck(mtof(m), 5.5) * v, int((c * 6 + j * 1.5 + rng.uniform(-.03, .03)) * SR))
    return b * vol


def chimes(notes, count, vol=1.0):
    b = np.zeros(N)
    for _ in range(count):
        wrap_add(b, bell(mtof(rng.choice(notes))) * rng.uniform(.4, 1), int(rng.uniform(0, L) * SR))
    return b * vol


# 1) devotional / calm: tanpura drone, warm pad, soft bells  (Ramayana, Hanuman, calm scenes)
OUT.mkdir(parents=True, exist_ok=True)
save("devotional_calm", stereo([tanpura(48, .55), pad([[48, 55, 62, 64], [53, 57, 60, 64], [45, 52, 60, 64], [55, 62, 64, 69]], 1.0),
                                  chimes([72, 74, 76, 79, 81, 84], 22, .22)]))

# 2) epic / tense: low drone, minor pad, slow heartbeat, deep gong  (Mahabharat, superheroes)
beat = np.zeros(N)
for k in range(int(L / 1.2)):
    for off, v in ((0, 1.0), (.24, .6)):
        n = int(SR * .5); tt = np.arange(n) / SR
        wrap_add(beat, np.sin(2 * np.pi * 52 * np.exp(-tt * 3) * tt * 2 + 0) * np.exp(-tt * 9) * v, int((k * 1.2 + off) * SR))
gong = np.zeros(N)
for k in range(4):
    wrap_add(gong, bell(mtof(38), 9.0) * 1.2, int((k * 30 + 12) * SR))
save("epic_tense", stereo([tanpura(38, .5), pad([[38, 45, 50, 53, 57], [34, 41, 50, 53], [43, 50, 53, 58], [33, 45, 52, 57, 61]], 1.1),
                             beat * .35, gong * .25]))

# 3) adventure / light: kalimba-like arpeggios over a bright pad  (animal fables, Baby Hanuman, happy scenes)
arp = np.zeros(N)
scale = {0: [67, 71, 74, 79, 74, 71, 74, 71], 1: [64, 67, 71, 76, 71, 67, 71, 67], 2: [60, 64, 67, 72, 67, 64, 67, 64], 3: [62, 66, 69, 74, 69, 66, 69, 66]}
for step in range(int(L / .5)):
    m = scale[(step // 16) % 4][step % 8]
    wrap_add(arp, pluck(mtof(m), 2.5, bright=1.6, decay=3.2) * (0.9 if step % 4 == 0 else .55), int(step * .5 * SR))
save("adventure_light", stereo([pad([[55, 59, 62, 66], [52, 55, 59, 64], [48, 52, 55, 60], [50, 54, 57, 62]], .8), arp * .9,
                                chimes([79, 83, 86, 91], 10, .15)]))
