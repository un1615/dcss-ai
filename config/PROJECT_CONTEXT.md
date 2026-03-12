나는 DCSS(Dungeon Crawl Stone Soup) AI 플레이어 프로젝트를 개발하고 있다.

목표
DCSS는 턴제 게임이다.
매 턴마다 현재 게임 상태를 AI에게 전달하고,
AI는 이번 턴에 누를 키 하나를 판단한다.

즉 구조는

게임 상태 수집
→ AI 판단
→ 키 입력
→ 다음 턴

이 구조로 AI가 게임을 플레이한다.

중요한 철학

이 프로젝트는 FSM 자동 플레이가 아니라
AI 플레이어를 만드는 프로젝트다.

전투는 TAB 같은 규칙을 강제로 정하지 않는다.

AI가 상황을 보고

- TAB 공격
- 방향 공격
- 이동
- 후퇴
- 계단
- 휴식
- 아이템 사용

같은 행동을 스스로 선택하게 만든다.

죽어도 괜찮다.

대신 모든 턴을 기록해서
죽은 이유를 분석하고
다음 플레이에서 같은 실수를 줄이게 만든다.

즉 경험 기반으로 생존율이 올라가는 AI를 만드는 것이 목표다.

-------------------------------------

현재 구현된 시스템

WebTiles Bot API 사용

상태 읽기
http://localhost:9090/bot/state?username=MinZZang

로그 읽기
http://localhost:9090/bot/log?username=MinZZang&n=20

키 입력
send_keys()

-------------------------------------

현재 프로젝트 구조

ai_dcss/

autopilot_v2_fight.py
AI 플레이 루프
게임 상태 읽기 → AI 판단 → 키 입력

webtiles/

webtiles/observation.py
게임 상태를 읽어서 Observation 객체 생성

- msg_tail_raw 파싱
- recent_msgs
- recent_text
- input_mode 파싱

webtiles/actions.py
게임에 키 입력 전송
send_keys()

brain/

brain_openai.py
OpenAI를 사용해서 행동 결정

policy/

simple_policy.py
기본 정책 (needs_more, has_threat 등)

tests/

send_key_probe.py
키 입력 테스트

dump_state.py
bot state 확인

msg_tail_test.py
msg_tail 파싱 테스트

obs_smoke_test.py
Observation 테스트

config/

next_chat_context.md
다음 채팅용 컨텍스트

-------------------------------------

현재 Observation에 들어있는 정보

- user
- game_id
- running
- where
- idle_time
- turn
- blocked
- last_activity_time
- recent_text
- input_mode
- recent_msgs
- msg_tail_raw

-------------------------------------

현재 AI에게 제공되는 주요 정보

- 현재 위치 문자열
- 턴 번호
- 최근 메시지 로그
- idle_time
- input_mode

-------------------------------------

현재 입력 가능한 키

TAB
o
.
5
SPACE
ESC

확장 예정

h j k l y u b n
> <
f
v
i
W

-------------------------------------

현재 문제

AI에게 주는 정보가 부족하다.

현재는 텍스트 로그 기반 판단이라

- 몬스터 위치
- 플레이어 좌표
- 맵 정보
- 계단 위치

같은 전술 정보가 부족하다.

-------------------------------------

다음 개발 목표

1. Observation 강화

msg_tail_raw에서

- player position
- map cells
- 주변 타일

파싱

2. Replay 시스템 구축

runs/run_xxx.jsonl

형태로

observation
action
result

를 기록

3. AI에게 맵 제공

플레이어 중심 ASCII 맵 생성

예

#######
#..@..#
#..g..#
#..>..#
#######

-------------------------------------

이 프로젝트는
AI 플레이어를 만드는 프로젝트이며
FSM 자동화 프로젝트가 아니다.