# Round 4 결과 — 믹스→베이스(dettato)와 General 실제 녹음 재검증 (2026-11-21)

사전 등록: `eval/ROUND4_PREREG.md`(결과 보기 전에 고정, 바꾸지 않음). 기본값·API·피아노 경로·공용 백엔드는 바꾸지 않았다.

## 요약

| 판정 | 규칙 | 결과 |
|---|---|---|
| **A1 전체 곡 → 베이스 경로 후보** | mix_dettato − 현행, pitch-class CI 하한 > 0, 엄격 CI 하한 > −0.02 | **통과** (+0.216 [+0.102, +0.316], 엄격 +0.231 [+0.123, +0.328]) |
| A2 BASS_MODEL_PLAN 방향 전환 | mix_dettato − mix_yourmt3, pitch-class CI 하한 > 0 | **불통과** (+0.053 [−0.064, +0.153]) |
| **B1 General 실제 녹음** | gen_dettato − gen_basicpitch, micro F1 CI 하한 > 0 | **통과** (+0.222 [+0.187, +0.257]) |

## A. 믹스 → 베이스 — 새 실베이스 세트 `slakh_realbass_dk`

Slakh test 20곡, 베이스를 평가에 처음 쓰는 실제 녹음 일렉(Black-and-Blue darkblack reg)으로 다시 렌더링했다.
렌더 확인: 베이스 단독 오디오의 pYIN 음높이가 정답과 98.6~100% 일치, 옥타브 어긋남 0(2곡 점검).

| 시스템 | pitch-class F1 | 엄격 F1(옥타브 포함) |
|---|---|---|
| stem_basicpitch (현행: htdemucs 베이스 스템 → BP + 하이브리드) | 0.658 | 0.637 |
| **mix_dettato** (믹스 → dettato, GM 32–39) | **0.874** | **0.867** |
| mix_yourmt3 (참고) | 0.821 | 0.423 |

| 비교 (paired 95% CI, 20곡) | pitch-class | 엄격 |
|---|---|---|
| mix_dettato − 현행 | **+0.216 [+0.102, +0.316]** | **+0.231 [+0.123, +0.328]** |
| mix_dettato − mix_yourmt3 | +0.053 [−0.064, +0.153] | +0.445 [+0.302, +0.564] |
| mix_yourmt3 − 현행 | +0.163 [+0.089, +0.247] | — |

- **A1 통과**: 처음 보는 실제 녹음 음색에서도 Round 3(Fashionbass·Smolken)와 같은 방향이 재현됐다. "전체 곡 → 베이스" opt-in 경로 후보로 기록한다.
- **A2 불통과**: pitch-class F1에서는 YourMT3+ 믹스 입력과 유의한 차이가 없다. 규칙대로 BASS_MODEL_PLAN은 그대로 둔다.
  - 다만 **엄격 F1(옥타브 포함)은 dettato가 압도적**이다(+0.445). YourMT3+는 음이름은 맞혀도 옥타브를 자주 틀린다(이 세트 엄격 0.423).
    BASS_MODEL_PLAN이 "지켜야 한다"고 한 것이 바로 옥타브 정확도였으므로, 계획을 다시 볼 때 이 수치를 근거로 쓸 수 있다(사전 등록 판정은 아님).
- 실패 사례: **Track01898**에서 dettato가 베이스 노트를 전부 일렉 피아노(program 4)로 배정해 베이스 0노트(F1 0). 이 곡의 베이스는
  37~68로 음역이 매우 높다. Round 3 실베이스 세트에서도 같은 곡에 베이스 트랙이 없었다. 전사 실패가 아니라 **악기 배정(grouper) 실패**다.
  제품 경로로 쓰려면 "베이스 트랙이 없으면 최저 성부를 베이스로" 같은 폴백을 개발셋에서 따로 검토해야 한다.
- 속도: CPU 2스레드에서 60초 곡당 약 190초(이번 실측). MPS는 42~48초(CLAUDE.md 기존 측정).

