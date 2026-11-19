# Round 3 사전 등록 — dettato (2026-11-19, 결과를 보기 전에 고정)

브랜치 `round3/2026-11-19`. 하니스·채점은 Round 2와 같다(채점 v2, 곡별 평균, paired 95% 부트스트랩 CI 10,000회 seed 0).
기본값·API·피아노 경로는 이 라운드에서 바꾸지 않는다. 결과는 판정과 권고까지만 낸다.

## 후보

- dettato (github.com/kobimusic/dettato, 코드·가중치 Apache-2.0). 전사기 15.3M + evidence repairer 4.9M + grouper 2.9M + 드럼 5.0M.
- 저자 기본 설정(`dettato.transcribe()` 기본값)만 쓴다. 임계값·옵션 튜닝 없음 — 개발셋으로 고를 파라미터가 없으므로 테스트는 시스템마다 1회.

## 오염 점검 (모델 카드 기준)

| 세트 | 판정 | 근거 |
|---|---|---|
| Slakh test 20곡 (신스, 실베이스 일렉·업라이트 포함) | 전사기: 깨끗 | 카드: "None of the 151 Slakh2100 test MIDI files were in the training material" |
| 〃 드럼 | 드럼킷 모델: 깨끗 | 카드: 오케스트라 모델 학습 재료에 Slakh test MIDI 12곡이 들어갔으나 Slakh 점수는 드럼킷 모델이 낸다. 라우터가 오케스트라 모델을 고른 곡은 기록한다 |
| MDB Drums 23곡 | 깨끗 | 드럼 학습 데이터: 사내 합성, Sonatina·VSCO-2·VCSL, MUSDB18-HQ·MusicNet(드럼 없는 녹음). MDB·ENST·E-GMD·ADTOF 미사용 |

비교 대상의 학습 데이터 메모: Basic Pitch는 Slakh(train)를 학습에 썼고, YourMT3+도 Slakh train으로 학습했다. 같은 렌더러라 Slakh 신스에서 두 모델이 유리할 수 있다.

## 시스템

**드럼** (`drums_r2.py`, 5클래스·8클래스 채점)
- `dettato_stem` (주 시스템): htdemucs drums 스템 → dettato 전체 체인 → is_drum 노트. 제품 드럼 경로가 스템 입력이므로 주 시스템으로 고정.
- `dettato_mix` (참고): 믹스 → dettato → is_drum 노트.

**베이스** (`run_heldout.py` 채점, 옥타브 무관 onset F1 대표)
- `stem_dettato` (주 시스템): htdemucs bass 스템 → dettato → 모든 비드럼 노트, 후처리 없음.
- `mix_dettato` (참고 경로): 믹스 → dettato → 베이스 프로그램(32~39) 트랙만. `mix_yourmt3`와 같은 규칙.

**General** (새 채점: Slakh `all_src.mid`의 30~90초 창 비드럼 전 노트, 악기 무시 multi-pitch onset F1, 50 ms·50 cent, IGNORE_HEAD 0.1 s 동일)
- `gen_basicpitch` (현행 General 기본값): 믹스 → Basic Pitch.
- `gen_dettato`: 믹스 → dettato 비드럼 전 노트.
- `gen_yourmt3` (참고): 캐시된 YourMT3+ 전체 악기 출력의 비드럼 노트.

## 판정 규칙

1. **드럼 기본값 교체**: `dettato_stem` vs `stem_adtof`, MDB 5클래스 CI 하한 > 0 그리고 Slakh에서 유의한 하락 없음(CI 상한 > 0). Round 2 규칙과 같다.
2. **상업용 폴백 후보** (새 질문, 기본값과 무관): `dettato_stem` vs `stem_egmd`, MDB 5클래스 CI 하한 > 0 이면 "ADTOF(비상업) 대신 쓸 수 있는 Apache 드럼 경로"로 기록한다. 단 드럼 학습 데이터에 MUSDB18-HQ(비상업 조건)가 포함된 점을 함께 적는다.
3. **베이스 기본값 교체**: R1 규칙 그대로 — `stem_dettato` vs `stem_basicpitch`가 slakh_realbass·slakh_realbass_up **둘 다**와 신스 slakh에서 CI 하한 > 0.
   `mix_dettato`는 "전체 곡 → 베이스" 경로 참고값으로 `mix_yourmt3`와 나란히 보고한다.
4. **General 기본값**: `gen_dettato` vs `gen_basicpitch`, Slakh CI 하한 > 0이면 "유력 후보"로만 기록한다.
   Slakh는 신스 렌더라(원칙 5) 실제 녹음 세트 없이는 기본값을 바꾸지 않는다.

## 실행 조건

- `nice -n 15`, `OMP_NUM_THREADS=2`, 무거운 작업 동시 2~3개까지. 공용 백엔드(8000)는 건드리지 않는다.
- 실패한 곡은 기록하고 paired 비교에서 뺀 n을 함께 적는다.
