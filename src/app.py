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
import os
import sys
from pathlib import Path
from urllib.parse import quote, unquote

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analyzer import DATA_DIR, load_faculty_data  # noqa: E402
from src.image_feedback import analyze_portfolio_image  # noqa: E402
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


EXAMPLE_ESSAY_PARAGRAPHS = [
    {
        "stage": "도입 — 질문의 기원",
        "text": (
            "매주 일요일, 어머니는 같은 순서로 부엌을 닦았다. 나는 그 손이 지나간 자리마다 뽀얗게 다시 내려앉는 먼지를 "
            "지켜보며 자랐다 — 아무리 반복해도 완결되지 않는, 그러나 누구도 그 반복을 '일'이라 부르지 않는 노동. "
            "1번 회화 〈먼지, 그녀의 손이 닿은 자리〉는 그 먼지를 실제로 캔버스에 수집해 얹는 것에서 시작했다. "
            "돌봄노동을 은유가 아니라 물질 그 자체로 다루고 싶었다."
        ),
    },
    {
        "stage": "전개 — 매체적 실험의 논리",
        "text": (
            "회화가 먼지의 '축적'을 보여줄 수는 있어도 그 축적이 만들어지는 '시간'은 담지 못했다. 그래서 2번 작업 "
            "〈부엌의 시간, 12시간 루프〉로 넘어가 같은 손동작의 반복을 시간 기반 매체에 옮겼고, 다시 그 먼지를 "
            "인화지 유제 위에 직접 얹어 노출한 3번 〈먼지 초상 #3〉로 사진의 화학적 과정 자체에 결합시켰다. "
            "매체를 바꾼 것은 새로움을 위해서가 아니라, 같은 물질(수집된 가정용 먼지)이 회화·영상·사진 각각에서 "
            "요구하는 질문이 달랐기 때문이다."
        ),
    },
    {
        "stage": "심화 — 이론적 좌표",
        "text": (
            "이 반복은 페미니즘 노동사에서 말하는 '비가시적 재생산 노동'과 정확히 겹쳤다. 다만 나는 그 개념을 "
            "인용하는 데서 멈추지 않고, 먼지라는 물질이 그 비가시성을 어떻게 감각적으로 배반하는지 — 지워도 "
            "다시 쌓이고, 지운 흔적마저 흔적으로 남는지 — 를 매체별 표면(캔버스의 물성, 필름의 화학, 렌즈의 시간)에서 "
            "각기 다른 방식으로 실험하고 싶었다. 이 집요함은 20점 전체에서 클로즈업 디테일 샷으로 반복된다."
        ),
    },
    {
        "stage": "마무리 — 다음 단계",
        "text": (
            "시카고에서의 2년 동안, 이 질문을 조각과 설치로 확장하고 싶다. 20번에 배치한 미완성 스케치는 수집한 "
            "먼지를 압축해 실제 오브제로 만드는 작업의 첫 시도다 — 아직 결론이 아니라, 다음 매체가 던질 질문을 "
            "기다리는 자리로 남겨두었다."
        ),
    },
]


def render_essay_example():
    st.markdown("**작성 예시 (포트폴리오 예시와 동일한 핵심 개념 사용)**")
    st.caption(
        "위 포트폴리오 작성 예시(1~3번)와 같은 '가정 내 먼지로 돌봄노동의 비가시성을 탐구한다'는 개념으로 쓴 "
        "가상의 에세이입니다. 포트폴리오 작품을 구체적으로 언급하고, 재료 란에 쓴 어휘('수집된 가정용 먼지')를 "
        "그대로 반복해 두 텍스트가 같은 세계에서 나왔음을 보여주는 방식에 주목하세요."
    )
    for para in EXAMPLE_ESSAY_PARAGRAPHS:
        with st.container(border=True):
            st.markdown(f"**{para['stage']}**")
            st.write(para["text"])


def render_essay_strategy_guide(es):
    st.write(es["intro"])

    if es.get("structure_stages"):
        st.markdown("**구조 전략: 포트폴리오의 기승전결과 맞물리는 4단계**")
        for stage in es["structure_stages"]:
            with st.container(border=True):
                st.markdown(f"**{stage['stage']}**")
                st.write(stage["description"])

    render_essay_example()

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