## B. General — TRIOS(실제 녹음 실내악 5곡)

TRIOS(Zenodo 10.5281/zenodo.6797837, md5 일치, CC BY-NC-SA 2.0 UK) 5곡, 약 191초, 정답 1,528노트(드럼 트랙 제외).
비교는 5초 구간 39개 블록 부트스트랩(10,000회, seed 0), TP·FP·FN 합으로 micro F1.

| 시스템 | micro F1 [95% CI] | Basic Pitch 대비 [95% CI] | brahms | lussier | mozart | schubert | take_five |
|---|---|---|---|---|---|---|---|
| gen_basicpitch (현행) | 0.682 [0.642, 0.722] | — | 0.597 | 0.506 | 0.767 | 0.681 | 0.801 |
| **gen_dettato** | **0.904 [0.882, 0.925]** | **+0.222 [+0.187, +0.257]** | 0.870 | 0.859 | 0.908 | 0.904 | 0.966 |
| gen_yourmt3 (참고) | 0.737 [0.688, 0.783] | +0.055 [+0.015, +0.094] | 0.689 | 0.544 | 0.759 | 0.781 | 0.844 |

- **B1 통과**: 5곡 모두에서 dettato가 가장 높다. Slakh(신스)에서 본 +0.293이 실제 녹음에서도 +0.222로 유지됐다.
- **정렬 보정에 대한 주의(중요)**: 사전 등록 규칙대로 정답을 곡마다 +30~40 ms 옮겼다(온셋 강도 곡선 교차상관이 20 ms를 넘어서).
  보정 없이 다시 재면(기록용, 판정 아님) Basic Pitch 0.656 / **dettato 0.938** / YourMT3+ 0.870이다.
  dettato의 결론은 그대로지만 YourMT3+ 점수는 보정에 크게 흔들린다. 온셋 강도 곡선은 실제 어택보다 늦게 솟는 편향이 있어
  이번 보정은 정답을 실제보다 늦게 옮겼을 가능성이 높다. **YourMT3+와의 비교(참고값)는 이 세트로는 결론 내지 않는다.**
  다음 라운드에서는 정렬 점검을 온셋 강도 곡선이 아니라 어택 발치(25% 교차점) 기준으로 바꾼다.
- 한계: 실내악 5곡(클래식 4 + 재즈 1)뿐이다. 팝·록 실제 믹스, 보컬이 있는 곡은 없다. Bach10은 등록 양식(개인정보) 때문에 받지 않았다.

## 추가 — 음 길이까지 본 재채점 (2026-11-21, 기록용·사전 등록 판정 아님)

위 General 수치는 음 시작·음높이만 봤다(`offset_ratio=None`). 실제 결과물에서 take_five의 dettato 노트가 정답보다 훨씬 짧게 보여서,
음 끝까지 맞아야 정답으로 치는 기준(mir_eval 기본: 길이의 20% 또는 50 ms 이내)으로 다시 채점했다. 스크립트는 세션 스크래치패드의 `rescore_offset.py`,
결과는 `eval/heldout/runs/round4_general/offset_rescore.json`.

| 세트 | 시스템 | 시작만 F1 | 시작+끝 F1 [95% CI] | Basic Pitch 대비 [95% CI] |
|---|---|---|---|---|
| Slakh 20곡 | gen_basicpitch | 0.451 | 0.154 [0.125, 0.186] | — |
| | **gen_dettato** | 0.744 | 0.489 [0.407, 0.565] | **+0.335 [+0.268, +0.395]** |
| | gen_yourmt3 | 0.746 | 0.527 [0.431, 0.618] | +0.373 [+0.291, +0.449] |
| TRIOS 5곡 | gen_basicpitch | 0.682 | 0.225 [0.193, 0.257] | — |
| | **gen_dettato** | 0.904 | 0.371 [0.317, 0.428] | **+0.146 [+0.101, +0.194]** |
| | gen_yourmt3 | 0.737 | 0.369 [0.312, 0.431] | +0.145 [+0.072, +0.219] |

