"""dettato 전사 래퍼 — 격리 venv(.venv-dettato)에서 실행된다.

모델/코드 출처: github.com/kobimusic/dettato (코드·가중치 Apache-2.0), 패키지 dettato==2.0.0.
가중치: HuggingFace kobimusic/dettato, -evidence, -grouper, -drums (첫 실행 때 내려받아 캐시).
저자 기본 설정 그대로(Round 3 홀드아웃과 같은 설정, eval/ROUND3_REPORT.md).

MPS(Apple GPU): 패키지 2.0.0은 cuda/cpu만 고른다. MPS로 돌리면 grouper의 gather()가 float64 노트 배열을
그대로 MPS로 올리다 실패한다. 설치된 패키지는 고치지 않고, 여기서 gather만 감싸 float32로 넘긴다
(gather 안에서 어차피 .float()로 바꾸므로 결과는 같다 — CLAUDE.md Round 3 섹션에 CPU 대비 비교 기록).

사용법:
    python dettato_transcribe.py input.wav output.mid [--device auto|mps|cpu|cuda] [--threads N]
마지막 줄에 JSON 한 줄({"notes", "tracks", "seconds", "audio_seconds", "device"})을 출력한다.
"""

from __future__ import annotations

import argparse
import json
import time


def _patch_mps_gather() -> None:
    import numpy as np
    from dettato.grouper import core

    if getattr(core.gather, "_passaggio_f32", False):
        return
    orig = core.gather

    def gather(P, H, S, notes, hop):
        return orig(P, H, S, np.ascontiguousarray(notes, dtype=np.float32), hop)

    gather._passaggio_f32 = True
    core.gather = gather


def pick_device(requested: str) -> str:
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--device", default="auto", choices=("auto", "mps", "cpu", "cuda"))
    ap.add_argument("--threads", type=int, default=0, help="CPU 스레드 수(0 = torch 기본값)")
    a = ap.parse_args()

    import torch
    from dettato.pipeline import Dettato

    if a.threads > 0:
        torch.set_num_threads(a.threads)
    device = pick_device(a.device)
    if device == "mps":
        _patch_mps_gather()
    t = time.time()
    model = Dettato.from_pretrained(device)
    res = model.transcribe(a.input)
    res.save_midi(a.output)
    tracks = [{"name": tr.name, "program": tr.program, "drum": tr.is_drum, "notes": int(len(tr.notes))}
              for tr in res.tracks]
    print(json.dumps({
        "notes": sum(tr["notes"] for tr in tracks),
        "tracks": tracks,
        "seconds": round(time.time() - t, 1),
        "audio_seconds": round(float(res.seconds), 1),
        "device": device,
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
