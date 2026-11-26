"""음 길이 보정 실험 — dettato 실행 + 전사기 확률 맵 저장 (.venv-dettato에서 실행). eval/NOTELEN_PREREG.md.

곡마다 dettato를 저자 기본 설정 그대로 한 번 돌리고, 증거 보정 단계가 쓴 전사기 맵(첫 run 호출, hop_frac 0.25)을 같이 저장한다.
보정(노트 끝 재계산)과 채점은 notelen.py(.venv-backend)가 한다.

    python notelen_run.py <set> <song> [<song> ...]      # set: dev | slakh | trios
출력: runs/_notelen/<set>/<song>/{notes.json, maps.npz}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
OUT = HERE / "runs" / "_notelen"
AUDIO = {"dev": HERE / "data" / "slakh_train", "slakh": HERE / "data" / "slakh", "trios": HERE / "data" / "trios"}


def main() -> int:
    import torch
    from dettato.pipeline import Dettato
    from dettato.transcriber.core import Transcriber
    from dettato_transcribe import _patch_mps_gather, pick_device

    set_name, songs = sys.argv[1], sys.argv[2:]
    device = pick_device("auto")
    if device == "mps":
        _patch_mps_gather()
    stash: dict = {}
    orig_run = Transcriber.run

    def run(self, audio, hop_frac=0.25, batch=2, taps=(), pad_batch=False):
        maps, buf = orig_run(self, audio, hop_frac=hop_frac, batch=batch, taps=taps, pad_batch=pad_batch)
        if "maps" not in stash:
            stash["maps"] = maps
        return maps, buf

    Transcriber.run = run
    model = Dettato.from_pretrained(device)
    for g in songs:
        dest = OUT / set_name / g
        if (dest / "maps.npz").exists():
            continue
        stash.clear()
        with torch.no_grad():
            res = model.transcribe(str(AUDIO[set_name] / g / "mix.wav"))
        dest.mkdir(parents=True, exist_ok=True)
        tracks = [{"name": t.name, "program": t.program, "drum": bool(t.is_drum),
                   "notes": [[float(n[0]), float(n[1]), int(n[2]), int(n[3]) if len(n) > 3 else 100] for n in t.notes]}
                  for t in res.tracks]
        (dest / "notes.json").write_text(json.dumps({"hop": float(model.transcriber.hop), "tracks": tracks}))
        m = stash["maps"]
        np.savez_compressed(dest / "maps.npz", **{k: m[k].astype(np.float16) for k in ("frame", "frame2", "offset", "offset2")})
        print(set_name, g, "ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