def render_image_feedback_section(faculty_data):
    st.markdown("### 🖼️ 이미지 교수 피드백")
    st.caption(
        "작품 이미지를 업로드하면 Claude(Anthropic)가 이미지를 직접 분석해, DoVA 교수 9인이 "
        "각자의 예술 철학/관심사에 비추어 이 이미지를 볼 때 할 법한 평가와 질문을 상상해서 보여줍니다. "
        "(포트폴리오 평가/에세이 매칭은 텍스트만 비교하지만, 이 항목만은 이미지를 실제로 읽습니다.)"
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY")
        except StreamlitSecretNotFoundError:
            api_key = None
    has_key = bool(api_key)
    if not has_key:
        st.warning(
            "이 기능을 사용하려면 `ANTHROPIC_API_KEY` 환경 변수가 설정되어 있어야 합니다."
        )

    uploaded = st.file_uploader(
        "작품 이미지 업로드 (JPG/PNG/WEBP)", type=["jpg", "jpeg", "png", "webp"], key="img_feedback_upload"
    )
    consent = st.checkbox(
        "업로드한 이미지를 Anthropic Claude API로 전송해 분석하는 데 동의합니다.",
        key="img_feedback_consent",
    )

    if uploaded is not None:
        st.image(uploaded, width=280)

    if st.button(
        "🔍 이미지 분석하기", disabled=not (has_key and consent and uploaded is not None), width="stretch"
    ):
        media_type = uploaded.type or "image/jpeg"
        image_bytes = uploaded.getvalue()
        with st.spinner("Claude가 이미지를 분석하고 9인의 교수 반응을 생성하는 중..."):
            try:
                report = analyze_portfolio_image(image_bytes, media_type, faculty_data, api_key=api_key)
            except Exception as e:
                st.error(f"분석 실패: {e}")
                report = None
        st.session_state["image_feedback_report"] = report

    report = st.session_state.get("image_feedback_report")
    if report:
        st.markdown("#### 이미지에 대한 중립적 관찰")
        st.write(report["overall_impression"])

        st.markdown("#### 교수별 예상 반응 & 질문")
        for fb in report["faculty_feedback"]:
            with st.container(border=True):
                st.markdown(f"**{fb['name']}**")
                st.write(fb["reaction"])
                if fb.get("questions"):
                    st.caption("예상 질문")
                    for q in fb["questions"]:
                        st.markdown(f"- {q}")


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
    render_image_feedback_section(faculty_data)

    st.divider()
    st.markdown("### ✍️ 에세이 매칭")

    essay_strategy = (admission_info or {}).get("essay_strategy")
    if essay_strategy:
        with st.expander("📖 작성 가이드 보기 — SOP/아티스트 스테이트먼트 작성 전략"):
            render_essay_strategy_guide(essay_strategy)

    st.markdown("#### 🔗 포트폴리오 ↔ 에세이 상호보완성 분석")
    st.caption(
        "글에서 주장한 탐구가 시각물로 증명되는지, 시각물이 미처 설명하지 못한 맥락을 글이 채워주는지를 봅니다. "
        "포트폴리오를 평가하고 아래 에세이를 분석하면 결과가 이 아래에 표시됩니다."
    )
    with st.expander("ℹ️ 포트폴리오 분석방법 - 포트폴리오와 에세이 매칭방법"):
        st.markdown(
            "**이미지가 아니라 텍스트를 분석합니다.** 이 도구는 업로드된 이미지 파일을 시각적으로 "
            "판독하지 않습니다. 대신 각 포트폴리오 슬롯에 입력한 **제목 + 재료 + 설명**을 "
            "`\"제목. 재료. 설명\"` 형태의 한 문장으로 합친 뒤, 에세이를 문단 단위로 나눈 것과 함께 "
            "임베딩(문장을 의미 벡터로 변환)해서 코사인 유사도로 비교합니다. "
            "교수진 매칭에 쓰는 것과 동일한 임베딩 백엔드(TF-IDF / Sentence-Transformers / OpenAI)를 재사용합니다."
        )
        st.markdown(
            "**양방향으로 커버리지를 계산합니다.**\n"
            "- 포트폴리오 → 에세이: 각 작품의 텍스트와 가장 유사한 에세이 문단을 찾고, 평균보다 유사도가 "
            "많이 낮은 작품은 '글로 뒷받침되지 않은 시각적 주장(visual gap)'으로 표시합니다.\n"
            "- 에세이 → 포트폴리오: 각 문단과 가장 유사한 작품을 찾고, 평균보다 유사도가 많이 낮은 문단은 "
            "'이미지로 증명되지 않은 주장(text gap)'으로 표시합니다."
        )
        st.warning(
            "**따라서 제목·재료·설명을 얼마나 꼼꼼하고 구체적으로 채웠는지가 분석 품질을 좌우합니다.** "
            "제목이 '무제'이거나 재료 란에 재료명만 짧게 적혀 있거나 설명이 비어 있으면, 실제 이미지가 "
            "에세이와 개념적으로 잘 맞물려도 유사도 계산에 반영될 텍스트 자체가 없어서 '공백(gap)'으로 "
            "잘못 표시될 수 있습니다. 반대로 설명을 에세이 문장과 비슷한 개념어로 채우면 실제 작품 내용과 "
            "무관하게 유사도가 높게 나올 수도 있습니다 — 즉 이 점수는 '이미지와 글의 실제 일치'가 아니라 "
            "'입력한 텍스트 사이의 의미적 유사성'을 재는 것이므로, 참고용 보조 지표로 활용하고 최종 판단은 "
            "직접 이미지와 에세이를 함께 보며 내려야 합니다."
        )

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
            st.markdown("#### 결과")
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

def render_admission_info(info):
    st.markdown("## 📋 DoVA 지원 요건")

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
# Graduate opportunities (dova.uchicago.edu/graduate/opportunities)
# ---------------------------------------------------------------------------

OPPORTUNITIES = [
    {
        "title": "Teaching Fellowship (교육 펠로우십)",
        "description": "최근 DoVA 졸업생을 위한 1년 프로그램으로, 교육 역량 강화와 예술 실무 발전을 목표로 합니다.",
        "details": [
            "Arts 코어 과목 4개를 담당하는 전임 강사(Full-time Lecturer) 직책",
            "개인 예술 활동을 지속하고 캠퍼스 활동에 참여할 것을 기대",
            "분기말 MFA 크리틱 및 봄학기 학부 크리틱 참석",
            "Chicago Center for Teaching 및 DoVA 디렉터를 통한 교육/전문성 개발 참여",
        ],
        "link": None,
    },
    {
        "title": "Ground Floor: A Biennial Exhibition of New Art from Chicago",
        "description": "시카고 5개 MFA 프로그램(Columbia College Chicago, Northwestern University, School of the Art Institute of Chicago, University of Chicago, University of Illinois at Chicago)에서 20명의 작가를 선발하는 격년제 전시로, 2010년 시작되었습니다.",
        "details": [
            "학과 추천 및 심사위원회 검토를 통해 선정",
            "전시 및 도록(publication) 발간 포함",
            "Hyde Park Art Center에서 개최",
        ],
        "link": ("Ground Floor at Hyde Park Art Center", "https://www.hydeparkart.org/get-involved/artist-opportunities/ground-floor/"),
    },
    {
        "title": "Arts Club of Chicago Fellowship",
        "description": "시카고 지역 신진 작가를 위한 격년제 펠로우십으로, 학과 추천이 필요한 경쟁 프로그램입니다.",
        "details": [
            "선정된 펠로우는 Arts Club의 프로그램 및 전시에 참여",
            "최근 추천자: Brit Barton (2016), Takashi Shallow (MFA 2018), Daisy Schultz (2020), Quichen Wu (2023)",
        ],
        "link": ("Arts Club of Chicago", "https://www.artsclubchicago.org/"),
    },
    {
        "title": "EXPO CHICAGO",
        "description": "국제 현대·근대 미술 아트페어로, DoVA가 최근 MFA 졸업생의 부스 참가 비용을 지원합니다.",
        "details": [
            "Reva and David Logan Center for the Arts와 협력",
            "매년 Navy Pier의 Festival Hall에서 4일간 개최",
            "작가, 컬렉터, 갤러리스트 및 국제적인 관객에게 노출될 기회 제공",
        ],
        "link": ("EXPO CHICAGO", "https://www.expochicago.com/"),
    },
    {
        "title": "Outside Visitors Program",
        "description": "동문을 초청 비평가 및 강연자로 초대하여 커뮤니티와의 연결을 유지하는 프로그램입니다.",
        "details": [
            "Tuesday Night Critiques, Quarter-End Critiques, Senior Seminars",
            "MFA 학생 스튜디오 방문, 동문 강연 및 패널",
            "과거 참여자: Devin T. Mays (MFA 2016), Dado (MFA 2014), Matthew Metzger (MFA 2009), John Preus (MFA 2006), Karen Reimer (MFA 1989)",
        ],
        "link": None,
    },
    {
        "title": "Office of Career Advancement",
        "description": "경험 학습(experiential learning) 기회를 제공하고, 재학생 및 동문을 고용주와 연결합니다.",
        "details": [],
        "link": ("Career Advancement", "https://careeradvancement.uchicago.edu/"),
    },
]


def render_opportunities():
    st.markdown("## 🎓 DoVA 졸업 후 진로 & 기회")
    st.caption(
        "출처: [dova.uchicago.edu/graduate/opportunities]"
        "(https://dova.uchicago.edu/graduate/opportunities)"
    )

    for opp in OPPORTUNITIES:
        with st.container(border=True):
            st.markdown(f"**{opp['title']}**")
            st.write(opp["description"])
            for d in opp["details"]:
                st.markdown(f"- {d}")
            if opp["link"]:
                label, url = opp["link"]
                st.markdown(f"🔗 [{label}]({url})")

    st.markdown("### 문의처")
    st.markdown(
        "**Department of Visual Arts**  \n"
        "Reva and David Logan Center for the Arts  \n"
        "915 East 60th Street, Suite 236, Chicago, IL 60637  \n"
        "Email: [dova@uchicago.edu](mailto:dova@uchicago.edu)  \n"
        "Phone: (773) 753-4821"
    )


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
        if st.button("🎓 진로 & 기회", width="stretch", type="primary" if tab == "opportunities" and not person_name else "secondary"):
            go_to(tab="opportunities")
    with nav3:
        if st.button("🖼️✍️ 포트폴리오/에세이 매칭", width="stretch", type="primary" if tab == "match" else "secondary"):
            go_to(tab="match")
    with nav4:
        if st.button("📋 지원 요건", width="stretch", type="primary" if tab == "info" else "secondary"):
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

    if tab == "opportunities":
        render_opportunities()
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
