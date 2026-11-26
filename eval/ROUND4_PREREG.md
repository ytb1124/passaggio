# Round 4 사전 등록 — 믹스→베이스(dettato)와 General 실제 녹음 재검증 (2026-11-21, 결과 보기 전에 고정)

Round 3(`eval/ROUND3_REPORT.md`)의 두 후속 권고를 판정한다. 기본값·API·피아노 경로는 이 라운드에서 바꾸지 않는다.
통과해도 기본값 교체는 사용자 결정이다(공용 백엔드·프론트 영향).

## A. 믹스 → 베이스 (dettato)

**질문**: "전체 곡 믹스 → 베이스 노트" 경로에서 dettato가 현행(htdemucs 베이스 스템 → Basic Pitch + 하이브리드)과
YourMT3+ 믹스 입력보다 나은가. 그렇다면 `eval/BASS_MODEL_PLAN.md`(자체 소형 모델, 6주)의 정확도 목표는 이미 달성된 것이고,
남은 과제는 크기·속도다.

**왜 새 세트인가**: Round 3에서 slakh_realbass(Fashionbass)·slakh_realbass_up(Smolken)의 mix_dettato 점수를 이미 봤다.
같은 세트로 다시 판정하면 사후 판정이 된다. 그래서 평가에 처음 쓰는 실제 녹음 베이스 음색으로 새 세트를 만든다.

- **세트 `slakh_realbass_dk`**: Slakh test 20곡(Round 3와 같은 곡·같은 30~90초 창), 베이스를 Karoryfer Black-and-Blue **darkblack reg**
  실제 녹음 단음으로 다시 렌더링(`build_realbass.py --set slakh_realbass_dk`, 반주·레벨 맞춤 방식은 기존 실베이스 세트와 같음).
  - darkblack은 어떤 평가에도 쓴 적이 없다. (같은 라이브러리의 babyblue는 개발셋 dev_realbass에 썼다.)
  - 파일 이름이 실제 음보다 한 옥타브 높다(pYIN으로 42개 전부 −12.0 ± 0.2 확인) → 인덱스 `electric_dk`에서 −12 보정.
  - 반주는 원래 믹스의 htdemucs vocals+drums+other(신스 베이스가 조금 새어 있음, 기존 세트와 같은 한계).
- **시스템**: `stem_basicpitch`(현행), `mix_dettato`(Round 3과 같은 워커 `eval/heldout/dettato_transcribe.py`, CPU, 비드럼·GM 32–39만), `mix_yourmt3`(참고).
- **지표**: `run_heldout.score_bass` 채점 v2 — pitch-class onset F1(50 ms, 대표), 엄격 F1(옥타브 포함, 필수 보조).
- **비교**: 곡별 차이의 paired 95% 부트스트랩 CI(10,000회, seed 0).

**판정 규칙**
- **A1 (전체 곡 → 베이스 경로 후보)**: `mix_dettato − stem_basicpitch`의 pitch-class F1 CI 하한 > 0 **그리고** 엄격 F1 차이 CI 하한 > −0.02.
  통과하면 "전체 곡 → 베이스" opt-in 경로 후보로 기록한다. 제품의 베이스 모드(베이스 단독 입력)는 바꾸지 않는다.
- **A2 (BASS_MODEL_PLAN 방향)**: `mix_dettato − mix_yourmt3`의 pitch-class F1 CI 하한 > 0이면,
  BASS_MODEL_PLAN의 "YourMT3+ 믹스 수준을 따라잡는다"는 정확도 목표를 dettato가 이미 넘는다고 기록하고,
  계획을 '처음부터 학습'에서 '크기·속도(증류·경량화)' 쪽으로 바꾸도록 권고한다. 불통과면 계획은 그대로 둔다.
- 참고로 MPS 처리 시간(1분 곡 기준)을 적는다. 판정에는 쓰지 않는다.

## B. General — 실제 녹음 다악기 (TRIOS)

**질문**: Slakh(신스 렌더)에서 본 gen_dettato의 큰 이득(+0.293)이 실제 녹음에서도 유지되는가.

- **세트**: TRIOS(Fritsch 2012, Zenodo 10.5281/zenodo.6797837, CC BY-NC-SA 2.0 UK, md5 0922b785…) 5곡 — 실제 녹음 실내악 트리오
  (brahms 호른·바이올린·피아노, lussier 바순·트럼펫·피아노, mozart 클라리넷·비올라·피아노, schubert 첼로·바이올린·피아노,
  take_five 색소폰·피아노·드럼). 총 약 191초, 음높이 노트 약 1,600개.
  - 입력: 배포된 `mix.wav`(모노 44.1 kHz) 그대로.
  - 정답: 곡의 음높이 있는 MIDI 트랙 전부(take_five의 kick·ride·snare는 뺀다).
  - 오염: dettato 카드가 밝힌 학습 데이터(전사기: 사내 합성 + URMP 솔로, 그루퍼: Slakh·MusicNet·MUSDB18·GuitarSet·Medley-solos-DB·IRMAS·OpenMIC)
    에 TRIOS는 없다. Basic Pitch·YourMT3+ 학습 데이터에도 TRIOS는 알려진 바 없다.
  - Bach10(dettato 카드의 평가 세트, 학습에서 제외)은 등록 양식(개인정보 입력)이 필요해 이번엔 받지 않았다.
- **시스템**: `gen_basicpitch`(현행 General), `gen_dettato`(MPS 워커 `backend/scripts/dettato_transcribe.py`, `--ckpt` 없음 = 원본), `gen_yourmt3`(참고).
- **지표**: Round 3 General과 같다 — 악기 무시 multi-pitch onset F1(같은 음높이, onset ±50 ms, 50 cent), 드럼 제외, 앞 0.1 s 무시.
- **정렬 점검(시스템 결과를 보기 전에)**: 정답 온셋과 믹스의 온셋 강도 곡선의 교차상관으로 곡별 시간 오프셋을 잰다.
  |오프셋| > 20 ms인 곡은 그만큼 정답을 옮기고 기록한다(옮긴 값은 세 시스템에 똑같이 적용).
- **비교**: 곡이 5개뿐이라 곡 단위 CI는 쓸 수 없다. **5초 구간 블록 부트스트랩**으로 한다:
  모든 곡을 5초 구간으로 나누고(약 38개), 구간을 복원 추출(10,000회, seed 0)해 TP·FP·FN 합으로 micro F1 차이의 95% CI를 낸다.
  곡별 F1도 함께 적는다.

**판정 규칙**
- **B1 (General 기본값 후보, 실제 녹음 근거)**: `gen_dettato − gen_basicpitch` micro F1 CI 하한 > 0.
  통과하면 "실제 녹음에서도 유력"으로 기록하고 기본값 교체를 권고한다(교체·속도 문제 판단은 사용자).
  불통과면 Slakh 결과만으로는 교체하지 않는다.
- 한계(결과와 상관없이 적는다): 실내악 5곡뿐이고 팝·록 실제 믹스가 아니다. 기본값을 바꾸려면 장르가 다른 실제 녹음 세트가 더 있어야 한다.

## 운영
- 무거운 작업은 nice, OMP 스레드 제한, GPU 작업은 한 번에 하나.
- 이 문서 이후 규칙을 바꾸면 날짜와 이유를 여기 적는다.
