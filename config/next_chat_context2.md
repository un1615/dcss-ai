# DCSS AI 프로젝트 컨텍스트 (다음 채팅용)

## 0) 한 줄 목표 (내가 원하는 것)
- DCSS는 턴제 게임이고, 매 턴마다 현재 상황(최대한 많은 정보)을 AI에게 제공한다.
- AI가 매 턴 “이번 턴에 누를 키(또는 1개 행동)”를 판단해서 입력한다.
- TAB만 강제 같은 룰 기반(FSM) 자동화가 아니라, 공격/후퇴/이동/계단/아이템 등도 AI가 선택한다.
- 죽어도 괜찮다. 대신 매 판의 실수를 기록하고, 그 기록을 바탕으로 다음 판에서 같은 실수를 줄여 “생존율이 올라가는” 구조를 만들고 싶다.
- 안전장치로 막는 방식이 아니라, 경험(로그/리플레이) 기반으로 개선되게 하고 싶다.
- 비용 문제 때문에 “매 한 칸 이동마다 AI 호출”은 피하고 싶지만, 내가 원하는 궁극 형태는 ‘턴마다 AI 판단’이다.
  -> 해결 방향: AI 호출은 상황에 따라 조절 가능(쿨다운/캐시/이벤트 기반)하지만, 기본 철학은 AI가 게임을 한다.

## 1) 현재까지 된 것 (확실히 성공)
- 로컬 WebTiles Bot API 사용 중:
  - GET http://localhost:9090/bot/state?username=MinZZang  -> 상태 수집 OK
  - GET http://localhost:9090/bot/log?username=MinZZang&n=20 -> 로그 수집 OK
- PowerShell에서 URL 직접 입력하면 오류나므로 Invoke-RestMethod 사용:
  - Invoke-RestMethod "http://localhost:9090/bot/state?username=MinZZang"
- send_keys로 키 입력 전송 검증 완료:
  - python -m tests.send_key_probe
  - '.' 'o' '5' ' ' '\t' '\x1b'(ESC) 전송 OK
- Observation 파서 구현:
  - msg_tail_raw에서 텍스트 메시지 recent_msgs/recent_text 추출
  - input_mode(msg_tail의 {"msg":"input_mode","mode":...}) 파싱해서 Observation.input_mode에 넣음
- autopilot_v2_fight.py 실행하며 실제 플레이가 굴러감:
  - 탐험 o, 전투 TAB 등 AI/정책 기반으로 턴 진행 확인됨

## 2) 오늘 핵심 전환점 (FSM -> AI 플레이어 방향 확정)
- 사용자는 “전투는 tab” 같은 고정 룰 기반 자동화가 아니라,
  AI가 상황을 보고 tab/방향공격/후퇴/계단/아이템 등을 스스로 판단하는 ‘AI 플레이어’를 원함.
- 죽어도 괜찮고, 그 경험을 기록해서 다음 판에서 개선되는 시스템(리플레이/포스트모템)이 핵심.

## 3) 현재 문제 / 관찰
- 메시지 기반으로만 판단하면 “도망 루트/포지셔닝”이 어려움.
- 그래서 AI에게 더 많은 정보를 주기 위해 msg_tail에서 구조화 정보 파싱이 필요:
  - player 좌표(pos)
  - map cells (지형/문/계단/가능하면 몬스터)
  - HP/MP 등 상태(가능하면)
- OpenAI 호출이 오래 걸리면 루프가 멈출 수 있음(KeyboardInterrupt 경험)
  - 향후 brain_openai에 timeout 필요
- Unknown command 루프 같은 현상은 입력 모드/메뉴 처리와 연결될 수 있음(input_mode가 중요)

## 4) 다음 개발 방향 (반드시 포함)
### 방향 A: “AI 턴 플레이 엔진” 고도화
- 루프는 고정: (obs fetch) -> (AI decide) -> (send key) -> (log/replay)
- AI는 “이번 턴 행동 1개”를 JSON으로 출력 (예: {"action":"k","reason":"..."} )
- 허용 키 목록(action space)을 AI에게 명시해서 엉뚱한 키를 줄인다.
  - 초기 허용 키: 이동(hjkl yubn), TAB, '.', '5', 'o', '>', '<', SPACE, ESC
  - 이후 확장: f/v/i/W/q 등 메뉴/타겟팅 처리 후

### 방향 B: “죽어도 개선되는 학습(경험) 시스템”
- 매 턴을 JSONL로 기록하는 replay 시스템 구축:
  - obs(가능한 많이), action, result(다음 obs 변화), turn, where, recent_msgs 등
- 죽으면 postmortem(사후 분석) 스크립트로:
  - 무엇이 위험이었는지/어떤 선택이 나빴는지 요약
  - 다음 런 프롬프트에 “교훈/메모리”로 주입해서 반복 실수 감소

### 방향 C: “Observation 최대화”
- msg_tail_raw에서 다음을 구조화해서 Observation에 추가:
  - player_pos (x,y)
  - 주변 map 요약(플레이어 중심 15x15 ASCII)
  - 계단/문 위치
  - (가능하면) 몬스터 표식/위치
  - (가능하면) HP/MP 등

## 5) 주요 파일/모듈 (현재)
- webtiles/observation.py
  - Observation dataclass
  - fetch_observation()
  - msg_tail_raw 파싱: recent_msgs/recent_text, input_mode
- webtiles/actions.py
  - send_keys()
- policy/simple_policy.py
  - needs_more(), has_threat(), choose_action() (초기 규칙이지만 AI 중심으로 갈 예정)
- autopilot_v2_fight.py
  - main loop: fetch -> decide -> send

## 6) 내일 바로 할 작업 (작게 시작)
1) replay 로거(JSONL) 추가: 매 턴 obs/action/result 기록
2) brain_openai 프롬프트 강화:
   - 허용 키 목록 포함
   - 반드시 JSON 출력
   - timeout 적용
3) Observation 확장 1차:
   - msg_tail_raw에서 player pos 파싱
   - map cells 일부라도 파싱해서 AI에게 제공 (초기엔 raw도 OK)

## 7) 실행 명령
- 상태 확인:
  - Invoke-RestMethod "http://localhost:9090/bot/state?username=MinZZang"
- 키 전송 테스트:
  - python -m tests.send_key_probe
- 자동 플레이:
  - python autopilot_v2_fight.py