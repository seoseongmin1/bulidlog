# 공장 에너지 에이전트

철강 공장의 전력 데이터를 자연어로 분석하는 AI 에이전트입니다. "12월 16일 일요일에 왜 전력을 많이 썼을까?"라고 물으면 에이전트가 필요한 분석 도구를 골라 실행하고, 그래프와 함께 사실과 가설을 구분해 답합니다. 기획 문서는 [docs](docs)에 있습니다.

| 기능 | 내용 |
|---|---|
| 대시보드 | 연간 사용량, 최대 수요전력, 역률, CO2와 월별·시간대별·날짜별 그래프 |
| 이상한 날 | 주변 같은 요일 유형과 비교해 평소와 가장 다른 8일. 날짜를 누르면 그날의 보고서가 열립니다. |
| 일일 보고서 | 날짜를 고르면 표로 보여 주고, 버튼으로 `.md` 파일로 저장합니다. |
| AI 에이전트 | 평소 말투로 질문하면 분석 도구 9개 중 필요한 것을 골라 답합니다. |

## 구성

```
화면 (React, frontend/)  ──/api──▶  서버 (FastAPI, backend/)  ──▶  데이터베이스 (database/)
                                       └──▶ Claude API
```

- **화면:** 데이터베이스에 직접 접속하지 않습니다. 서버만 접속하므로 접속 정보가 화면에 노출되지 않습니다.
- **데이터베이스:** 원본 전력 데이터 35,040건만 넣습니다. 질문, 대화, 보고서는 저장하지 않습니다.
  - 설정이 없으면 `database/energy.db`(SQLite)를 씁니다.
  - `backend/.env`에 `DATABASE_URL`을 넣으면 그 데이터베이스(Supabase)를 씁니다.
- **계산:** 모든 수치는 서버의 분석 코드가 계산하고, Claude는 결과를 해석합니다. 그래프도 계산 결과로만 그립니다.

## 처음 한 번 (Windows PowerShell)

Python 3.15와 Node.js 26에서 확인했습니다.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
copy .env.example .env
cd ..\frontend
npm install
```

`backend/.env`에 [Claude API 키](https://platform.claude.com/)를 넣으세요. 키는 사용한 만큼 요금이 나오며 다른 사람에게 보여 주면 안 됩니다. 키가 없어도 대시보드, 이상한 날, 보고서는 작동합니다.

```
ANTHROPIC_API_KEY=발급받은_키
```

## 실행

```powershell
.\start.cmd
```

브라우저에서 http://localhost:8000 을 엽니다. 이 명령은 다음을 알아서 합니다.

1. 화면이 아직 빌드되지 않았으면 빌드합니다.
2. 데이터베이스에 전력 데이터가 없으면 `database/steel_industry_data.csv`에서 넣습니다.
3. 서버를 켭니다. 서버가 빌드된 화면도 함께 제공합니다.

포트를 바꾸려면 `.\start.cmd -Port 8001`을 씁니다.

## 개발할 때

화면 코드를 고치면서 바로 보려면 터미널 두 개를 씁니다.

```powershell
# 터미널 1: 서버
cd backend
.venv\Scripts\python -m app.loader --if-missing
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# 터미널 2: 화면 (http://localhost:5173)
cd frontend
npm run dev
```

## 테스트

```powershell
cd backend;  .venv\Scripts\python -m pytest     # 서버 (임시 SQLite만 씁니다)
cd frontend; npm test                            # 화면
```

서버 테스트는 가짜 Claude 서버를 띄워 실제 SDK를 통과시킵니다. **실제 Claude 모델의 답변 품질은 평가하지 않습니다.**

## Supabase로 바꾸기

1. [Supabase](https://supabase.com/)에서 프로젝트를 만들고 데이터베이스 비밀번호를 정합니다.
2. 프로젝트의 연결 문자열을 `backend/.env`에 `DATABASE_URL=...`로 넣습니다. `postgresql://`로 시작하는 주소를 그대로 넣으면 됩니다. 직접 연결이 안 되면 Supabase가 안내하는 풀러(pooler) 주소를 쓰세요.
3. 데이터를 넣습니다. 이때 외부에서 이 표를 읽거나 바꾸지 못하도록 행 수준 보안(RLS)도 자동으로 켭니다.
   ```powershell
   cd backend
   .venv\Scripts\python -m app.loader
   ```
4. 서버를 다시 켜면 Supabase를 씁니다. 무료 플랜은 오래 쓰지 않으면 프로젝트가 일시 중지될 수 있으니, 시연 전에 확인하세요.

SQLite로 돌아가려면 `DATABASE_URL` 줄을 지우면 됩니다.

## 한계

- 2018년 과거 데이터이며 실시간 연동이 없습니다.
- 공장 전체 전력만 있어 설비별 원인을 특정할 수 없습니다. 에이전트는 원인을 단정하지 않고 가능성으로 말합니다.
- 전기요금 데이터가 없어 금액을 계산하지 않습니다.
- 로그인과 사용량 제한이 없는 로컬 시연용입니다. 인터넷에 공개하면 다른 사람이 내 API 키로 요금을 쓸 수 있습니다.

## 데이터 출처

[Steel Industry Energy Consumption](https://archive.ics.uci.edu/dataset/851/steel+industry+energy+consumption), UCI Machine Learning Repository. DAEWOO Steel Co. Ltd (광양). [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). 원본 파일을 변경 없이 `database/`에 포함했습니다.
