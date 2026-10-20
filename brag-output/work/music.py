"""Generate the brag soundtrack (48 kHz stereo): pad + bass + soft beat + in-key chimes, one mix.

With a timeline JSON argument (from composition-full.html), cues follow its scenes."""
import json, sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve, butter, sosfilt

SR, BPM = 48000, 100
TL = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else None
DUR = TL["duration"] if TL else 40.0
OUT = sys.argv[2] if len(sys.argv) > 2 else "music.wav"
SC = {s["kind"]: s for s in TL["scenes"]} if TL else {}
FEAT0 = next((s["a"] for s in TL["scenes"] if s["kind"] == "feature"), 8.0) if TL else 8.0
RES = SC.get("results", {"a": 31.0, "b": 36.5}); OUTRO = SC.get("outro", {"a": 36.5})
REVEAL = SC.get("reveal", {"a": 4.0})
CUTS = [s["a"] for s in TL["scenes"][1:]] if TL else [4.0, 8.0, 14.0, 19.5, 25.0, 31.0, 36.5]
BEAT = 60 / BPM
n = int(SR * DUR)
t = np.arange(n) / SR
rng = np.random.default_rng(7)

def hz(m):  # MIDI note -> Hz
    return 440.0 * 2 ** ((m - 69) / 12)

def env_adsr(length, a, r):
    e = np.ones(length)
    ai, ri = int(a * SR), int(r * SR)
    e[:ai] = np.linspace(0, 1, ai)
    e[-ri:] *= np.linspace(1, 0, ri)
    return e

def place(buf, sig, start):
    i = int(start * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i]

# Am - F - C - G, one chord per bar (4 beats)
chords = [[57, 60, 64], [53, 57, 60], [48, 55, 60, 64], [55, 59, 62]]
roots = [45, 41, 48, 43]
bar = 4 * BEAT
pad = np.zeros(n); bass = np.zeros(n)
for k in range(int(DUR / bar) + 1):
    start = k * bar
    L = int(bar * SR * 1.15)
    tt = np.arange(L) / SR
    sig = np.zeros(L)
    for m in chords[k % 4]:
        for det in (-0.08, 0.08):  # two detuned saw-ish partials, softened
            f = hz(m) * (1 + det / 100)
            sig += sum(np.sin(2 * np.pi * f * h * tt) / h ** 1.6 for h in range(1, 6))
    place(pad, sig * env_adsr(L, 0.6, 0.9), start)
    if start >= FEAT0 - 0.4:  # bass enters with the first feature
        bl = int(bar * SR)
        bt = np.arange(bl) / SR
        b = np.sin(2 * np.pi * hz(roots[k % 4]) * bt) + 0.3 * np.sin(2 * np.pi * 2 * hz(roots[k % 4]) * bt)
        place(bass, b * env_adsr(bl, 0.02, 0.4), start)

# low-pass the pad so it stays warm
pad = sosfilt(butter(2, 1800, fs=SR, output="sos"), pad)

# soft beat from the first feature to the end of the results
drums = np.zeros(n)
kl = int(0.35 * SR); kt = np.arange(kl) / SR
kick = np.sin(2 * np.pi * (48 + 70 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 9)
hl = int(0.06 * SR)
hat = sosfilt(butter(2, 7000, btype="high", fs=SR, output="sos"), rng.standard_normal(hl)) * np.exp(-np.arange(hl) / SR * 60)
b = FEAT0
while b < RES["b"]:
    idx = round((b - FEAT0) / BEAT)
    if idx % 2 == 0:
        place(drums, kick, b)
    place(drums, hat * (0.5 if idx % 2 else 0.3), b + BEAT / 2)
    b += BEAT

# chimes in key (A minor pentatonic) under each stat card and the reveal
chime = np.zeros(n)
def bell(m, at, gain=1.0):
    L = int(2.2 * SR); tt = np.arange(L) / SR
    s = (np.sin(2 * np.pi * hz(m) * tt) + 0.35 * np.sin(2 * np.pi * hz(m) * 2.76 * tt) * np.exp(-tt * 4))
    place(chime, gain * s * np.exp(-tt * 2.2) * env_adsr(L, 0.005, 0.3), at)
for m, at in [(76, REVEAL["a"] + 0.1), (69, REVEAL["a"] + 0.35)]:
    bell(m, at, 0.8)
for m, at in [(76, RES["a"] + 0.7), (81, RES["a"] + 1.3), (84, RES["a"] + 1.9)]:
    bell(m, at)
bell(69, OUTRO["a"] + 0.1, 0.9); bell(76, OUTRO["a"] + 0.3, 0.6)

# gentle noise swell into each scene change (texture, kept low)
swell = np.zeros(n)
for at in CUTS:
    L = int(0.8 * SR)
    s = sosfilt(butter(2, [800, 5000], btype="band", fs=SR, output="sos"), rng.standard_normal(L))
    place(swell, s * np.linspace(0, 1, L) ** 2, at - 0.8)

# arrangement: pad grows slightly into results, everything fades out at the end
arr = np.interp(t, [0, 4, FEAT0, RES["a"], RES["a"] + 2, OUTRO["a"], OUTRO["a"] + 1, DUR], [0.55, 0.7, 0.8, 0.85, 1.0, 0.9, 0.7, 0.0])
mix = (0.22 * pad + 0.20 * bass * (t > FEAT0 - 0.4) + 0.30 * drums + 0.16 * chime + 0.015 * swell) * arr

# shared room reverb so all elements sit in the same space
ir_len = int(1.6 * SR)
ir = rng.standard_normal(ir_len) * np.exp(-np.arange(ir_len) / SR * 3.2)
ir = sosfilt(butter(2, 4000, fs=SR, output="sos"), ir); ir /= np.abs(ir).sum() ** 0.5 * 30
wet = fftconvolve(mix, ir)[:n]
L_ch = mix + 0.35 * wet
R_ch = mix + 0.35 * np.roll(wet, int(0.011 * SR))
st = np.stack([L_ch, R_ch], 1)
st /= np.abs(st).max() / 0.85  # peak -1.4 dBFS
fade = np.ones(n); fade[: int(0.05 * SR)] = np.linspace(0, 1, int(0.05 * SR))
st *= fade[:, None]
wavfile.write(OUT, SR, (st * 32767).astype(np.int16))
print("wrote", OUT, round(DUR, 1), "s")
