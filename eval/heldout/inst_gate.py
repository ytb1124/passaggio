"""악기 이름 신뢰도 게이트 — 개발셋 선택·평가셋 판정 (.venv-backend). 규칙: eval/INST_PREREG.md (결과 전에 고정).

    python inst_gate.py dev     # 격자 → runs/_inst/choice.json (잠금)
    python inst_gate.py test    # 고른 설정 하나로 Slakh test·TRIOS 판정 → runs/_inst/test_results.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inst_diag as D  # noqa: E402

OUT = HERE / "runs" / "_inst"
INSTRUMENTS = D._I["INSTRUMENTS"]
FAM = D.FAMILIES
ALL_FAMS = sorted({f for fs in FAM.values() for f in fs})
FAM_MEMBERS = {f: [i for i, n in enumerate(INSTRUMENTS) if f in FAM[n]] for f in ALL_FAMS}
GRID = [(t1, t2) for t1 in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9) for t2 in (0.5, 0.6, 0.7, 0.8, 0.9)]
SEG = 5.0


def labels(set_name, song, cfg):
    """트랙별 표시 이름: ("inst", 이름) | ("fam", 계열) | ("other",). cfg None = 대조군(dettato 그대로)."""
    d = json.loads((OUT / set_name / song / "notes.json").read_text())
    tp = np.load(OUT / set_name / song / "track_probs.npy")
    out = []
    for k, p in zip(d["group_inst"], tp):
        n = INSTRUMENTS[k]
        if cfg is None or p[k] >= cfg[0]:
            out.append(("inst", n))
            continue
        fam = max(FAM[n], key=lambda f: p[FAM_MEMBERS[f]].sum())
        out.append(("fam", fam) if p[FAM_MEMBERS[fam]].sum() >= cfg[1] else ("other",))
    return out


def pred(set_name, song, cfg):
    d = json.loads((OUT / set_name / song / "notes.json").read_text())
    lab = labels(set_name, song, cfg)
    tracks = [t for t in d["tracks"] if not t["drum"]]
    return [(a, b, p, lab[k]) for k, t in enumerate(tracks) for a, b, p, _ in t["notes"] if a >= D.rh.IGNORE_HEAD]


def ok(label, r):
    if label[0] == "inst":
        return D.same_inst(label[1], r)
    return label[1] in FAM[r]


def unit_counts(set_name, song, cfg, by_seg):
    """단위(곡 또는 5초 구간)별 [맞음, 표시, 구체, 기권, 매칭]."""
    ref, est = D.gt_notes(set_name, song), pred(set_name, song, cfg)
    out = {}
    for i, j in D.match(ref, est):
        lab, r = est[j][3], ref[i][3]
        key = (song, int(ref[i][0] // SEG)) if by_seg else song
        c = out.setdefault(key, np.zeros(5))
        c[4] += 1
        if lab[0] == "other":
            c[3] += 1
            continue
        c[1] += 1
        c[2] += lab[0] == "inst"
        c[0] += ok(lab, r)
    return out


def summary(c):
    return {"precision": c[0] / max(c[1], 1), "specific": c[2] / max(c[4], 1), "abstain": c[3] / max(c[4], 1), "matched": int(c[4])}


def cmd_dev() -> int:
    if (OUT / "choice.json").exists():
        print("이미 골랐다(잠금):", (OUT / "choice.json").read_text())
        return 0
    songs = (HERE / "runs" / "_notelen" / "dev_songs.txt").read_text().split()
    cache = {}
    rows = []
    for cfg in [None] + GRID:
        tot = np.zeros(5)
        for g in songs:
            for v in unit_counts("dev", g, cfg, False).values():
                tot += v
        s = summary(tot)
        rows.append({"cfg": cfg, **s})
        print(cfg, {k: round(v, 3) for k, v in s.items()}, flush=True)
    base = rows[0]
    cand = rows[1:]
    good = [r for r in cand if r["precision"] >= 0.90]
    if good:
        pick = sorted(good, key=lambda r: (-r["specific"], r["abstain"], r["cfg"][0], r["cfg"][1]))[0]
        note = "정밀도 0.90 이상 중 구체 비율 최대"
    else:
        pick = max(cand, key=lambda r: r["precision"])
        note = "0.90을 넘는 설정 없음 → 정밀도 최대"
    (OUT / "choice.json").write_text(json.dumps({"baseline": base, "grid": cand, "choice": pick, "note": note}, indent=1, ensure_ascii=False))
    print("선택:", pick, note)
    _ = cache
    return 0


def _boot(units_b, units_n, n=10000):
    keys = sorted(units_b)
    B = np.array([units_b[k] for k in keys])
    N = np.array([units_n.get(k, np.zeros(5)) for k in keys])
    idx = np.random.default_rng(0).integers(0, len(keys), size=(n, len(keys)))
    pb = np.array([B[i, 0].sum() / max(B[i, 1].sum(), 1) for i in idx])
    pn = np.array([N[i, 0].sum() / max(N[i, 1].sum(), 1) for i in idx])
    return [float(x) for x in np.percentile(pn - pb, [2.5, 97.5])]


def cmd_test() -> int:
    ch = json.loads((OUT / "choice.json").read_text())
    cfg = tuple(ch["choice"]["cfg"])
    res = {"choice": cfg}
    for set_name, songs, by_seg in (("slakh", D.songs_of("slakh"), False), ("trios", D.songs_of("trios"), True)):
        ub, un = {}, {}
        per = {}
        for g in songs:
            b, n = unit_counts(set_name, g, None, by_seg), unit_counts(set_name, g, cfg, by_seg)
            ub.update(b)
            un.update(n)
            per[g] = {"base": summary(sum(b.values(), np.zeros(5))), "new": summary(sum(n.values(), np.zeros(5))),
                      "labels": [list(x) for x in labels(set_name, g, cfg)], "base_labels": [list(x) for x in labels(set_name, g, None)]}
        sb, sn = summary(sum(ub.values(), np.zeros(5))), summary(sum(un.values(), np.zeros(5)))
        ci = _boot(ub, un)
        res[set_name] = {"base": sb, "new": sn, "diff": sn["precision"] - sb["precision"], "diff_ci": ci, "per_song": per}
        print(set_name, "정밀도 %.3f → %.3f (차 %+.3f [%+.3f, %+.3f]), 구체 %.3f, 기권 %.3f"
              % (sb["precision"], sn["precision"], sn["precision"] - sb["precision"], ci[0], ci[1], sn["specific"], sn["abstain"]))
    res["verdict"] = {"I1": all(res[s]["diff_ci"][0] > 0 and res[s]["new"]["precision"] >= 0.85 for s in ("slakh", "trios"))}
    (OUT / "test_results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    for g, v in res["trios"]["per_song"].items():
        print(" ", g, v["base_labels"], "→", v["labels"])
    print(json.dumps(res["verdict"]))
    return 0


if __name__ == "__main__":
    raise SystemExit({"dev": cmd_dev, "test": cmd_test}[sys.argv[1]]())