- **dettato가 Basic Pitch보다 낫다는 결론은 음 길이를 넣어도 유지된다**(두 세트 모두 CI 하한 > 0). 기본값 변경을 되돌릴 근거는 아니다.
- 하지만 **절대 수준은 셋 다 낮다.** 시작만 보면 0.90이던 dettato가 TRIOS에서 0.37이다. 음 끝을 잘 못 맞힌다.
- 노트 길이 중간값(TRIOS): 정답 0.485 s, dettato 0.285 s, Basic Pitch 0.277 s, YourMT3+ 0.382 s. dettato는 음을 짧게 끊는 경향이 있다(take_five에서 특히 심함: 0.13 s 대 0.31 s, 시작+끝 F1 0.347).
- 음 길이 기준에서는 dettato와 YourMT3+가 비슷하다(TRIOS 0.371 대 0.369, Slakh 0.489 대 0.527). 시작 기준의 큰 차이는 길이 기준에서 사라진다.
- 교훈: General 평가는 앞으로 **시작만 F1과 시작+끝 F1을 같이 보고**한다. 음 길이 개선(노트 끝 연장 후처리 등)은 별도 사전 등록 후 개발셋에서 본다.

## 권고 (실행은 사용자 결정)

1. **General 기본값을 dettato로 바꾸는 것을 권고한다.** Slakh(+0.293)와 실제 녹음(+0.222) 둘 다 큰 폭이고 라이선스도 Apache-2.0이다.
   남은 문제: 속도(MPS 0.7× 실시간, CPU 약 3× 실시간), 크기(전사기 15.3M + grouper·evidence), 그리고 `general_dettato.mid`가 악기별 트랙 + 드럼 트랙을
   내므로 프론트가 이를 어떻게 보여 줄지. 기본값 변경은 공용 백엔드 재시작과 프론트 확인이 필요해 이번엔 하지 않았다.
   가장 작은 변경은 `backend=dettato`를 general 기본으로 바꾸고 venv가 없으면 지금처럼 Basic Pitch로 폴백하는 것이다.
2. **"전체 곡 → 베이스" 경로(opt-in)를 dettato로 만든다.** 세 개의 서로 다른 실제 녹음 베이스 음색에서 현행을 크게 앞선다.
   그 전에 Track01898 같은 악기 배정 실패에 대한 폴백을 개발셋(dev_realbass)에서 정한다.
3. **BASS_MODEL_PLAN**: 사전 등록 규칙(A2)으로는 방향을 바꾸지 않는다. 다만 옥타브(엄격 F1)까지 보면 dettato가 이미 계획의 목표를 넘으므로,
   6주 계획을 시작하기 전에 "dettato 증류·경량화"를 대안으로 새로 사전 등록해 비교하는 것을 권한다.

## 만든 것 (커밋하지 않음)
- `eval/ROUND4_PREREG.md`, 이 보고서
- `eval/heldout/build_realbass.py`: `slakh_realbass_dk` 세트 추가. `data/raw/samples_src/realbass_index.json`: `electric_dk`(168샘플, −12 보정)
- `eval/heldout/run_heldout.py`: BASS_SETS에 `slakh_realbass_dk` 추가(기존 세트 동작 불변)
- `eval/heldout/round4_general.py`: TRIOS 준비·전사·블록 부트스트랩 채점
- 데이터: `eval/heldout/data/slakh_realbass_dk/`, `eval/heldout/data/trios/`, 원본 `data/raw/trios_dl/`(93 MB zip + 풀린 파일)
- 결과: `eval/heldout/runs/round4_bass_results.json`, `eval/heldout/runs/round4_general/results.json`
- htdemucs 분리 캐시 `eval/heldout/runs/_sep`(808 MB, Slakh test 재분리)
