# axis_migration 웹 뷰어

Next.js App Router에서 기존 자료 탐색 화면을 실행합니다. 시작 화면은
`2025 / 09월 → 수량·치수·계산 기준`입니다. 표, 검색, 페이지 이동, 3D 관계도,
업무별 헤더와 CSV 다운로드를 사용할 수 있습니다. 원본 근거 화면에는 가져온
파일 연결, 위치와 추출값을 보여줍니다. 원본 파일, PDF 미리보기, 원본 시트 화면,
SQLite SQL 내보내기는 기존 로컬 뷰어에서 확인할 수 있습니다.

## 로컬 3D 관계도에서 MCP 작업 검토하기

기존 관계도 서버를 예를 들어 `127.0.0.1:62117`에서 실행합니다. 같은
컴퓨터에서 Next.js 뷰어가 기존 자료와 MCP의 검토 화면을 함께 제공합니다.
Supabase를 거치지 않고 기존 관계도의 데이터와 MCP 실행 폴더를 사용합니다.

```powershell
$env:AXIS_LOCAL_GRAPH_URL = 'http://127.0.0.1:62117'
$env:AXIS_LOCAL_REVIEW_ROOT = 'D:\작업\output'
npm run build
npm run start -- -H 127.0.0.1 -p 62116
```

`AXIS_LOCAL_REVIEW_ROOT`는 원본 폴더 옆의 `output` 경로입니다. 이 경로
아래의 `<원본 폴더 이름>/<실행 ID>/`에서 열린 검토를 찾습니다. MCP로
작업을 시작하고 검토 준비가 되면 관계도 페이지를 새로고침한 뒤 **자료 범위**에서
해당 실행의 **구조 검토**를 선택합니다. 제안한 표가 3D 관계도에 나타나며,
같은 화면에서 헤더 검토와 원본 근거를 열 수 있습니다. **이 구조로 확정하고 변환**을 누르면
실행기가 SQLite를 생성하고 검증합니다. 검증 후에는 같은 3D 뷰어에서
변환된 표, 실제 외래 키 관계, 원본 행을 함께 봅니다.
로컬 검토를 사용할 때 Next.js 서버를 `127.0.0.1`에 연결합니다.

## Supabase 준비와 데이터 가져오기

1. 사용할 Supabase 프로젝트의 SQL Editor에서 [schema.sql](supabase/schema.sql)을
   실행합니다. `axis_viewer` 스키마는 REST API로 공개할 필요가 없습니다.
2. `web` 폴더에서 `npm ci`를 실행합니다. Python으로 기존 뷰어 설정과 SQLite를
   읽습니다. Python 명령이 다르면 `AXIS_PYTHON`으로 실행 파일을 지정합니다.
3. 기존 뷰어 실행 파일과 대상 자료 범위를 지정합니다.

   ```powershell
   node scripts/import.mjs --dry-run "D:\결과폴더\integrated_server.py" september prior
   ```

4. 쓰기 권한이 있는 Supabase 접속 문자열을 로컬 환경 변수
   `AXIS_IMPORT_DATABASE_URL`에 설정하고 다음 명령을 실행합니다.

   ```powershell
   node scripts/import.mjs "D:\결과폴더\integrated_server.py" september prior
   ```

   지정한 자료 범위를 한 트랜잭션으로 가져옵니다. 같은 이름으로 다시 가져오면
   해당 자료 범위가 교체됩니다. 가져오는 내용에는 추출값과 관계도 근거가
   포함됩니다. 로컬에서 `--dry-run`으로 범위와 행 수를 확인할 수 있습니다.

## Vercel에서 실행

- 프로젝트의 **Root Directory**는 `web`, **Framework Preset**은 Next.js,
  **Node.js Version**은 22.x로 설정합니다.
- Vercel 환경 변수 `DATABASE_URL`에 Supabase **Transaction pooler** 접속
  문자열을 등록합니다. PostgreSQL 읽기 계정에는 다음 권한만 필요합니다.
  `axis_viewer_reader`는 Supabase에서 만든 실제 읽기용 로그인 역할로 바꿉니다.

  ```sql
  grant usage on schema axis_viewer to axis_viewer_reader;
  grant select on all tables in schema axis_viewer to axis_viewer_reader;
  ```

- `DATABASE_CA_PEM`에 Supabase Database Settings에서 받은 CA 인증서의
  PEM 내용을 등록하면 PostgreSQL 연결에서 TLS 인증서를 확인합니다.

- 뷰어 홈은 조회 번호 없이 열립니다. `AXIS_VIEWER_PASSWORD`에는 16자 이상의
  서버 암호를 설정합니다. MCP 조회 번호로 연 자료의 세션을 확인할 때 사용합니다.
  수동으로 가져온 자료는 기존 `axis` 기본 인증을 통해 볼 수 있습니다.
- 같은 설정으로 로컬에서 실행하려면 [.env.example](.env.example)을
  `.env`로 복사해 값을 채우고 `npm run dev`를 실행합니다.

기존 화면의 스타일과 관계도는 `public/`에 있습니다. 회사 DB, 추출 데이터,
원본 파일, 접속 문자열은 앱과 Git 저장소 밖에서 관리합니다.

## MCP 폴더 결과를 운영에서 조회

