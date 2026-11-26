"""Round 3 — dettato(github.com/kobimusic/dettato, Apache-2.0) 추론 워커. .venv-dettato/bin/python으로 실행한다.

저자 기본 설정 그대로 쓴다(임계값·옵션 변경 없음). 템포 검출·퀀타이즈 없음(dettato는 원래 하지 않는다).

part:
  all    Dettato.transcribe() 전체 체인(전사기 → evidence repairer → grouper, + 드럼 모델). 출력 MIDI = 저자 to_midi().
  drums  드럼 모델만(DrumTranscriber.transcribe). 전체 체인에서도 드럼 트랙은 음정 경로와 독립적으로 같은 오디오
         (44.1 kHz)에서 같은 함수로 나오므로 결과가 같다. 음정 경로를 건너뛰어 시간만 아낀다.

입력: --jobs <json> [[audio, out_mid, part], ...]
각 출력 옆에 <out>.json(저자 summary + 걸린 시간)을 남긴다.
"""
import argparse
import json
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--device", default=None)
    a = ap.parse_args()
    import numpy as np
    import torch
    from dettato import audio as A
    from dettato.drums import MIN_SOURCE_RATE
    from dettato.pipeline import Dettato, Track, Transcription

    torch.set_num_threads(2)
    model = Dettato.from_pretrained(a.device)
    for audio, out, part in json.loads(Path(a.jobs).read_text()):
        t = time.time()
        if part == "all":
            res = model.transcribe(audio)
        else:
            src = A.load(audio)
            tracks, info = [], {}
            if src.rate >= MIN_SOURCE_RATE:
                hits = model.drums.transcribe(src.at(44100))
                if hits:
                    d = np.array([[h["onset"], h["offset"], h["pitch"], max(1, min(127, int(round(h["velocity"] * 127))))]
                                  for h in hits], np.float64)
                    tracks.append(Track("Drums", 0, d, is_drum=True))
                info["drums"] = {"hits": len(hits), **getattr(model.drums, "last_info", {})}
            else:
                info["drums"] = f"skipped: {src.rate} Hz"
            res = Transcription(audio, src.seconds, tracks, info)
        res.save_midi(out)
        summ = res.summary()
        summ.update(seconds_run=round(time.time() - t, 1), device=str(model.device), part=part)
        Path(out).with_suffix(".json").write_text(json.dumps(summ, ensure_ascii=False, default=str))
        print(json.dumps({"out": out, "seconds": summ["seconds_run"], "device": summ["device"]}), flush=True)


if __name__ == "__main__":
    main()
