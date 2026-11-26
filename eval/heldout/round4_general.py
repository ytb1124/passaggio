"""Round 4 B — General 실제 녹음 재검증(TRIOS 5곡). 사전 등록: eval/ROUND4_PREREG.md §B

사용법(.venv-backend):
  python eval/heldout/round4_general.py prep    # data/trios/<곡>/{mix.wav, gt.json} + 정렬 점검(시스템 결과 보기 전)
  python eval/heldout/round4_general.py run     # gen_basicpitch / gen_dettato(MPS) / gen_yourmt3 전사(캐시)
  python eval/heldout/round4_general.py score   # 곡별 F1 + 5초 구간 블록 부트스트랩 micro F1 차이 CI
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import librosa
import mir_eval
import numpy as np
import pretty_midi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT))
import run_heldout as rh  # noqa: E402
import score  # noqa: E402

SRC = ROOT / "data" / "raw" / "trios_dl" / "TRIOS Dataset"
DATA = rh.DATA / "trios"
RUNS = rh.RUNS / "round4_general"
DRUM_TRACKS = {"kick", "ride", "snare"}
SEG = 5.0
SYSTEMS = ("gen_basicpitch", "gen_dettato", "gen_yourmt3")


def songs() -> list[str]:
    return sorted(p.name for p in SRC.iterdir() if p.is_dir())


def gt_raw(song: str) -> list:
    out = []
    for m in sorted((SRC / song).glob("*.mid")):
        if m.stem in DRUM_TRACKS:
            continue
        for inst in pretty_midi.PrettyMIDI(str(m)).instruments:
            if inst.is_drum:
                continue
            out += [(n.start, n.end, n.pitch) for n in inst.notes]
    return sorted(out)


def cmd_prep(a) -> int:
    rows = []
    for g in songs():
        d = DATA / g
        d.mkdir(parents=True, exist_ok=True)
        if not (d / "mix.wav").exists():
            shutil.copy(SRC / g / "mix.wav", d / "mix.wav")
        ref = gt_raw(g)
        # 정렬 점검: 정답 온셋 임펄스 vs 믹스 온셋 강도 곡선, ±200 ms
        y, sr = librosa.load(d / "mix.wav", sr=22050)
        hop = 220  # 10 ms
        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        imp = np.zeros_like(env)
        for s, _, _ in ref:
            k = int(round(s * sr / hop))
            if k < len(imp):
                imp[k] = 1.0
        lags = range(-20, 21)
        sc = [float(np.dot(imp[max(0, -L):len(imp) - max(0, L)], env[max(0, L):len(env) - max(0, -L)])) for L in lags]
        lag = list(lags)[int(np.argmax(sc))] * hop / sr  # +면 오디오가 정답보다 늦다
        shift = lag if abs(lag) > 0.020 else 0.0
        gt = rh._dedupe_notes([(s + shift, e + shift, p) for s, e, p in ref if s + shift >= rh.IGNORE_HEAD])
        (d / "gt.json").write_text(json.dumps(gt))
        dur = len(y) / sr
        rows.append({"song": g, "duration": round(dur, 2), "n_ref": len(gt), "align_lag_s": round(lag, 3), "shift_applied_s": round(shift, 3)})
        print(rows[-1], flush=True)
    (DATA / "manifest.json").write_text(json.dumps(rows, indent=1))
    return 0


def est_path(system: str, g: str) -> Path:
    return RUNS / system / g / {"gen_basicpitch": "general_basic_pitch.mid", "gen_dettato": "all.mid", "gen_yourmt3": "yourmt3_all.mid"}[system]


def cmd_run(a) -> int:
    from backend import pipeline

    for g in songs():
        mix = DATA / g / "mix.wav"
        for system in a.systems or SYSTEMS:
            dest = est_path(system, g)
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if system == "gen_basicpitch":
                res = pipeline.run_general_mode(mix, dest.parent)
                if Path(res["midiPath"]) != dest:
                    shutil.copy(res["midiPath"], dest)
            elif system == "gen_dettato":
                subprocess.run([str(ROOT / ".venv-dettato" / "bin" / "python"), str(ROOT / "backend/scripts/dettato_transcribe.py"),
                                str(mix), str(dest), "--device", "mps"], check=True, capture_output=True, text=True)
            else:
                rh.yourmt3_all(mix, dest.parent)
            print(system, g, "ok", flush=True)
    return 0


def _match_counts(ref, est):
    """곡 전체에서 매칭(score.mir_eval_metrics와 같은 조건) 후, TP·FN은 정답 온셋, FP는 추정 온셋 기준 5초 구간에 배정."""
    ri = np.array([[s, max(e, s + 0.01)] for s, e, _ in ref]) if ref else np.zeros((0, 2))
    ei = np.array([[s, max(e, s + 0.01)] for s, e, _ in est]) if est else np.zeros((0, 2))
    rp = np.array([pretty_midi.note_number_to_hz(p) for *_, p in ref])
    ep = np.array([pretty_midi.note_number_to_hz(p) for *_, p in est])
    m = mir_eval.transcription.match_notes(ri, rp, ei, ep, onset_tolerance=score.ONSET_TOLERANCE_SEC,
                                           pitch_tolerance=score.PITCH_TOLERANCE_CENTS, offset_ratio=None) if len(ref) and len(est) else []
    mr = {i for i, _ in m}
    me = {j for _, j in m}
    seg = lambda t: int(t // SEG)  # noqa: E731
    out: dict = {}
    for i, (s, _, _) in enumerate(ref):
        out.setdefault(seg(s), [0, 0, 0])[0 if i in mr else 2] += 1
    for j, (s, _, _) in enumerate(est):
        if j not in me:
            out.setdefault(seg(s), [0, 0, 0])[1] += 1
    return out, len(m)


def f1_of(c):
    tp, fp, fn = c
    return 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)


def cmd_score(a) -> int:
    man = {r["song"]: r for r in json.loads((DATA / "manifest.json").read_text())}
    per = {s: {} for s in SYSTEMS}
    segs = {s: {} for s in SYSTEMS}
    for g in songs():
        ref = [tuple(x) for x in json.loads((DATA / g / "gt.json").read_text())]
        nseg = int(np.ceil(man[g]["duration"] / SEG))
        for s in SYSTEMS:
            est = [x for x in rh._notes(est_path(s, g), drums=False) if x[0] >= rh.IGNORE_HEAD]
            counts, ntp = _match_counts(ref, est)
            p, r, f1, _ = score.mir_eval_metrics(ref, est)
            tot = np.sum([v for v in counts.values()], axis=0)
            assert int(tot[0]) == ntp and abs(f1_of(tot) - f1) < 1e-9, (g, s, f1_of(tot), f1)
            per[s][g] = {"f1": f1, "precision": p, "recall": r, "n_ref": len(ref), "n_est": len(est)}
            for k in range(nseg + 1):
                segs[s][(g, k)] = counts.get(k, [0, 0, 0])
    keys = sorted(segs[SYSTEMS[0]])
    arr = {s: np.array([segs[s][k] for k in keys]) for s in SYSTEMS}
    keep = arr[SYSTEMS[0]][:, 0] + arr[SYSTEMS[0]][:, 2] > 0  # 정답 노트가 있는 구간만
    arr = {s: v[keep] for s, v in arr.items()}
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(keys := [k for k, ok in zip(keys, keep) if ok]), size=(10000, len(keys)))
    micro = {s: f1_of(arr[s].sum(0)) for s in SYSTEMS}
    boot = {s: np.array([f1_of(arr[s][i].sum(0)) for i in idx]) for s in SYSTEMS}
    table = {}
    for s in SYSTEMS:
        lo, hi = np.percentile(boot[s], [2.5, 97.5])
        row = {"micro_f1": micro[s], "ci": [float(lo), float(hi)], "per_song": per[s]}
        if s != "gen_basicpitch":
            d = boot[s] - boot["gen_basicpitch"]
            row["diff_vs_basicpitch"] = micro[s] - micro["gen_basicpitch"]
            row["diff_ci"] = [float(x) for x in np.percentile(d, [2.5, 97.5])]
        table[s] = row
    verdict = {"B1_gen_dettato_minus_basicpitch_lo>0": table["gen_dettato"]["diff_ci"][0] > 0}
    out = {"n_segments": len(keys), "table": table, "verdict": verdict}
    (RUNS / "results.json").write_text(json.dumps(out, indent=1))
    print(f"구간 {len(keys)}개\n| 시스템 | micro F1 [95% CI] | Basic Pitch 대비 [95% CI] | " + " | ".join(songs()) + " |")
    print("|---|---|---|" + "---|" * len(songs()))
    for s in SYSTEMS:
        t = table[s]
        diff = "—" if s == "gen_basicpitch" else f"{t['diff_vs_basicpitch']:+.4f} [{t['diff_ci'][0]:+.3f}, {t['diff_ci'][1]:+.3f}]"
        print(f"| {s} | {t['micro_f1']:.4f} [{t['ci'][0]:.3f}, {t['ci'][1]:.3f}] | {diff} | "
              + " | ".join(f"{t['per_song'][g]['f1']:.3f}" for g in songs()) + " |")
    print(json.dumps(verdict))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prep")
    r = sub.add_parser("run")
    r.add_argument("--systems", nargs="*")
    sub.add_parser("score")
    a = ap.parse_args()
    return {"prep": cmd_prep, "run": cmd_run, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
