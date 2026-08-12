"""DovaMatch Streamlit web app.

Two views, reachable from the top nav and also directly via shareable URLs
(so opening a link on a phone jumps straight to that screen):
  - Faculty/alumni gallery -> click a card for a detail page with an artwork
    image slideshow, philosophy, academic orientation, and visual-language tags.
  - Essay matching dashboard -> paste an SOP essay, run src/matcher.py's
    embedding-based match against the 9 faculty (+ 2 Korean alumni as reference).

Run with:
    streamlit run src/app.py
"""

import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analyzer import DATA_DIR, load_faculty_data  # noqa: E402
from src.matcher import analyze_essay, get_backend, load_alumni_data  # noqa: E402
from src.portfolio import (  # noqa: E402
    PORTFOLIO_SIZE,
    analyze_essay_portfolio_complementarity,
    empty_portfolio,
    evaluate_portfolio,
)

st.set_page_config(page_title="DovaMatch", page_icon="🎨", layout="wide")

CSS = """
<style>
  .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1100px; }
  .dm-card {
    border: 1px solid rgba(128,128,128,0.25); border-radius: 12px; padding: 16px;
    height: 100%; display: flex; flex-direction: column; gap: 8px;
  }
  .dm-card img { border-radius: 8px; }
  .dm-card h4 { margin: 4px 0 0 0; }
  .dm-meta { font-size: 12px; opacity: 0.65; margin-bottom: 4px; }
  .dm-philosophy { font-style: italic; font-size: 13px; line-height: 1.5; opacity: 0.9; }
  .dm-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
  .dm-tag {
    background: rgba(59, 83, 216, 0.12); color: #3b53d8; border-radius: 999px;
    padding: 3px 10px; font-size: 12px; white-space: nowrap;
  }
  .dm-alumni-tag { background: rgba(216, 59, 129, 0.12); color: #d83b81; }
  .dm-score-bar-wrap { background: rgba(128,128,128,0.15); border-radius: 6px; height: 10px; overflow: hidden; }
  .dm-score-bar { background: #3b53d8; height: 100%; }
  .dm-note { font-size: 12px; opacity: 0.6; }
  .dm-stage-card { border-left: 4px solid rgba(128,128,128,0.35); padding: 4px 0 4px 12px; margin-bottom: 8px; }
  .dm-stage-ok { border-left-color: #2fa84f; }
  .dm-stage-warn { border-left-color: #d8a13b; }
  .dm-stage-empty { border-left-color: rgba(128,128,128,0.35); }
  .dm-grade-badge {
    display: inline-block; border-radius: 999px; padding: 4px 14px; font-weight: 700; font-size: 13px;
  }
  .dm-grade-good { background: rgba(47,168,79,0.15); color: #2fa84f; }
  .dm-grade-mid { background: rgba(216,161,59,0.15); color: #d8a13b; }
  .dm-grade-bad { background: rgba(216,59,59,0.15); color: #d83b3b; }
  .dm-coverage-wrap { display: flex; gap: 16px; margin: 8px 0 16px 0; }
  .dm-coverage-box { flex: 1; border: 1px solid rgba(128,128,128,0.25); border-radius: 10px; padding: 10px 14px; }
  .dm-coverage-num { font-size: 24px; font-weight: 700; }
  .dm-toefl-wrap { max-width: 420px; margin: 0 auto; text-align: center; }
  .dm-toefl-label { font-size: 14px; opacity: 0.6; margin-bottom: 4px; }
  .dm-toefl-gauge { position: relative; display: inline-block; line-height: 0; }
  .dm-toefl-total {
    position: absolute; left: 50%; top: 62%; transform: translate(-50%, -50%);
    font-size: 22px; font-weight: 700; white-space: nowrap;
  }
  .dm-toefl-sub { font-size: 14px; opacity: 0.6; margin-top: 4px; margin-bottom: 20px; }
  .dm-toefl-grid {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; text-align: center;
  }
  @media (max-width: 420px) {
    .dm-toefl-grid { grid-template-columns: 1fr; }
  }
  .dm-toefl-card-label { font-size: 14px; opacity: 0.75; margin-bottom: 8px; }
  .dm-toefl-card-value {
    background: rgba(59, 83, 216, 0.10); border-radius: 12px; padding: 18px 8px;
    font-size: 20px; font-weight: 700; color: #3b53d8;
  }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def get_faculty_data():
    return load_faculty_data()


@st.cache_data(show_spinner=False)
def get_alumni_data():
    return load_alumni_data()


@st.cache_data(show_spinner=False)
def get_admission_info():
    with open(DATA_DIR / "admission_info.json", "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_resource(show_spinner="임베딩 모델 준비 중...")
def get_cached_backend(backend_name, model):
    return get_backend(backend_name, model or None)


def render_tags(tags, alumni=False):
    cls = "dm-tag dm-alumni-tag" if alumni else "dm-tag"
    spans = "".join(f'<span class="{cls}">{t}</span>' for t in tags)
    st.markdown(f'<div class="dm-tags">{spans}</div>', unsafe_allow_html=True)


def find_person(name, faculty_data, alumni_data):
    for r in faculty_data:
        if r["name"] == name:
            return r, "faculty"
    for r in alumni_data:
        if r["name"] == name:
            return r, "alumni"
    return None, None


def go_to(**params):
    st.query_params.clear()
    for k, v in params.items():
        if v:
            st.query_params[k] = v
    st.rerun()


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------

def render_faculty_orientation_guide(fao):
    st.write(fao["intro"])
    for theme in fao.get("themes", []):
        with st.container(border=True):
            st.markdown(f"**{theme['title']}**")
            st.write(theme["description"])
            for ex in theme.get("examples", []):
                st.markdown(f"- {ex}")
    if fao.get("summary"):
        st.info(fao["summary"])
    if fao.get("application_tip"):
        st.markdown("**지원 전략 적용 팁**")
        st.write(fao["application_tip"])


def render_gallery(records, alumni=False):
    if not records:
        st.info("표시할 항목이 없습니다.")
        return
    cols = st.columns(3)
    for i, person in enumerate(records):
        with cols[i % 3]:
            with st.container(border=True):
                if person.get("image"):
                    st.image(person["image"], width="stretch")
                st.markdown(f"#### {person['name']}")
                if person.get("title"):
                    st.caption(person["title"])
                if person.get("philosophy"):
                    text = person["philosophy"]
                    excerpt = text if len(text) <= 110 else text[:110] + "..."
                    st.markdown(f'<div class="dm-philosophy">"{excerpt}"</div>', unsafe_allow_html=True)
                if person.get("visual_languages"):
                    render_tags(person["visual_languages"][:5], alumni=alumni)
                if st.button("자세히 보기", key=f"open-{person['name']}", width="stretch"):
                    go_to(tab="alumni" if alumni else "faculty", person=quote(person["name"]))


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------

def render_detail(person, kind):
    if st.button("← 갤러리로 돌아가기"):
        go_to(tab=kind)

    left, right = st.columns([1, 1], gap="large")

    with right:
        images = person.get("artwork_images") or ([person["image"]] if person.get("image") else [])
        if images:
            idx_key = f"slide-idx-{person['name']}"
            if idx_key not in st.session_state:
                st.session_state[idx_key] = 0
            idx = st.session_state[idx_key] % len(images)
            st.image(images[idx], width="stretch")
            if len(images) > 1:
                nav1, nav2, nav3 = st.columns([1, 2, 1])
                with nav1:
                    if st.button("← 이전", key=f"prev-{person['name']}"):
                        st.session_state[idx_key] = (idx - 1) % len(images)
                        st.rerun()
                with nav2:
                    st.markdown(
                        f'<div style="text-align:center;opacity:0.6;">{idx + 1} / {len(images)}</div>',
                        unsafe_allow_html=True,
                    )
                with nav3:
                    if st.button("다음 →", key=f"next-{person['name']}"):
                        st.session_state[idx_key] = (idx + 1) % len(images)
                        st.rerun()
        else:
            st.info("등록된 이미지가 없습니다.")

    with left:
        st.markdown(f"## {person['name']}")
        if person.get("title"):
            st.caption(person["title"])
        for field, label in (("office", None), ("teaching_since", None), ("email", None)):
            if person.get(field):
                st.markdown(f"📍 {person[field]}" if field == "office" else person[field])
        if person.get("homepage"):
            st.markdown(f"🔗 [{person['homepage']}]({person['homepage']})")
        if person.get("url"):
            st.markdown(f"[DoVA 프로필 페이지 원문]({person['url']})")

        lang = st.radio("소개 언어", ["한국어", "English"], horizontal=True, key=f"lang-{person['name']}")
        if lang == "한국어" and person.get("bio_ko"):
            st.write(person["bio_ko"])
        else:
            st.write(person.get("bio", ""))

        if person.get("current_activity_ko"):
            st.markdown("**현재 활동**")
            st.write(person["current_activity_ko"])

    st.divider()

    if person.get("philosophy"):
        st.markdown("### 예술 철학")
        st.markdown(f'<div class="dm-philosophy">"{person["philosophy"]}"</div>', unsafe_allow_html=True)

    if person.get("academic_orientation_ko"):
        st.markdown("### 학문적 성향")
        st.write(person["academic_orientation_ko"])

    if person.get("visual_languages"):
        st.markdown("### 표현 언어 (Visual Languages)")
        render_tags(person["visual_languages"], alumni=(kind == "alumni"))

    if person.get("key_exhibitions"):
        st.markdown("### 대표 전시 및 성과")
        for item in person["key_exhibitions"]:
            st.markdown(f"- {item}")

    if person.get("events"):
        st.markdown("### Related Events")
        for ev in person["events"]:
            title = f"[{ev['title']}]({ev['url']})" if ev.get("url") else ev.get("title", "")
            meta = " · ".join(x for x in [ev.get("date"), ev.get("host"), ev.get("location")] if x)
            st.markdown(f"- {title}  \n  <span class='dm-note'>{meta}</span>", unsafe_allow_html=True)

    st.markdown(
        '<p class="dm-note">※ 철학/표현 언어/전시 항목은 자동 추출 또는 리서치 기반 참고 자료입니다. '
        "실제 인용 전 원문 확인을 권장합니다.</p>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Essay matching dashboard
# ---------------------------------------------------------------------------

def render_match_card(match, alumni=False):
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**{match['name']}**")
        with c2:
            st.markdown(f"<div style='text-align:right;font-weight:700;'>{match['match_score']}점</div>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="dm-score-bar-wrap"><div class="dm-score-bar" '
            f'style="width:{min(match["match_score"], 100)}%;"></div></div>',
            unsafe_allow_html=True,
        )
        if match.get("recommended_keywords"):
            st.caption("추천 표현 언어")
            render_tags(match["recommended_keywords"], alumni=alumni)
        with st.expander("가이드 피드백 보기"):
            st.write(match["guide_feedback"])


GRADE_CSS = {
    "우수": "dm-grade-good", "양호": "dm-grade-good",
    "보완 필요": "dm-grade-mid", "미작성": "dm-grade-mid",
    "재구성 필요": "dm-grade-bad",
}

PORTFOLIO_COLUMNS = ["index", "title", "year", "size", "material", "medium", "description", "detail_shot", "cross_media"]

MEDIUM_OPTIONS = ["", "회화", "사진", "조각", "영상/퍼포먼스", "설치", "드로잉", "판화", "도자", "텍스타일", "디지털/뉴미디어", "기타"]

EXAMPLE_PORTFOLIO_ROWS = [
    {
        "index": 1, "title": "먼지, 그녀의 손이 닿은 자리", "year": "2024", "size": "130 x 97 cm",
        "material": "Oil and collected domestic dust on canvas", "medium": "회화",
        "description": "매일 반복된 돌봄노동의 흔적을 먼지라는 물질로 캔버스 표면에 축적시켜, 비가시적 노동을 회화의 물성 자체에 새겨넣는 실험이다.",
        "detail_shot": False, "cross_media": False,
    },
    {
        "index": 2, "title": "부엌의 시간, 12시간 루프", "year": "2024", "size": "4분 32초, 단채널 영상",
        "material": "Single-channel video, found kitchen audio", "medium": "영상/퍼포먼스",
        "description": "같은 부엌에서 반복되는 손동작을 12시간 동안 기록해, 1번 회화가 다룬 반복성을 시간 기반 매체로 확장한 작업이다.",
        "detail_shot": False, "cross_media": True,
    },
    {
        "index": 3, "title": "먼지 초상 #3", "year": "2025", "size": "40 x 50 cm",
        "material": "Gelatin silver print, dust residue on emulsion", "medium": "사진",
        "description": "1번 작업에 쓴 먼지를 인화지 유제 위에 직접 얹어 노출한 사진으로, 같은 물질을 다른 매체의 논리로 재실험했다.",
        "detail_shot": True, "cross_media": True,
    },
]


def render_portfolio_example():
    st.markdown("**작성 예시 (1~3번 · Hook)**")
    st.caption(
        "'가정 내 먼지로 돌봄노동의 비가시성을 탐구한다'는 가상의 핵심 개념을 예로 든 것입니다. "
        "같은 물질(먼지)을 회화 → 영상 → 사진으로 확장하며 교차 매체 실험을 표시한 방식을 참고해, 실제 작업 톤에 맞게 바꿔 쓰세요."
    )
    st.dataframe(
        pd.DataFrame(EXAMPLE_PORTFOLIO_ROWS),
        width="stretch",
        hide_index=True,
        column_order=PORTFOLIO_COLUMNS,
        column_config={
            "index": st.column_config.NumberColumn("#", width="small"),
            "title": st.column_config.TextColumn("제목", width="medium"),
            "year": st.column_config.TextColumn("연도", width="small"),
            "size": st.column_config.TextColumn("크기", width="small"),
            "material": st.column_config.TextColumn("재료 (맥락 포함 권장)", width="medium"),
            "medium": st.column_config.TextColumn("매체 유형", width=110),
            "description": st.column_config.TextColumn("설명 (미니 에세이, 1~2문장)", width="large"),
            "detail_shot": st.column_config.CheckboxColumn("디테일/매크로 샷", width=110),
            "cross_media": st.column_config.CheckboxColumn("교차 매체 실험", width=110),
        },
    )


def _portfolio_df_to_items(df):
    return [
        {
            "index": int(row["index"]),
            "title": str(row.get("title") or "").strip(),
            "year": str(row.get("year") or "").strip(),
            "size": str(row.get("size") or "").strip(),
            "material": str(row.get("material") or "").strip(),
            "medium": str(row.get("medium") or "").strip(),
            "description": str(row.get("description") or "").strip(),
            "detail_shot": bool(row.get("detail_shot")),
            "cross_media": bool(row.get("cross_media")),
        }
        for _, row in df.iterrows()
    ]


def render_portfolio_strategy_guide(ps):
    st.write(ps["intro"])

    if ps.get("sequencing_stages"):
        st.markdown("**시퀀싱 전략: 기승전결이 있는 시각 논문 만들기**")
        for stage in ps["sequencing_stages"]:
            with st.container(border=True):
                st.markdown(f"**{stage['range']}**")
                st.write(stage["description"])

    render_portfolio_example()

    if ps.get("slideroom_text_tips"):
        tips = ps["slideroom_text_tips"]
        st.markdown("**Slideroom 텍스트 입력란 활용하기**")
        st.write(tips["intro"])
        st.caption("흔한 실수:")
        st.code(tips["common_mistake"], language=None)
        st.caption("합격 전략 (재료 란 활용):")
        st.code(tips["better_practice"], language=None)
        st.caption(f"Description(설명)란 활용: {tips['description_field_tip']}")

    if ps.get("pitfalls"):
        st.markdown("**절대 넣지 말아야 할 것**")
        for item in ps["pitfalls"]:
            st.markdown(f"- {item}")

    if ps.get("summary"):
        st.info(ps["summary"])


def render_essay_strategy_guide(es):
    st.write(es["intro"])

    if es.get("structure_stages"):
        st.markdown("**구조 전략: 포트폴리오의 기승전결과 맞물리는 4단계**")
        for stage in es["structure_stages"]:
            with st.container(border=True):
                st.markdown(f"**{stage['stage']}**")
                st.write(stage["description"])

    if es.get("writing_tips"):
        st.markdown("**작성 팁**")
        for tip in es["writing_tips"]:
            st.markdown(f"- {tip}")

    if es.get("pitfalls"):
        st.markdown("**절대 하지 말아야 할 것**")
        for item in es["pitfalls"]:
            st.markdown(f"- {item}")

    if es.get("summary"):
        st.info(es["summary"])


def render_portfolio_section(backend_name, disabled, portfolio_strategy=None):
    st.markdown("### 🖼️ 포트폴리오 매칭 (20점)")
    st.caption(
        "20점을 무작위 나열이 아니라 '기승전결'이 있는 시각 논문(Visual Thesis)으로 시퀀싱했는지, "
        "그리고 각 슬롯의 제목/재료/설명이 단순 정보 기입이 아니라 미니 에세이 역할을 하는지 점검합니다."
    )

    if portfolio_strategy:
        with st.expander("📖 작성 가이드 보기 — 포트폴리오(20점) 구성 전략"):
            render_portfolio_strategy_guide(portfolio_strategy)

    core_concept = st.text_input(
        "핵심 개념 / 철학적 줄기 (선택 — 입력하면 20점 전체의 개념적 일관성(Conceptual Cohesion)을 체크합니다)",
        placeholder="예: 가정 내 먼지와 시간의 축적을 통해 돌봄 노동의 비가시성을 탐구한다",
        key="portfolio_core_concept",
    )

    if "portfolio_df" not in st.session_state:
        st.session_state["portfolio_df"] = pd.DataFrame(empty_portfolio())

    edited_df = st.data_editor(
        st.session_state["portfolio_df"],
        key="portfolio_editor",
        width="stretch",
        num_rows="fixed",
        hide_index=True,
        column_order=PORTFOLIO_COLUMNS,
        column_config={
            "index": st.column_config.NumberColumn("#", disabled=True, width="small"),
            "title": st.column_config.TextColumn("제목", width="medium"),
            "year": st.column_config.TextColumn("연도", width="small"),
            "size": st.column_config.TextColumn("크기", width="small"),
            "material": st.column_config.TextColumn("재료 (맥락 포함 권장)", width="medium"),
            "medium": st.column_config.SelectboxColumn("매체 유형", options=MEDIUM_OPTIONS, width=110),
            "description": st.column_config.TextColumn("설명 (미니 에세이, 1~2문장)", width="large"),
            "detail_shot": st.column_config.CheckboxColumn("디테일/매크로 샷", width=110),
            "cross_media": st.column_config.CheckboxColumn("교차 매체 실험", width=110),
        },
    )
    st.session_state["portfolio_df"] = edited_df
    st.caption(
        "행 순서 = 배치 순서입니다. 1\\~3번 Hook · 4\\~15번 Body · 16\\~19번 Climax(디테일 샷 체크) · 20번 Open Ending."
    )

    if st.button("포트폴리오 평가하기", disabled=disabled, width="stretch"):
        items = _portfolio_df_to_items(edited_df)
        backend = None
        try:
            backend = get_cached_backend(backend_name, None)
        except Exception as e:
            st.warning(f"임베딩 백엔드 초기화 실패로 개념적 일관성 체크는 건너뜁니다: {e}")
        with st.spinner("포트폴리오 시퀀싱 평가 중..."):
            portfolio_report = evaluate_portfolio(items, core_concept=core_concept, backend=backend)
        st.session_state["portfolio_items"] = items
        st.session_state["portfolio_report"] = portfolio_report

    portfolio_report = st.session_state.get("portfolio_report")
    if portfolio_report:
        summary = portfolio_report["summary"]
        badge_cls = GRADE_CSS.get(summary["grade"], "dm-grade-mid")
        st.markdown(
            f'<span class="dm-grade-badge {badge_cls}">{summary["grade"]}</span> '
            f'&nbsp;{summary["message"]} '
            f'<span class="dm-note">(채워진 슬롯 {portfolio_report["filled_count"]}/{PORTFOLIO_SIZE})</span>',
            unsafe_allow_html=True,
        )

        st.markdown("#### 시퀀싱 평가 (기승전결)")
        for stage in portfolio_report["stage_feedback"]:
            cls = f"dm-stage-card dm-stage-{stage['status']}"
            msgs = "".join(f"<div>• {m}</div>" for m in stage["messages"]) or "<div>이상 없음.</div>"
            st.markdown(
                f'<div class="{cls}"><strong>{stage["stage"]}</strong>{msgs}</div>',
                unsafe_allow_html=True,
            )

        if portfolio_report["item_feedback"]:
            st.markdown("#### 슬롯별 미니 에세이 피드백")
            for f in portfolio_report["item_feedback"]:
                with st.expander(f"{f['index']}번 · {f['title']}"):
                    for issue in f["issues"]:
                        st.markdown(f"- {issue}")

        cohesion = portfolio_report.get("cohesion", {})
        if cohesion.get("available"):
            st.markdown("#### 개념적 일관성 (Conceptual Cohesion)")
            if cohesion["outliers"]:
                st.warning("핵심 개념과의 연관성이 상대적으로 약해, '뷔페식 구성'으로 보일 수 있는 작품:")
                for o in cohesion["outliers"]:
                    st.markdown(f"- {o['index']}번 · {o['title']} (유사도 {o['score']}%)")
            else:
                st.success("20점 전체가 핵심 개념과 고르게 연결되어 있습니다.")


def render_match_dashboard(faculty_data, alumni_data, admission_info=None):
    st.markdown("## ✍️ 포트폴리오 & 에세이 매칭")
    st.caption(
        "포트폴리오 20점을 먼저 시퀀싱/미니 에세이 관점에서 점검한 뒤, SOP 에세이를 교수 9인 + 한국인 동문 2인의 "
        "철학/표현 언어와 비교하고, 포트폴리오와 에세이가 서로의 빈틈을 얼마나 잘 채워주는지 확인합니다."
    )

    with st.expander("⚙️ 임베딩 설정 (기본값 그대로 사용해도 됩니다)"):
        backend_choice = st.selectbox(
            "임베딩 백엔드",
            ["auto (로컬, 권장)", "sentence-transformers", "tfidf", "openai (텍스트 전송, 명시적 동의 필요)"],
            index=0,
        )
        top_k = st.slider("교수 매칭 상위 N명", min_value=1, max_value=9, value=3)
        openai_consent = False
        if backend_choice.startswith("openai"):
            st.warning(
                "openai 백엔드는 포트폴리오 텍스트/에세이 전문을 OpenAI 임베딩 API로 전송합니다. "
                "`OPENAI_API_KEY` 환경 변수가 설정되어 있어야 합니다."
            )
            openai_consent = st.checkbox("텍스트를 OpenAI API로 전송하는 데 동의합니다.")

    backend_name = backend_choice.split(" ")[0]
    disabled = backend_choice.startswith("openai") and not openai_consent

    portfolio_strategy = (admission_info or {}).get("portfolio_strategy")
    render_portfolio_section(backend_name, disabled, portfolio_strategy)

    st.divider()
    st.markdown("### ✍️ 에세이 매칭")

    essay_strategy = (admission_info or {}).get("essay_strategy")
    if essay_strategy:
        with st.expander("📖 작성 가이드 보기 — SOP/아티스트 스테이트먼트 작성 전략"):
            render_essay_strategy_guide(essay_strategy)

    essay_text = st.text_area(
        "SOP 에세이 텍스트",
        height=280,
        placeholder="여기에 Artist's Statement / SOP 에세이 전문을 붙여넣으세요...",
    )

    if st.button("분석하기", type="primary", disabled=disabled, width="stretch"):
        if not essay_text.strip():
            st.error("에세이 텍스트를 입력해주세요.")
            return
        try:
            backend = get_cached_backend(backend_name, None)
        except Exception as e:
            st.error(f"백엔드 초기화 실패: {e}")
            return
        with st.spinner("분석 중..."):
            report = analyze_essay(
                essay_text, faculty_data=faculty_data, alumni_data=alumni_data,
                backend=backend, top_k=top_k,
            )
            portfolio_items = st.session_state.get("portfolio_items")
            if portfolio_items:
                report["portfolio_complementarity"] = analyze_essay_portfolio_complementarity(
                    essay_text, portfolio_items, backend,
                )
        st.session_state["last_report"] = report

    report = st.session_state.get("last_report")
    if report:
        st.info(f"임베딩 백엔드: {report['backend']}")

        complementarity = report.get("portfolio_complementarity")
        if complementarity:
            st.markdown("### 🔗 포트폴리오 ↔ 에세이 상호보완성 분석")
            st.caption(
                "글에서 주장한 탐구가 시각물로 증명되는지, 시각물이 미처 설명하지 못한 맥락을 글이 채워주는지를 봅니다."
            )
            st.markdown(
                '<div class="dm-coverage-wrap">'
                f'<div class="dm-coverage-box"><div class="dm-coverage-num">{complementarity["portfolio_coverage_pct"]}%</div>'
                '<div class="dm-note">포트폴리오 커버리지 — 에세이가 뒷받침하는 작품 비율</div></div>'
                f'<div class="dm-coverage-box"><div class="dm-coverage-num">{complementarity["essay_coverage_pct"]}%</div>'
                '<div class="dm-note">에세이 커버리지 — 포트폴리오가 증명하는 주장 비율</div></div>'
                "</div>",
                unsafe_allow_html=True,
            )

            if complementarity["visual_gaps"]:
                st.markdown("**🖼️ → 📝 글로 채워야 할 시각적 공백**")
                for gap in complementarity["visual_gaps"]:
                    it = gap["item"]
                    excerpt = gap["paragraph"] if len(gap["paragraph"]) <= 140 else gap["paragraph"][:140] + "..."
                    st.markdown(
                        f"- **{it['index']}번 · {it['title'] or '(제목 없음)'}** — 이 작품을 뒷받침하는 맥락이 "
                        f"에세이에 뚜렷하지 않습니다 (가장 가까운 문단, 유사도 {round(gap['score']*100,1)}%: "
                        f"\"{excerpt}\"). 이 작업을 에세이에서 직접 언급하거나 설명을 보강하세요."
                    )

            if complementarity["text_gaps"]:
                st.markdown("**📝 → 🖼️ 시각물로 증명해야 할 주장**")
                for gap in complementarity["text_gaps"]:
                    excerpt = gap["paragraph"] if len(gap["paragraph"]) <= 140 else gap["paragraph"][:140] + "..."
                    it = gap["item"]
                    st.markdown(
                        f"- \"{excerpt}\" — 이 주장을 뒷받침하는 포트폴리오 작품이 뚜렷하지 않습니다 "
                        f"(가장 가까운 작품 '{it['title'] or it['index']}', 유사도 {round(gap['score']*100,1)}%). "
                        "이 주장을 증명하는 이미지를 포함하거나, 관련 작품의 설명을 보강하세요."
                    )

            if not complementarity["visual_gaps"] and not complementarity["text_gaps"]:
                st.success("포트폴리오와 에세이가 서로를 고르게 뒷받침하고 있습니다.")

            if complementarity["strong_links"]:
                with st.expander("잘 연결된 지점 (상호보완 구조가 작동하는 예시)"):
                    for link in complementarity["strong_links"]:
                        it = link["item"]
                        excerpt = link["paragraph"] if len(link["paragraph"]) <= 140 else link["paragraph"][:140] + "..."
                        st.markdown(f"- **{it['index']}번 · {it['title'] or '(제목 없음)'}** ↔ \"{excerpt}\" (유사도 {round(link['score']*100,1)}%)")
        elif st.session_state.get("portfolio_items"):
            st.caption("포트폴리오를 평가하면 에세이와의 상호보완성 분석도 함께 표시됩니다 (텍스트가 부족하면 생략될 수 있습니다).")

        st.markdown(f"### 🎯 교수진 매칭 Top {len(report['top_matches'])}")
        for match in report["top_matches"]:
            render_match_card(match)

        if report.get("alumni_references"):
            st.markdown("### 🇰🇷 참고: 한국인 DoVA 동문 매칭")
            st.caption("경쟁 순위가 아닌 참고 사례입니다.")
            for match in report["alumni_references"]:
                render_match_card(match, alumni=True)


# ---------------------------------------------------------------------------
# Admission info
# ---------------------------------------------------------------------------

def _parse_fraction(text, default_max=6.0):
    m = re.match(r"\s*([\d.]+)\s*/\s*([\d.]+)", text or "")
    if not m:
        return None, default_max
    return float(m.group(1)), float(m.group(2))


def render_toefl_score_report(scores):
    total_val, total_max = _parse_fraction(scores["toefl_new_total"])
    old_val, old_max = _parse_fraction(scores["toefl_old_total"], default_max=120.0)
    pct = max(0.0, min(1.0, total_val / total_max)) if total_val is not None else 0.0

    radius = 80
    half_circ = math.pi * radius
    filled = pct * half_circ

    gauge_svg = (
        '<svg viewBox="0 0 200 112" width="220" height="124">'
        '<path d="M20 100 A 80 80 0 0 1 180 100" fill="none" '
        'stroke="rgba(128,128,128,0.18)" stroke-width="18" stroke-linecap="round"/>'
        '<path d="M20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#3b53d8" '
        f'stroke-width="18" stroke-linecap="round" stroke-dasharray="{filled:.1f} {half_circ:.1f}"/>'
        "</svg>"
    )

    total_label = f"{total_val:g} of {total_max:g}" if total_val is not None else scores["toefl_new_total"]
    old_label = f"{old_val:g} of {old_max:g}" if old_val is not None else scores["toefl_old_total"]

    sub_scores = [
        ("📖 Reading", scores["reading"]),
        ("🎧 Listening", scores["listening"]),
        ("✏️ Writing", scores["writing"]),
        ("🎤 Speaking", scores["speaking"]),
    ]
    cards = "".join(
        f'<div><div class="dm-toefl-card-label">{label}</div>'
        f'<div class="dm-toefl-card-value">{value} of {total_max:g}</div></div>'
        for label, value in sub_scores
    )

    st.markdown(
        f"""
        <div class="dm-toefl-wrap">
          <div class="dm-toefl-label">Overall Score</div>
          <div class="dm-toefl-gauge">
            {gauge_svg}
            <div class="dm-toefl-total">{total_label}</div>
          </div>
          <div class="dm-toefl-sub">{old_label}</div>
          <div class="dm-toefl-grid">{cards}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_admission_info(info):
    st.markdown("## 📋 DoVA 지원 요건 & 내 점수")

    st.markdown("### 내 어학 점수 (TOEFL)")
    scores = info["my_scores"]
    render_toefl_score_report(scores)

    st.markdown("### 제출 서류 요건")
    for doc in info["required_documents"]:
        with st.container(border=True):
            st.markdown(f"**{doc['item']}**")
            st.write(doc["requirement"])
            st.caption(f"💡 {doc['tip']}")

    st.markdown("### 대학원 조교(TA) 영어 자격 요건")
    ta = info["ta_eligibility"]
    st.write(ta["description"])
    st.table(
        [
            {"시험 구분": row["test"], "무심사 패스 기준": row["pass"], "⚠️ 자체 추가 시험(AEPA) 필요 기준": row["review"]}
            for row in ta["table"]
        ]
    )
    st.caption(
        f"내 TOEFL Speaking 점수: {scores['speaking']} → 26점 이상(뉴토플 5.5) 기준을 충족하여 "
        "별도 추가 시험 없이 조교 임용이 가능합니다."
    )

    st.markdown("### 영어 성적 송부처 (Where to Send)")
    ss = info["score_sending"]
    st.markdown(f"- TOEFL 기관 코드: {ss['toefl_code']}")
    st.markdown(f"- IELTS: {ss['ielts_note']}")
    st.markdown(f"- Account Name: {ss['ielts_account_name']}")
    st.markdown(f"- Address: {ss['ielts_address']}")

    st.markdown("### 문의처 및 연락처 안내")
    for c in info["contacts"]:
        st.markdown(f"- {c['purpose']}: [{c['email']}](mailto:{c['email']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    faculty_data = get_faculty_data()
    alumni_data = get_alumni_data()
    admission_info = get_admission_info()

    params = st.query_params
    tab = params.get("tab", "faculty")
    person_name = unquote(params.get("person", "")) if params.get("person") else None

    st.markdown("# 🎨 DovaMatch")
    st.caption("시카고대학교 DoVA 지원자를 위한 교수진 아카이브 & 포트폴리오/에세이 매칭")

    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        if st.button("👩‍🏫 교수진 갤러리", width="stretch", type="primary" if tab == "faculty" and not person_name else "secondary"):
            go_to(tab="faculty")
    with nav2:
        if st.button("🇰🇷 한국인 동문", width="stretch", type="primary" if tab == "alumni" and not person_name else "secondary"):
            go_to(tab="alumni")
    with nav3:
        if st.button("🖼️✍️ 포트폴리오/에세이 매칭", width="stretch", type="primary" if tab == "match" else "secondary"):
            go_to(tab="match")
    with nav4:
        if st.button("📋 지원 요건 & 내 점수", width="stretch", type="primary" if tab == "info" else "secondary"):
            go_to(tab="info")

    st.divider()

    if person_name:
        person, kind = find_person(person_name, faculty_data, alumni_data)
        if person is None:
            st.error(f"'{person_name}'을(를) 찾을 수 없습니다.")
            go_to(tab=tab)
        else:
            render_detail(person, kind)
        return

    if tab == "alumni":
        st.markdown("## 🇰🇷 한국인 DoVA / DoVA-연계 동문")
        render_gallery(alumni_data, alumni=True)
    elif tab == "match":
        render_match_dashboard(faculty_data, alumni_data, admission_info)
    elif tab == "info":
        render_admission_info(admission_info)
    else:
        st.markdown("## 👩‍🏫 교수진 아카이브")
        fao = (admission_info or {}).get("faculty_academic_orientation")
        if fao:
            with st.expander("📖 DoVA 교수진의 학문적 성향"):
                render_faculty_orientation_guide(fao)
        render_gallery(faculty_data, alumni=False)


if __name__ == "__main__":
    main()
