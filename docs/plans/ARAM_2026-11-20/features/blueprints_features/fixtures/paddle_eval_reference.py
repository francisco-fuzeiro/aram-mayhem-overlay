import json, sys, time, glob, os, re, unicodedata
import numpy as np, onnxruntime as ort
from PIL import Image
from rapidfuzz import fuzz
MODEL, DICT, FIX = sys.argv[1], sys.argv[2], sys.argv[3]
sess = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
chars = [""] + open(DICT, encoding="utf-8").read().splitlines() + [" "]
H, W = 48, 448
def rec(img):
    img = img.convert("RGB"); w = max(1, min(W, round(img.width * H / img.height)))
    a = np.asarray(img.resize((w, H), Image.BILINEAR), dtype=np.float32) / 255.0
    x = np.zeros((1, 3, H, W), np.float32); x[0, :, :, :w] = ((a - 0.5) / 0.5).transpose(2, 0, 1)
    p = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
    best = p.argmax(1); conf = p.max(1); out, last, cs = "", 0, []
    for b, c in zip(best, conf):
        if b != last and b != 0: out += chars[b]; cs.append(c)
        last = b
    return out.strip(), (float(np.mean(cs)) if cs else 0.0)
def lines(img):
    g = np.asarray(img.convert("L"), dtype=np.float32); rows = (g > 150).sum(1) > 2
    segs, s = [], None
    for i, r in enumerate(list(rows) + [False]):
        if r and s is None: s = i
        if not r and s is not None:
            if i - s >= 6: segs.append((s, i))
            s = None
    if not segs: return []
    x = np.where((g > 150).sum(0) > 0)[0]
    return [img.crop((max(0, x.min() - 6), max(0, a - 4), min(img.width, x.max() + 6), min(img.height, b + 4))) for a, b in segs]
def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)
cat = json.load(open(f"{FIX}/expected_mayhem_catalog_2026-11-20.json"))["catalog"]
names = {i: norm(n) for i, n in cat.items()}
def match(text):
    t = norm(text); sc = sorted(((fuzz.ratio(t, n), i) for i, n in names.items()), reverse=True)
    (s1, i1), (s2, _) = sc[0], sc[1]
    return (cat[i1] if s1 >= 90 and s1 - s2 >= 8 else None), s1, s1 - s2
cases = []
for d in ["title_crops_1440p", "title_crops_prismatic_snips"]:
    for c in json.load(open(f"{FIX}/{d}/ground_truth.json"))["cases"]: cases.append((f"{FIX}/{d}/{c['file']}", c["expected_name"]))
for f in sorted(glob.glob(f"{FIX}/no_offer_2544x1353/*.png")): cases.append((f, None))
ok_full = ok_lines = 0; times = []
for f, exp in cases:
    img = Image.open(f)
    t0 = time.perf_counter(); full, cf = rec(img); times.append(time.perf_counter() - t0)
    ls = [rec(l) for l in lines(img)]
    joined = " ".join(t for t, c in ls if c >= 0.5 and len(norm(t)) >= 2)
    mf = match(full)[0]; ml, s, m = match(joined) if joined else (None, 0, 0)
    ok_full += (mf == exp); ok_lines += (ml == exp)
    print(f"{os.path.basename(f)[:34]:34} exp={str(exp):24} full={full!r:30}->{str(mf):22} lines={joined!r:34}->{ml} ({s:.0f}/{m:.0f})")
print(f"\nfull-crop correct {ok_full}/{len(cases)} ; line-split correct {ok_lines}/{len(cases)} ; median {1000*np.median(times):.0f} ms/crop (CPU, onnxruntime)")