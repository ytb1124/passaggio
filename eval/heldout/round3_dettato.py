"""Round 3 — dettato 전사를 배치로 미리 돌려 캐시하고, 기존 하니스로 채점한다. 사전 등록: eval/ROUND3_PREREG.md

캐시 위치: runs/_dettato/<input>/<set>/<song>/{all.mid, drums.mid}  (input = stem_bass | stem_drums | mix)
  - stem_bass   htdemucs bass 스템  → 전체 체인 (베이스 stem_dettato)
  - mix         믹스               → 전체 체인 (베이스 mix_dettato, General gen_dettato, 드럼 dettato_mix와 같은 파일)
  - stem_drums  htdemucs drums 스템 → 드럼 모델만 (드럼 dettato_stem)

사용법:
  .venv-backend/bin/python eval/heldout/round3_dettato.py prep [--shards 3]   # 전사(캐시 없는 것만)
  .venv-backend/bin/python eval/heldout/round3_dettato.py score              # 베이스·드럼 요약 JSON 작성
  .venv-backend/bin/python eval/heldout/round3_dettato.py general            # General 채점 + 표
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pretty_midi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT))
import run_heldout as rh  # noqa: E402
import score  # noqa: E402

CACHE = rh.RUNS / "_dettato"
BASS_SETS = ["slakh", "slakh_realbass", "slakh_realbass_up"]
DRUM_SETS = ["mdb", "slakh"]
PY = ROOT / ".venv-dettato" / "bin" / "python"


def stem(set_name: str, song: str, kind: str) -> Path:
    return Path(json.loads((rh.RUNS / "_sep" / set_name / song / "stems.json").read_text())[kind])


def jobs() -> list[list[str]]:
    m = rh._manifest()
    out = []
    for s in BASS_SETS:
        for song in rh._songs(m, s):
            out.append([str(stem(s, song, "bass")), str(CACHE / "stem_bass" / s / song / "all.mid"), "all"])
            out.append([str(rh.DATA / s / song / "mix.wav"), str(CACHE / "mix" / s / song / "all.mid"), "all"])
    for s in DRUM_SETS:
        for song in rh._songs(m, s):
            out.append([str(stem(s, song, "drums")), str(CACHE / "stem_drums" / s / song / "drums.mid"), "drums"])
            if s == "mdb":  # slakh 믹스는 위에서 전체 체인으로 돌린다(드럼 트랙 포함)
                out.append([str(rh.DATA / s / song / "mix.wav"), str(CACHE / "mix" / s / song / "all.mid"), "all"])
    return out


def cmd_prep(a) -> int:
    todo = [j for j in jobs() if not Path(j[1]).exists()]
    # 무거운 전체 체인을 샤드에 고르게: 길이 비슷하므로 라운드로빈
    shards = [todo[i::a.shards] for i in range(a.shards)]
    procs = []
    env = dict(os.environ, OMP_NUM_THREADS="2", PYTHONWARNINGS="ignore")
    for i, sh in enumerate(shards):
        if not sh:
            continue
        jf = CACHE / f"jobs_{i}.json"
        jf.parent.mkdir(parents=True, exist_ok=True)
        jf.write_text(json.dumps(sh))
        log = open(CACHE / f"prep_{i}.log", "a")
        procs.append(subprocess.Popen(["nice", "-n", "15", str(PY), str(HERE / "dettato_transcribe.py"), "--jobs", str(jf),
                                       "--device", "cpu"], env=env, stdout=log, stderr=subprocess.STDOUT))
    print(f"{len(todo)}개 작업, {len(procs)}개 워커", flush=True)
    t = time.time()
    codes = [p.wait() for p in procs]
    print(f"완료 {round(time.time() - t)}s, 종료 코드 {codes}")
    return max(codes) if codes else 0


def _filter(src: Path, dest: Path, keep) -> Path:
    return rh.filter_midi(src, dest, keep)


def _write_summary(kind: str, system: str, results: dict):
    p = rh.RUNS / system / f"{kind}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_score(a) -> int:
    import drums_r2

    m = rh._manifest()
    # 베이스
    for system, src_dir, keep in (
        ("stem_dettato", "stem_bass", lambda i: not i.is_drum),
        ("mix_dettato", "mix", lambda i: not i.is_drum and i.program in rh.BASS_PROGRAMS),
    ):
        res = {}
        for s in BASS_SETS:
            for song in rh._songs(m, s):
                allm = CACHE / src_dir / s / song / "all.mid"
                key = f"{s}/{song}"
                if not allm.exists():
                    res[key] = {"error": "missing transcription"}
                    continue
                dest = rh.RUNS / system / "bass" / s / song / "bass.mid"
                dest.parent.mkdir(parents=True, exist_ok=True)
                _filter(allm, dest, keep)
                r = rh.score_bass(dest, rh.DATA / s / song / "bass.mid")
                r["midi"] = str(dest.relative_to(ROOT))
                res[key] = r
        _write_summary("bass", system, res)
        print(system, "bass", sum("f1" in v for v in res.values()), "곡")
    # 드럼
    for system, src in (("dettato_stem", lambda s, g: CACHE / "stem_drums" / s / g / "drums.mid"),
                        ("dettato_mix", lambda s, g: CACHE / "mix" / s / g / "all.mid")):
        res = {}
        for s in DRUM_SETS:
            for song in rh._songs(m, s):
                f = src(s, song)
                key = f"{s}/{song}"
                if not f.exists():
                    res[key] = {"error": "missing transcription"}
                    continue
                dest = rh.RUNS / system / "drums" / s / song / "drums.mid"
                dest.parent.mkdir(parents=True, exist_ok=True)
                _filter(f, dest, lambda i: i.is_drum)
                r = drums_r2.score_both(dest, rh.DATA / s / song / "drums.mid")
                r["midi"] = str(dest.relative_to(ROOT))
                info = f.with_suffix(".json")
                if info.exists():
                    r["drum_model"] = json.loads(info.read_text()).get("drums", {}).get("model") \
                        if isinstance(json.loads(info.read_text()).get("drums"), dict) else None
                res[key] = r
        _write_summary("drums", system, res)
        print(system, "drums", sum("f1" in v for v in res.values()), "곡")
    return 0


# ---------------------------------------------------------------- General (악기 무시 multi-pitch)

def general_gt(song: str) -> list:
    raw = rh.DATA / "_raw" / "slakh" / song / "all_src.mid"
    pm = pretty_midi.PrettyMIDI(str(raw))
    import fetch_heldout as fh

    out = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in fh.window_notes(inst.notes, fh.WIN_START, fh.WIN_END):
            out.append((n.start, n.end, n.pitch))
    return rh._dedupe_notes([x for x in out if x[0] >= rh.IGNORE_HEAD])


def general_est(path: Path) -> list:
    return rh._notes(path, drums=False)


def score_general(est, ref) -> dict:
    p, r, f1, _ = score.mir_eval_metrics(ref, est)
    return {"f1": f1, "precision": p, "recall": r, "f1_offset": rh._f1_with_offset(ref, est),
            "n_ref": len(ref), "n_est": len(est)}


def basic_pitch_mix(song: str) -> Path:
    from backend import pipeline

    out_dir = rh.RUNS / "gen_basicpitch" / "general" / "slakh" / song
    dest = out_dir / "general_basic_pitch.mid"
    if not dest.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        res = pipeline.run_general_mode(rh.DATA / "slakh" / song / "mix.wav", out_dir)
        dest = Path(res["midiPath"])
    return dest


def cmd_general(a) -> int:
    songs = rh._songs(rh._manifest(), "slakh")
    systems = {
        "gen_basicpitch": basic_pitch_mix,
        "gen_dettato": lambda g: CACHE / "mix" / "slakh" / g / "all.mid",
        "gen_yourmt3": lambda g: rh.RUNS / "_yourmt3_mix" / "slakh" / g / "yourmt3_all.mid",
    }
    summ = {}
    for name, fn in systems.items():
        res = {}
        for g in songs:
            try:
                path = fn(g)
                if not Path(path).exists():
                    raise FileNotFoundError(path)
                r = score_general(general_est(Path(path)), general_gt(g))
                r["midi"] = str(Path(path).relative_to(ROOT))
            except Exception as e:  # noqa: BLE001
                r = {"error": f"{type(e).__name__}: {e}"[:300]}
            res[f"slakh/{g}"] = r
        _write_summary("general", name, res)
        summ[name] = res
    base = summ["gen_basicpitch"]
    print("| 시스템 | onset F1 [95% CI] | gen_basicpitch 대비 [95% CI] | onset+offset F1 | P | R | n |\n|---|---|---|---|---|---|---|")
    for name, res in summ.items():
        ok = [k for k, v in res.items() if "f1" in v]
        f = [res[k]["f1"] for k in ok]
        lo, hi = rh.bootstrap_ci(f)
        d = [res[k]["f1"] - base[k]["f1"] for k in ok if "f1" in base.get(k, {})]
        dlo, dhi = rh.bootstrap_ci(d)
        diff = "—" if name == "gen_basicpitch" else f"{np.mean(d):+.4f} [{dlo:+.3f}, {dhi:+.3f}]"
        mean = lambda key: np.mean([res[k][key] for k in ok])  # noqa: E731
        print(f"| {name} | {np.mean(f):.4f} [{lo:.3f}, {hi:.3f}] | {diff} | {mean('f1_offset'):.4f} | "
              f"{mean('precision'):.3f} | {mean('recall'):.3f} | {len(ok)} |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("--shards", type=int, default=3)
    sub.add_parser("score")
    sub.add_parser("general")
    a = ap.parse_args()
    return {"prep": cmd_prep, "score": cmd_score, "general": cmd_general}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
