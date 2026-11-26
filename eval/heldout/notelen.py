"""음 길이 보정 실험 — 노트 끝 재계산·채점 (.venv-backend). 규칙: eval/NOTELEN_PREREG.md (결과 전에 고정).

    python notelen.py dev      # 개발셋 격자 → runs/_notelen/choice.json (한 번 고르면 잠금)
    python notelen.py test     # 고른 설정 하나로 Slakh test·TRIOS 판정 → runs/_notelen/test_results.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import mir_eval
import numpy as np
import pretty_midi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(HERE), str(ROOT / "eval"), str(ROOT)]
import fetch_heldout as fh  # noqa: E402
import run_heldout as rh  # noqa: E402
import score  # noqa: E402

OUT = HERE / "runs" / "_notelen"
PITCH_LO, N_KEYS = 21, 88
SEG = 5.0
DEV_SONGS = (ROOT / "eval" / "heldout" / "runs" / "_notelen" / "dev_songs.txt")

GRID_R = [("R", fr, off, k) for fr in (0.4, 0.3, 0.2, 0.1) for off in (0.3, 0.5, 0.7, None) for k in (2, 4)]
GRID_E = [("E", x) for x in (0.1, 0.2, 0.3, 0.5, 1.0)]


# ------------------------------------------------------------------ data
def load_est(set_name: str, song: str):
    d = json.loads((OUT / set_name / song / "notes.json").read_text())
    notes = [(a, b, p) for t in d["tracks"] if not t["drum"] for a, b, p, _ in t["notes"]]
    m = np.load(OUT / set_name / song / "maps.npz")
    fr = np.maximum(m["frame"], m["frame2"]).astype(np.float32)
    off = np.maximum(m["offset"], m["offset2"]).astype(np.float32)
    return sorted(notes), fr, off, d["hop"]


def gt_dev(song: str):
    pm = pretty_midi.PrettyMIDI(str(ROOT / "data" / "raw" / "slakh_train" / song / "all_src.mid"))
    out = [(n.start, n.end, n.pitch) for i in pm.instruments if not i.is_drum
           for n in fh.window_notes(i.notes, fh.WIN_START, fh.WIN_END)]
    return rh._dedupe_notes([x for x in out if x[0] >= rh.IGNORE_HEAD])


def gt_slakh(song: str):
    pm = pretty_midi.PrettyMIDI(str(HERE / "data" / "_raw" / "slakh" / song / "all_src.mid"))
    out = [(n.start, n.end, n.pitch) for i in pm.instruments if not i.is_drum
           for n in fh.window_notes(i.notes, fh.WIN_START, fh.WIN_END)]
    return rh._dedupe_notes([x for x in out if x[0] >= rh.IGNORE_HEAD])


def gt_trios(song: str):
    return [tuple(x) for x in json.loads((HERE / "data" / "trios" / song / "gt.json").read_text())]


# ------------------------------------------------------------------ 보정
def _next_same_pitch(notes):
    """노트마다 같은 음높이(트랙 무관) 다음 시작 시각. 없으면 inf."""
    nxt = [np.inf] * len(notes)
    last: dict = {}
    for i in range(len(notes) - 1, -1, -1):
        a, _, p = notes[i]
        nxt[i] = last.get(p, np.inf)
        last[p] = a
    return nxt


def _peaks(x, th):
    pk = (x >= th)
    pk[1:] &= x[1:] >= x[:-1]
    pk[:-1] &= x[:-1] > x[1:]
    return pk


def apply(cfg, notes, fr, off, hop):
    nxt = _next_same_pitch(notes)
    if cfg[0] == "E":
        return [(a, max(b, min(b + cfg[1], nx)), p) for (a, b, p), nx in zip(notes, nxt)]
    _, fr_th, off_th, k = cfg
    T = fr.shape[0]
    low = fr < fr_th
    run = low.copy()
    for j in range(1, k):
        run[:T - j] &= low[j:]
    pk = _peaks(off, off_th) if off_th is not None else None
    out = []
    for (a, b, p), nx in zip(notes, nxt):
        l = p - PITCH_LO
        if not 0 <= l < N_KEYS:
            out.append((a, b, p))
            continue
        t0 = int(min(max(round(a / hop), 0), T - 1))
        lows = np.nonzero(run[t0 + 1:, l])[0]
        e = (t0 + 1 + lows[0] - 0.5) if len(lows) else T
        if pk is not None:
            offs = np.nonzero(pk[t0 + 2:, l])[0]
            if len(offs):
                e = min(e, t0 + 2 + offs[0])
        out.append((a, max(b, min(e * hop, nx)), p))
    return out


# ------------------------------------------------------------------ 채점
def f1_pair(ref, est):
    _, _, f_on, _ = score.mir_eval_metrics(ref, est)
    return f_on, rh._f1_with_offset(ref, est)


def cfg_name(c):
    return "E(+%.1fs)" % c[1] if c[0] == "E" else "R(fr %.1f, off %s, k %d)" % (c[1], "끔" if c[2] is None else c[2], c[3])


def cmd_dev() -> int:
    if (OUT / "choice.json").exists():
        print("이미 골랐다(잠금):", (OUT / "choice.json").read_text())
        return 0
    songs = DEV_SONGS.read_text().split()
    data = {g: (gt_dev(g), *load_est("dev", g)) for g in songs}
    rows = []
    base_on = np.mean([f1_pair(r, e)[0] for r, e, *_ in data.values()])
    base_off = np.mean([f1_pair(r, e)[1] for r, e, *_ in data.values()])
    print(f"개발셋 {len(songs)}곡, 보정 전: 시작만 {base_on:.4f}, 시작+끝 {base_off:.4f}")
    for c in GRID_E + GRID_R:
        fo = [f1_pair(r, apply(c, e, fr, of, hop)) for r, e, fr, of, hop in data.values()]
        rows.append({"cfg": list(c), "name": cfg_name(c), "onset": float(np.mean([x[0] for x in fo])),
                     "onset_offset": float(np.mean([x[1] for x in fo]))})
        print(f"{rows[-1]['name']:28s} 시작만 {rows[-1]['onset']:.4f}  시작+끝 {rows[-1]['onset_offset']:.4f}", flush=True)
    best = max(r["onset_offset"] for r in rows)
    # 0.005 이내면 단순한 쪽: E 먼저(작은 x부터), R은 기본값(0.4, 0.3, 2)에 가까운 순 = GRID 순서
    pick = next(r for r in rows if r["onset_offset"] >= best - 0.005)
    out = {"songs": songs, "baseline": {"onset": float(base_on), "onset_offset": float(base_off)}, "grid": rows, "choice": pick}
    (OUT / "choice.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("선택:", pick["name"], f"시작+끝 {pick['onset_offset']:.4f} (최고 {best:.4f})")
    return 0


def _seg_counts(ref, est, offset_ratio):
    ri = np.array([[a, max(b, a + .01)] for a, b, _ in ref])
    ei = np.array([[a, max(b, a + .01)] for a, b, _ in est])
    rp = np.array([pretty_midi.note_number_to_hz(p) for *_, p in ref])
    ep = np.array([pretty_midi.note_number_to_hz(p) for *_, p in est])
    m = mir_eval.transcription.match_notes(ri, rp, ei, ep, onset_tolerance=score.ONSET_TOLERANCE_SEC,
                                           pitch_tolerance=score.PITCH_TOLERANCE_CENTS, offset_ratio=offset_ratio)
    mr, me, c = {i for i, _ in m}, {j for _, j in m}, {}
    for i, (a, _, _) in enumerate(ref):
        c.setdefault(int(a // SEG), [0, 0, 0])[0 if i in mr else 2] += 1
    for j, (a, _, _) in enumerate(est):
        if j not in me:
            c.setdefault(int(a // SEG), [0, 0, 0])[1] += 1
    return c


def _f1(c):
    return 0.0 if c[0] == 0 else 2 * c[0] / (2 * c[0] + c[1] + c[2])


def cmd_test() -> int:
    ch = json.loads((OUT / "choice.json").read_text())
    cfg = tuple(ch["choice"]["cfg"])
    res = {"choice": ch["choice"]["name"]}
    # Slakh test: 곡 단위 paired bootstrap
    songs = rh._songs(rh._manifest(), "slakh")
    per, dur = {}, {"gt": [], "base": [], "new": []}
    for g in songs:
        ref = gt_slakh(g)
        est, fr, of, hop = load_est("slakh", g)
        est = [x for x in est if x[0] >= rh.IGNORE_HEAD]
        new = apply(cfg, est, fr, of, hop)
        (b_on, b_off), (n_on, n_off) = f1_pair(ref, est), f1_pair(ref, new)
        per[g] = {"base_onset": b_on, "base_onset_offset": b_off, "new_onset": n_on, "new_onset_offset": n_off}
        dur["gt"] += [b - a for a, b, _ in ref]
        dur["base"] += [b - a for a, b, _ in est]
        dur["new"] += [b - a for a, b, _ in new]
    d_off = [v["new_onset_offset"] - v["base_onset_offset"] for v in per.values()]
    d_on = [v["new_onset"] - v["base_onset"] for v in per.values()]
    sl = {"base_onset": float(np.mean([v["base_onset"] for v in per.values()])),
          "new_onset": float(np.mean([v["new_onset"] for v in per.values()])),
          "base_onset_offset": float(np.mean([v["base_onset_offset"] for v in per.values()])),
          "new_onset_offset": float(np.mean([v["new_onset_offset"] for v in per.values()])),
          "diff_onset_offset": float(np.mean(d_off)), "diff_ci": rh.bootstrap_ci(d_off), "diff_onset": float(np.mean(d_on)),
          "median_dur": {k: float(np.median(v)) for k, v in dur.items()}, "per_song": per}
    res["slakh"] = sl
    # TRIOS: 5초 구간 블록 bootstrap, micro F1
    man = {r["song"]: r for r in json.loads((HERE / "data" / "trios" / "manifest.json").read_text())}
    segs = {k: {} for k in ("base_on", "new_on", "base_off", "new_off")}
    dur = {"gt": [], "base": [], "new": []}
    tper = {}
    for g in ("brahms", "lussier", "mozart", "schubert", "take_five"):
        ref = gt_trios(g)
        est, fr, of, hop = load_est("trios", g)
        est = [x for x in est if x[0] >= rh.IGNORE_HEAD]
        new = apply(cfg, est, fr, of, hop)
        dur["gt"] += [b - a for a, b, _ in ref]
        dur["base"] += [b - a for a, b, _ in est]
        dur["new"] += [b - a for a, b, _ in new]
        n = int(np.ceil(man[g]["duration"] / SEG))
        cs = {"base_on": _seg_counts(ref, est, None), "new_on": _seg_counts(ref, new, None),
              "base_off": _seg_counts(ref, est, rh.OFFSET_RATIO), "new_off": _seg_counts(ref, new, rh.OFFSET_RATIO)}
        tper[g] = {k: _f1(np.sum(list(v.values()), axis=0)) for k, v in cs.items()}
        for k, c in cs.items():
            for s in range(n + 1):
                segs[k][(g, s)] = c.get(s, [0, 0, 0])
    keys = sorted(segs["base_on"])
    arr = {k: np.array([segs[k][x] for x in keys]) for k in segs}
    keep = arr["base_on"][:, 0] + arr["base_on"][:, 2] > 0
    arr = {k: v[keep] for k, v in arr.items()}
    idx = np.random.default_rng(0).integers(0, keep.sum(), size=(10000, keep.sum()))
    micro = {k: _f1(v.sum(0)) for k, v in arr.items()}
    boot = {k: np.array([_f1(arr[k][i].sum(0)) for i in idx]) for k in ("base_off", "new_off")}
    tr = {"base_onset": micro["base_on"], "new_onset": micro["new_on"], "base_onset_offset": micro["base_off"],
          "new_onset_offset": micro["new_off"], "diff_onset_offset": micro["new_off"] - micro["base_off"],
          "diff_ci": [float(x) for x in np.percentile(boot["new_off"] - boot["base_off"], [2.5, 97.5])],
          "diff_onset": micro["new_on"] - micro["base_on"], "n_segments": int(keep.sum()),
          "median_dur": {k: float(np.median(v)) for k, v in dur.items()}, "per_song": tper}
    res["trios"] = tr
    ok = all(res[s]["diff_ci"][0] > 0 and abs(res[s]["diff_onset"]) < 0.005 for s in ("slakh", "trios"))
    res["verdict"] = {"N1": ok, "slakh_lo>0": res["slakh"]["diff_ci"][0] > 0, "trios_lo>0": res["trios"]["diff_ci"][0] > 0}
    (OUT / "test_results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    for s in ("slakh", "trios"):
        r = res[s]
        print(f"{s}: 시작만 {r['base_onset']:.4f}→{r['new_onset']:.4f}, 시작+끝 {r['base_onset_offset']:.4f}→{r['new_onset_offset']:.4f} "
              f"(차 {r['diff_onset_offset']:+.4f} [{r['diff_ci'][0]:+.3f}, {r['diff_ci'][1]:+.3f}]), 길이 중간값 {r['median_dur']}")
    print(json.dumps(res["verdict"]))
    return 0


if __name__ == "__main__":
    raise SystemExit({"dev": cmd_dev, "test": cmd_test}[sys.argv[1]]())
