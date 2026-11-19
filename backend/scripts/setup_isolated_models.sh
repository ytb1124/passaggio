#!/usr/bin/env bash
# YourMT3+ / ADTOF / dettato 격리 venv와 모델을 공식 저장소에서 설치한다.
# 메인 .venv-backend의 torch/numpy 스택을 건드리지 않기 위해 각각 별도 venv를 쓴다.
#   YourMT3+ : HuggingFace Space mimbres/YourMT3 (코드 + YPTF.MoE+Multi noPS 체크포인트)
#   ADTOF    : GitHub MZehren/ADTOF (Frame_RNN adtofAll 가중치 포함)
#   dettato  : GitHub kobimusic/dettato 2.0.0 (Apache-2.0, 가중치 HF kobimusic/dettato{,-evidence,-grouper,-drums})
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=${PYTHON:-python3.10}

if [ ! -x .venv-yourmt3/bin/python ]; then
  "$PY" -m venv .venv-yourmt3
  .venv-yourmt3/bin/pip install --upgrade pip
  .venv-yourmt3/bin/pip install torch torchaudio "lightning>=2.2.1" transformers==4.45.1 \
    einops librosa mido numpy==1.26.4 deprecated huggingface_hub mir_eval soundfile pretty_midi wandb
fi
.venv-yourmt3/bin/python - <<'EOF'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="mimbres/YourMT3", repo_type="space", local_dir="third_party/yourmt3",
    allow_patterns=["amt/src/**", "model_helper.py", "README.md",
                    "amt/logs/2024/mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops/checkpoints/last.ckpt"],
    ignore_patterns=["*.DS_Store", "amt/src/.coverage"],
)
EOF

if [ ! -d third_party/adtof ]; then
  git clone --depth 1 https://github.com/MZehren/ADTOF.git third_party/adtof
fi
if [ ! -x .venv-adtof/bin/python ]; then
  "$PY" -m venv .venv-adtof
  .venv-adtof/bin/pip install --upgrade pip setuptools wheel Cython numpy
  .venv-adtof/bin/pip install ./third_party/adtof "tf_keras~=2.21.0"
fi
# dettato: Round 3에서 평가한 커밋에 고정한다(eval/ROUND3_REPORT.md). General 모드 선택 백엔드.
if [ ! -x .venv-dettato/bin/python ]; then
  "$PY" -m venv .venv-dettato
  .venv-dettato/bin/pip install --upgrade pip
  .venv-dettato/bin/pip install "dettato @ git+https://github.com/kobimusic/dettato@c4c52e051e988c9d469659cb5d7d0dbc4bd01edd"
fi
# 가중치 4종(전사기·evidence·grouper·드럼)을 HF 캐시로 미리 받는다.
.venv-dettato/bin/python -c "from dettato.pipeline import Dettato; Dettato.from_pretrained('cpu')"

echo "isolated models ready"
