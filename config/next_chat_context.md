# DCSS AI Project Context (Next Chat Start)

## 프로젝트 목표

DCSS (Dungeon Crawl Stone Soup)를 AI가 자동으로 플레이하도록 만드는
프로젝트.

목표: - WebTiles 기반 로컬 DCSS 서버에서 AI 자동 플레이 - AI가 게임
상태를 읽고 행동을 결정 - 장기적으로 방송 가능한 AI 플레이어 제작 -
목표: 최소 3룬 클리어

사용자 수준: - Python 초보자 - 단계적으로 구조를 이해하면서 개발 진행
필요

------------------------------------------------------------------------

# 현재 개발 상태

현재 로컬 WebTiles 서버(Docker)에서 Bot API 패치를 통해 AI가 게임을
제어할 수 있는 기반을 만들었다.

### 성공한 기능

1.  게임 상태 읽기

GET /bot/state

예시: http://localhost:9090/bot/state?username=MinZZang

반환 데이터 예시

{ "ok": true, "user": "MinZZang", "game_id": "dcss-web-trunk",
"running": true, "where": "L1 GnGl, D:1", "idle_time": 550, "turn":
3993, "blocked": "set()", "last_activity_time": 1772572315 }

------------------------------------------------------------------------

2.  게임 입력 보내기

POST /bot/input

예시

POST http://localhost:9090/bot/input { "keys": "." }

입력 성공 시 last_activity_time 변화 확인 가능

------------------------------------------------------------------------

3.  게임 로그 읽기

GET /bot/log

예시 http://localhost:9090/bot/log?username=MinZZang&n=20

로그 파일 위치 /data/rcs/MinZZang/MinZZang.txt

로그 내용 예시

There are no monsters in sight!

Notes Turn \| Place \| Note

이 로그를 이용해 AI가 게임 상황을 이해하도록 만들 예정.

------------------------------------------------------------------------

# 현재 프로젝트 폴더 구조

ai_dcss/

main.py

config/ project_context.txt project_state.txt next_chat_context.md

controller/ action_to_queue.py controller_webtiles.py

workers/ reader_worker.py input_worker.py

webtiles/ webtiles_client.py webtiles_input.py webtiles_reader.py

policy/ policy.py policy_openai.py

server_patch/ bot_api.py server.py server_entry.py server_webtiles.py

tests/ main_webtiles_test.py main_webtiles_obs_test.py ws_listen.py
ws_probe.py

------------------------------------------------------------------------

# 실행 방법

1.  Docker WebTiles 실행 확인 docker ps

컨테이너 dcss-webtiles

2.  WebTiles 접속 http://localhost:9090

username: MinZZang

3.  상태 확인 curl http://localhost:9090/bot/state?username=MinZZang

4.  로그 확인 curl http://localhost:9090/bot/log?username=MinZZang&n=20

5.  Python 테스트 python tests/main_webtiles_obs_test.py

6.  메인 실행 python main.py

------------------------------------------------------------------------

# 다음 개발 목표

AI가 사용할 Observation 구조 만들기

예시

obs = { turn where idle_time last_activity_time map recent_messages }

데이터 출처 state API log API

------------------------------------------------------------------------

# 중요 정보

username: MinZZang game_id: dcss-web-trunk base_url:
http://localhost:9090
