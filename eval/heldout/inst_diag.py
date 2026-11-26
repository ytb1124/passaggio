"""악기 배정 진단 (.venv-backend) — dettato가 붙인 트랙 악기 이름이 실제 악기와 맞는지. 기록용, 판정 아님.

정답: Slakh(악기별 program), TRIOS(악기별 MIDI). 예측: runs/_notelen/<set>/<song>/notes.json (dettato 기본 설정 출력).
노트 매칭: 음높이 + 시작 50 ms(mir_eval, 끝 무시). 매칭된 노트끼리 악기를 비교한다.

    python inst_diag.py dev|slakh|trios
"""

from __future__ import annotations

import json
import runpy
import sys
from collections import Counter, defaultdict
from pathlib import Path

import mir_eval
import numpy as np
import pretty_midi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(HERE), str(ROOT / "eval"), str(ROOT)]
import fetch_heldout as fh  # noqa: E402
import run_heldout as rh  # noqa: E402

_I = runpy.run_path(str(next((ROOT / ".venv-dettato" / "lib").glob("python*/site-packages/dettato/grouper/instruments.py"))))
PROGRAMS, FAMILIES = _I["PROGRAMS"], _I["FAMILIES"]
PROG2INST = {p: n for n, ps in PROGRAMS.items() for p in ps}
TRIOS_NAME = {"horn": "french_horn", "saxophone": "alto_sax"}
TRIOS_DIR = ROOT / "data" / "raw" / "trios_dl" / "TRIOS Dataset"
OUT = HERE / "runs" / "_notelen"


def same_inst(a: str, b: str) -> bool:
    return a == b or (a.endswith("_sax") and b.endswith("_sax"))


def same_family(a: str, b: str) -> bool:
    return same_inst(a, b) or bool(set(FAMILIES[a]) & set(FAMILIES[b]))


def gt_notes(set_name: str, song: str):
    """[(onset, offset, pitch, instrument)]"""
    out = []
    if set_name == "trios":
        man = {r["song"]: r for r in json.loads((HERE / "data" / "trios" / "manifest.json").read_text())}
        sh = man[song]["shift_applied_s"]
        for f in sorted((TRIOS_DIR / song).glob("*.mid")):
            if f.stem in ("kick", "snare", "ride"):
                continue
            name = TRIOS_NAME.get(f.stem, f.stem)
            for i in pretty_midi.PrettyMIDI(str(f)).instruments:
                out += [(n.start + sh, n.end + sh, n.pitch, name) for n in i.notes]
        return [x for x in out if x[0] >= rh.IGNORE_HEAD]
    src = ROOT / "data" / "raw" / "slakh_train" if set_name == "dev" else HERE / "data" / "_raw" / "slakh"
    for i in pretty_midi.PrettyMIDI(str(src / song / "all_src.mid")).instruments:
        if i.is_drum:
            continue
        name = PROG2INST.get(int(i.program), "sound_effect")
        out += [(n.start, n.end, n.pitch, name) for n in fh.window_notes(i.notes, fh.WIN_START, fh.WIN_END)]
    return [x for x in out if x[0] >= rh.IGNORE_HEAD]


def pred_notes(set_name: str, song: str):
    d = json.loads((OUT / set_name / song / "notes.json").read_text())
    out = []
    for k, t in enumerate(d["tracks"]):
        if t["drum"]:
            continue
        out += [(a, b, p, t["name"].replace(" ", "_"), k) for a, b, p, _ in t["notes"] if a >= rh.IGNORE_HEAD]
    return out


def match(ref, est):
    if not ref or not est:
        return []
    ri = np.array([[a, max(b, a + .01)] for a, b, *_ in ref])
    ei = np.array([[a, max(b, a + .01)] for a, b, *_ in est])
    rp = np.array([pretty_midi.note_number_to_hz(x[2]) for x in ref])
    ep = np.array([pretty_midi.note_number_to_hz(x[2]) for x in est])
    return mir_eval.transcription.match_notes(ri, rp, ei, ep, onset_tolerance=0.05, pitch_tolerance=50.0, offset_ratio=None)


def songs_of(set_name):
    if set_name == "dev":
        return (OUT / "dev_songs.txt").read_text().split()
    if set_name == "trios":
        return ["brahms", "lussier", "mozart", "schubert", "take_five"]
    return rh._songs(rh._manifest(), "slakh")


def main() -> int:
    set_name = sys.argv[1]
    tot = Counter()
    rows = []
    for g in songs_of(set_name):
        ref, est = gt_notes(set_name, g), pred_notes(set_name, g)
        m = match(ref, est)
        gt_insts = Counter(x[3] for x in ref)
        trk = defaultdict(list)  # 트랙 → 매칭된 정답 악기들
        for i, j in m:
            ri, (_, _, _, pi, k) = ref[i][3], est[j]
            trk[(k, pi)].append(ri)
            tot["matched"] += 1
            tot["inst_ok"] += same_inst(pi, ri)
            tot["fam_ok"] += same_family(pi, ri)
        names = {(e[4], e[3]) for e in est}
        tracks = []
        for key in sorted(names):
            got = Counter(trk.get(key, []))
            n_all = sum(1 for e in est if (e[4], e[3]) == key)
            maj = got.most_common(1)[0][0] if got else None
            ok = maj is not None and same_inst(key[1], maj)
            share = (sum(v for r, v in got.items() if same_inst(key[1], r)) / sum(got.values())) if got else 0.0
            tracks.append({"label": key[1], "notes": n_all, "majority_gt": maj, "label_ok": ok, "label_share": round(share, 2)})
            tot["tracks"] += 1
            tot["tracks_ok"] += ok
            tot["tracks_wrong_label_present_elsewhere"] += (not ok) and any(same_inst(key[1], r) for r in gt_insts)
        covered = {t["label"] for t in tracks if t["label_ok"]}
        missing = [r for r in gt_insts if not any(same_inst(c, r) for c in covered)]
        tot["gt_insts"] += len(gt_insts)
        tot["gt_missing"] += len(missing)
        rows.append({"song": g, "gt": dict(gt_insts), "tracks": tracks, "missing": missing})
    out = {"set": set_name, "totals": dict(tot),
           "note_inst_acc": tot["inst_ok"] / max(tot["matched"], 1), "note_family_acc": tot["fam_ok"] / max(tot["matched"], 1),
           "track_label_precision": tot["tracks_ok"] / max(tot["tracks"], 1),
           "gt_instrument_recall": 1 - tot["gt_missing"] / max(tot["gt_insts"], 1), "songs": rows}
    (OUT / f"inst_diag_{set_name}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(set_name, {k: round(v, 3) for k, v in out.items() if isinstance(v, float)}, dict(tot))
    if set_name == "trios" or "-v" in sys.argv:
        for r in rows:
            print(" ", r["song"], "정답", list(r["gt"]), "| 예측", [(t["label"], t["notes"], t["majority_gt"], t["label_share"]) for t in r["tracks"]],
                  "| 빠짐", r["missing"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
