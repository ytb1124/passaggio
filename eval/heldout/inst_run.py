"""악기 이름 게이트 실험 — dettato 실행 + grouper 트랙별 평균 악기 확률 저장 (.venv-dettato). eval/INST_PREREG.md.

    python inst_run.py <set> <song> [<song> ...]      # set: dev | slakh | trios
출력: runs/_inst/<set>/<song>/{notes.json, track_probs.npy}  (track_probs 행 = notes.json의 드럼 아닌 트랙 순서)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
OUT = HERE / "runs" / "_inst"
AUDIO = {"dev": HERE / "data" / "slakh_train", "slakh": HERE / "data" / "slakh", "trios": HERE / "data" / "trios"}


def main() -> int:
    import torch
    from dettato.grouper import core
    from dettato.pipeline import Dettato
    from dettato_transcribe import _patch_mps_gather, pick_device

    set_name, songs = sys.argv[1], sys.argv[2:]
    device = pick_device("auto")
    if device == "mps":
        _patch_mps_gather()
    stash: dict = {}
    orig = core.decode

    def decode(P, notes, th, **kw):
        groups = orig(P, notes, th, **kw)
        stash["probs"], stash["groups"] = np.asarray(P["probs"], np.float32), groups
        return groups

    core.decode = decode
    model = Dettato.from_pretrained(device)
    for g in songs:
        dest = OUT / set_name / g
        if (dest / "track_probs.npy").exists():
            continue
        stash.clear()
        with torch.no_grad():
            res = model.transcribe(str(AUDIO[set_name] / g / "mix.wav"))
        dest.mkdir(parents=True, exist_ok=True)
        groups = sorted(stash.get("groups", []), key=lambda t: -len(t[1]))  # Grouper._tracks와 같은 순서
        tp = np.stack([stash["probs"][np.asarray(ids)].mean(0) for _, ids in groups]) if groups else np.zeros((0, 73), np.float32)
        tracks = [{"name": t.name, "program": t.program, "drum": bool(t.is_drum),
                   "notes": [[float(n[0]), float(n[1]), int(n[2]), int(n[3]) if len(n) > 3 else 100] for n in t.notes]}
                  for t in res.tracks]
        assert len(tp) == sum(not t["drum"] for t in tracks), (g, len(tp), len(tracks))
        (dest / "notes.json").write_text(json.dumps({"tracks": tracks, "group_inst": [int(k) for k, _ in groups]}))
        np.save(dest / "track_probs.npy", tp)
        print(set_name, g, "ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