1. Supabase의 기존 뷰어 스키마에 [folder-results.sql](supabase/folder-results.sql)을
   적용한 뒤 [eight-digit-access.sql](supabase/eight-digit-access.sql)을 적용합니다.
   전용 뷰어 역할에는 `axis_viewer.open_result_code(text,text)` 실행 권한과
   `axis_viewer.lookup_failures`의 조회·삽입·수정·삭제 권한과 해당 역할의
   RLS 정책을 설정합니다.
   로컬 `.env`의 `DATABASE_URL` 또는 `AXIS_IMPORT_DATABASE_URL`에
   해당 프로젝트의 쓰기 연결을 설정하고 `AXIS_VIEWER_URL`은 운영 주소로 설정합니다.
2. 로컬 Axis Migration MCP에서 `start_folder`로 분석을 시작합니다.
   `folder_status`가 돌려주는 검토 주소에서 구조를 확정하면 변환과 SQLite 검증이 시작됩니다.
3. 검증 후 변환된 행과 관계 근거를 Supabase에 올립니다. `folder_status`에
   `lookup_code`와 `viewer_url`이 표시됩니다. 링크를 열거나 운영 화면의
   **MCP 자료 조회**에서 8자리 번호를 입력합니다. 해당 자료만 열립니다.
   조회 번호를 받은 사람은 자료를 볼 수 있으므로 접근을 허용할 사람에게만 공유합니다.

업로드나 운영 조회가 실패하면 `resume_folder`로 같은 작업을 이어갑니다.
이미 등록한 같은 작업에는 기존 코드를 다시 사용합니다. MCP에서
`publish=false`를 지정하면 로컬까지만 진행합니다.

## 웹 문서 분석

웹 홈의 **문서 올리고 분석하기**는 `/documents`에서 이용합니다. 브라우저가 파일을 읽고, 분석을 시작할 때 추출 본문과 위치를 서버에 보냅니다. 본문을 OpenAI 임베딩으로 검색하고 관련 구절을 대화 모델에 보내 요약, 인용, 관계 및 DB 구조를 제안합니다. 서버에는 본문과 주제별 결과를 보관합니다. 원본 파일은 브라우저에만 있습니다. 작업한 브라우저에서 새 주제를 추가할 수 있고, 다른 브라우저에서는 **조회 번호 입력**으로 저장된 결과를 볼 수 있습니다.

웹 분석을 활성화하려면 기존 뷰어 스키마와 8자리 조회 설정을 적용한 뒤 [document-analysis.sql](supabase/document-analysis.sql)을 실행합니다. 웹 서버에 `OPENAI_API_KEY`를 설정하고 [.env.example](.env.example)의 모델명과 일일 한도를 확인합니다. 사용량은 UTC 날짜 기준이며 Vercel에서는 플랫폼이 제공하는 방문자 IP를 사용합니다. 로컬 서버에서는 하나의 IP 한도를 공유합니다. 실패한 모델 호출도 한도에 포함됩니다.

전용 서버 역할을 쓰면 아래 예시의 `axis_viewer_reader`를 실제 서버 역할로 바꿔 적용합니다. 기존 데이터셋 조회와 코드 조회 권한도 필요합니다.

```sql
grant insert(id,label,description,default_table,catalog,graph,access_code)
  on axis_viewer.datasets to axis_viewer_reader;
grant select,insert on axis_viewer.document_jobs to axis_viewer_reader;
grant select,insert,update,delete on axis_viewer.document_topics to axis_viewer_reader;
grant select,insert,update on axis_viewer.document_usage to axis_viewer_reader;
create policy web_job_server on axis_viewer.document_jobs to axis_viewer_reader using(true) with check(true);
create policy web_topic_server on axis_viewer.document_topics to axis_viewer_reader using(true) with check(true);
create policy web_usage_server on axis_viewer.document_usage to axis_viewer_reader using(true) with check(true);
-- datasets에 RLS를 켠 설치에서는 웹 분석 작업의 삽입도 허용합니다.
create policy web_analysis_insert on axis_viewer.datasets for insert to axis_viewer_reader
  with check(default_table='__web_topics__' and id ~ '^run-[a-f0-9]{32}$');
```

## MCP 분석 테스트 실행

1. `.env`의 `DATABASE_URL`에 테스트할 Supabase 접속 문자열을 넣습니다.
   `AXIS_VIEWER_URL`은 테스트할 Next.js 주소이고, `AXIS_VIEWER_PASSWORD`는
   웹과 MCP가 함께 쓰는 비밀번호입니다. 배포 환경에서는 비밀번호를 Vercel의
   서버 환경 변수에도 같은 값으로 설정합니다.
2. Supabase SQL Editor에서 [analysis-test.sql](supabase/analysis-test.sql)을 실행합니다.
   전용 뷰어 역할로 접속할 경우 해당 역할에 테스트 테이블의 조회와 삽입을 허용합니다.
   아래에서 `axis_viewer_reader`를 실제 로그인 역할로 바꿉니다.

   ```sql
   grant usage on schema axis_viewer to axis_viewer_reader;
   grant select, insert on axis_viewer.analysis_tests to axis_viewer_reader;
   create policy analysis_test_read on axis_viewer.analysis_tests
     for select to axis_viewer_reader using (true);
   create policy analysis_test_create on axis_viewer.analysis_tests
     for insert to axis_viewer_reader with check (true);
   ```

3. `npm run dev`로 웹을 열고 Axis Migration MCP를 다시 연결합니다.
   MCP에서 `run_analysis_test`를 호출하면 1~100 사이의 임의 숫자 6개와
   6자리 조회 코드, 조회 링크가 반환됩니다. 링크를 열거나 웹 화면의
   **분석 테스트**에서 코드를 입력하면 같은 숫자를 순서대로 확인할 수 있습니다.
