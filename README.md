# DovaMatch

시카고대학교 미술대학원(**DoVA**, Department of Visual Arts) 지원을 위한, 지원자 맞춤형 예술 연구 아카이브입니다.

## 프로젝트의 본질

DovaMatch는 단순한 텍스트 유사도 매칭 도구가 아닙니다. DoVA 교수진 9인이 가진 **시각적·철학적 언어와 작품 세계를 심층 분석**하고, 이를 지원자 본인의 에세이(Artist's Statement)에 녹여내기 위한 리서치 아카이브를 목표로 합니다.

DoVA는 순수 예술(Fine Art) 대학원이기 때문에, 일반 학과처럼 논문 인용 지수나 초록(abstract)만으로 교수의 연구 방향을 파악할 수 없습니다. 대신:

- 전시 이력, 소속 갤러리, 평론 게재 매체 등 **텍스트 기반 이력**
- 작품 이미지, 시각적 표현 언어(재료, 형식, 매체)
- 작업 노트에 드러나는 **예술적 철학과 문제의식**

이 세 가지를 함께 다뤄야 각 교수의 실제 작업 세계에 맞닿은 지원 전략을 세울 수 있습니다.

## 현재 구현 상태

| 영역 | 내용 |
| --- | --- |
| 교수 프로필 수집 | 이름, 직함, 소속, 이메일, 오피스, 개인 홈페이지, bio(작업 설명), 대표 이미지, 관련 전시/행사(Related Events) |
| 표현 언어 분석 | `src/analyzer.py`가 bio 텍스트에서 `artwork_images`, `philosophy`(예술 철학 요약), `visual_languages`(매체/기법/담론 키워드), `key_exhibitions`(대표 전시)를 자동 추출하여 `faculty_data.json`에 병합 |
| 학문적 성향 분석 | 교수 9인 각각에 `academic_orientation_ko`(리서치 기반 학문적 성향 요약)를 수록하고, `admission_info.json`의 `faculty_academic_orientation`에 DoVA 전체를 관통하는 4가지 학문적 성향 테마(사회·정치·경제 구조 해체 / 역사적 텍스트·퍼포먼스 재구성 / 매체·지각에 대한 의문 / 학제 간 융합)와 지원 전략 팁을 정리 |
| 지원 요건 정보 | 제출 서류(포트폴리오/작가노트/추천서/GRE), 영어 자격 조건(Pass/Fail), TA(조교) 영어 자격 기준, 성적 송부처, 문의처, 지원자 본인 TOEFL 점수 |
| 포트폴리오(20점) 구성 전략 | `admission_info.json`의 `portfolio_strategy`에 시퀀싱 전략(Hook/Body/Climax/Open Ending 4단계), Slideroom 텍스트란 활용법, 절대 넣지 말아야 할 것(Pitfalls), 종합 요약을 수록하고 뷰어의 지원 요건 페이지에서 표시 |
| 한국인 동문 아카이브 | `data/alumni_data.json`에 한국인 DoVA/DoVA-연계 동문(베티 영 킴, 찰리 강)의 이력을 별도로 수록하고, 교수진과 동일한 파이프라인으로 `philosophy`/`visual_languages`를 추출해 뷰어와 매칭 리포트에서 참고 자료로 활용 |
| 에세이 매칭 | `src/matcher.py`가 지원자 에세이(SOP)와 교수별 `philosophy`/`visual_languages`를 임베딩 코사인 유사도로 비교, 학문적/예술적 핏 Top-N과 추천 키워드·가이드 피드백 리포트 생성. 동문 2인도 같은 방식으로 채점해 "참고 사례"로 별도 표시 |
| 뷰어 (정적) | 좌측 목록이 교수진/한국인 동문 두 그룹으로 구분 표시. 인물 클릭 시 좌: 설명(bio, 예술 철학, 표현 언어 태그, 대표 전시), 우: 대표 이미지 50/50 레이아웃. 지원 요건 정보는 별도 페이지로 분리 |
| 포트폴리오(20점) 매칭 | `src/portfolio.py`가 포트폴리오 20슬롯의 시퀀싱(Hook 1~3 / Body 4~15 / Climax 16~19 / Open Ending 20), 슬롯별 제목·재료·설명(미니 에세이) 완성도, 기술 과시용 습작 여부, 핵심 개념과의 개념적 일관성을 점검하고, SOP 에세이와 대조해 시각물↔글의 상호보완 공백(포트폴리오 커버리지/에세이 커버리지)을 리포트로 제공 |
| 웹 앱 (Streamlit) | `src/app.py`가 PC/맥/모바일 브라우저에서 반응형으로 동작. 교수 9인 + 동문 2인 프로필 카드 그리드 갤러리 → 클릭 시 작품 이미지 슬라이드 + 철학/학문적 성향/표현 언어 상세 페이지, 그리고 포트폴리오 20슬롯 입력 → 에세이 텍스트를 입력해 매칭 + 상호보완성 리포트를 받는 대시보드. 모든 화면이 URL 쿼리 파라미터로 딥링크되어 모바일에서 특정 교수/탭 링크를 바로 열 수 있음 |

교수별 텍스트 이력에 더해 **표현 언어(키워드)와 예술 철학 요약이 구조화**되었고, 이를 지원자 에세이와 비교하는 매칭 단계까지 구현되었습니다. 한국인 DoVA 동문 2인의 철학/표현 언어도 같은 구조로 정리되어 뷰어와 매칭 리포트에서 함께 참고할 수 있습니다. `philosophy`/`key_exhibitions`/매칭 리포트는 모두 규칙 기반 자동 추출 또는 임베딩 유사도 결과이므로, 지원 에세이에 실제로 쓰기 전에 직접 검토·다듬는 것을 권장합니다. 작품 이미지 자체의 시각적 특징(색채, 구성 등) 분석은 다음 단계 작업입니다 (아래 로드맵 참고).

## 프로젝트 구조

```
DovaMatch/
├── requirements.txt
├── src/
│   ├── scraper.py         # dova.uchicago.edu 프로필 페이지 스크래핑
│   ├── analyzer.py        # bio 텍스트 -> artwork_images/philosophy/visual_languages/key_exhibitions 추출
│   ├── matcher.py         # 지원자 SOP 에세이 <-> 교수별 철학/표현 언어 임베딩 매칭 리포트 생성
│   ├── generate_site.py   # data/*.json -> site/index.html 정적 뷰어 생성
│   └── app.py             # Streamlit 웹 앱 (갤러리 + 상세 페이지 + 에세이 매칭 대시보드, 반응형/딥링크)
├── data/
│   ├── faculty_list.txt      # 수집 대상 "이름,프로필URL" 목록
│   ├── faculty_data.json     # 스크래핑 결과 (구조화된 교수 프로필)
│   ├── alumni_data.json      # 한국인 DoVA/DoVA-연계 동문 프로필 (수동 작성, analyzer.py로 분석 필드 병합)
│   └── admission_info.json   # DoVA 지원 요건 & 지원자 본인 점수
└── site/
    └── index.html          # 생성된 정적 뷰어 (브라우저로 바로 열람 가능)
```

## 설치 및 실행

```bash
pip install -r requirements.txt

# 1. 교수 프로필 데이터 수집 (data/faculty_list.txt 기반)
python -m src.scraper

# 2. bio 텍스트에서 표현 언어/철학/대표 전시 추출 -> faculty_data.json에 병합
python -m src.analyzer

# 3. (선택) 내 SOP 에세이와 교수진 철학/표현 언어 매칭 리포트
python -m src.matcher my_essay.txt

# 4. 정적 뷰어 생성
python -m src.generate_site

# 5. site/index.html을 브라우저로 열기

# 6. (선택) 반응형 웹 앱으로 실행 — 갤러리 + 상세 페이지 + 포트폴리오/에세이 매칭 대시보드
streamlit run src/app.py

# 실행하면 터미널에 아래처럼 접속 주소가 뜹니다. 브라우저에서 열면 됩니다:
#   Local URL: http://localhost:8501
# 종료하려면 터미널에서 Ctrl+C
```

`src/app.py`는 PC/맥/스마트폰 브라우저에서 모두 반응형으로 동작하는 Streamlit 앱입니다. 상단 네비게이션(교수진 갤러리 / 한국인 동문 / 에세이 매칭)으로 이동하거나, URL 쿼리 파라미터로 특정 화면에 바로 접속할 수 있습니다 — 예: `?tab=faculty&person=Julia%20Phillips`로 특정 교수 상세 페이지를, `?tab=match`로 에세이 매칭 대시보드를 바로 엽니다. 모바일에서 이런 링크를 탭하면(예: 카카오톡/메시지로 공유) 별도 조작 없이 해당 화면이 바로 뜹니다. 다만 이 딥링크가 실제로 동작하려면 앱이 어딘가(로컬 네트워크든 Streamlit Community Cloud 등 배포 환경이든)에 떠 있어야 하며, `localhost` 주소는 앱을 실행 중인 PC에서만 열립니다.

`src/analyzer.py`는 `spacy`와 `en_core_web_sm` 모델이 설치되어 있으면 명사구 파싱으로 키워드를 보강하고, 없으면 큐레이션된 예술 용어 사전 + 정규식 기반으로 동작합니다 (설치 방법은 `requirements.txt` 참고). scraper를 다시 돌리면 `faculty_data.json`이 원본 스크랩 필드로 덮어써지므로, scraper 이후에는 analyzer를 다시 실행해야 확장 필드가 유지됩니다.

`src/matcher.py`는 기본적으로 `sentence-transformers`(다국어 모델, 로컬 실행)를 시도하고 설치되어 있지 않으면 외부 의존성 없는 TF-IDF 방식으로 대체합니다. `--backend openai`는 에세이 전문을 OpenAI 임베딩 API로 전송하므로 `pip install openai`와 `OPENAI_API_KEY` 설정 후 명시적으로 선택했을 때만 사용됩니다(자동 선택되지 않음). `--json` 옵션으로 구조화된 리포트를 받을 수 있습니다.

## 로드맵

- 작품 이미지의 시각적 특징(형식, 매체, 색채, 구성) 분석 (현재는 대표 이미지 1장만 `artwork_images`에 시드됨)
- `philosophy`/`visual_languages`를 지원자 본인의 관심사·에세이와 매칭하는 유사도 스코어링
- 단순 텍스트 유사도를 넘어선, 시각 자료를 포함한 다차원 매칭 스코어
