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
import sys
from pathlib import Path
from urllib.parse import quote, unquote

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analyzer import DATA_DIR, load_faculty_data  # noqa: E402
from src.matcher import analyze_essay, get_backend, load_alumni_data  # noqa: E402

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


def render_match_dashboard(faculty_data, alumni_data):
    st.markdown("## ✍️ 에세이 매칭 대시보드")
    st.caption("SOP 에세이를 입력하면 교수 9인 + 한국인 동문 2인의 철학/표현 언어와 비교해 핏이 높은 순서로 보여줍니다.")

    with st.expander("⚙️ 임베딩 설정 (기본값 그대로 사용해도 됩니다)"):
        backend_choice = st.selectbox(
            "임베딩 백엔드",
            ["auto (로컬, 권장)", "sentence-transformers", "tfidf", "openai (에세이 전송, 명시적 동의 필요)"],
            index=0,
        )
        top_k = st.slider("교수 매칭 상위 N명", min_value=1, max_value=9, value=3)
        openai_consent = False
        if backend_choice.startswith("openai"):
            st.warning(
                "openai 백엔드는 에세이 전문을 OpenAI 임베딩 API로 전송합니다. "
                "`OPENAI_API_KEY` 환경 변수가 설정되어 있어야 합니다."
            )
            openai_consent = st.checkbox("에세이를 OpenAI API로 전송하는 데 동의합니다.")

    essay_text = st.text_area(
        "SOP 에세이 텍스트",
        height=280,
        placeholder="여기에 Artist's Statement / SOP 에세이 전문을 붙여넣으세요...",
    )

    disabled = backend_choice.startswith("openai") and not openai_consent
    if st.button("분석하기", type="primary", disabled=disabled, width="stretch"):
        if not essay_text.strip():
            st.error("에세이 텍스트를 입력해주세요.")
            return
        backend_name = backend_choice.split(" ")[0]
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
        st.session_state["last_report"] = report

    report = st.session_state.get("last_report")
    if report:
        st.info(f"임베딩 백엔드: {report['backend']}")
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
    st.markdown("## 📋 DoVA 지원 요건 & 내 점수")

    st.markdown("### 내 어학 점수 (TOEFL)")
    scores = info["my_scores"]
    score_entries = [
        ("총점 (뉴토플)", scores["toefl_new_total"]),
        ("총점 (구토플 환산)", scores["toefl_old_total"]),
        ("Reading", scores["reading"]),
        ("Listening", scores["listening"]),
        ("Speaking", scores["speaking"]),
        ("Writing", scores["writing"]),
    ]
    cols = st.columns(len(score_entries))
    for col, (label, value) in zip(cols, score_entries):
        with col:
            st.metric(label, value)

    st.markdown("### 제출 서류 요건")
    for doc in info["required_documents"]:
        with st.container(border=True):
            st.markdown(f"**{doc['item']}**")
            st.write(doc["requirement"])
            st.caption(f"💡 {doc['tip']}")

    if info.get("faculty_academic_orientation"):
        fao = info["faculty_academic_orientation"]
        st.markdown("### DoVA 교수진의 학문적 성향")
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

    if info.get("portfolio_strategy"):
        ps = info["portfolio_strategy"]
        st.markdown("### 포트폴리오(20점) 구성 전략")
        st.write(ps["intro"])

        if ps.get("sequencing_stages"):
            st.markdown("**시퀀싱 전략: 기승전결이 있는 시각 논문 만들기**")
            for stage in ps["sequencing_stages"]:
                with st.container(border=True):
                    st.markdown(f"**{stage['range']}**")
                    st.write(stage["description"])

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
    st.caption("시카고대학교 DoVA 지원자를 위한 교수진 아카이브 & 에세이 매칭")

    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        if st.button("👩‍🏫 교수진 갤러리", width="stretch", type="primary" if tab == "faculty" and not person_name else "secondary"):
            go_to(tab="faculty")
    with nav2:
        if st.button("🇰🇷 한국인 동문", width="stretch", type="primary" if tab == "alumni" and not person_name else "secondary"):
            go_to(tab="alumni")
    with nav3:
        if st.button("✍️ 에세이 매칭", width="stretch", type="primary" if tab == "match" else "secondary"):
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
        render_match_dashboard(faculty_data, alumni_data)
    elif tab == "info":
        render_admission_info(admission_info)
    else:
        st.markdown("## 👩‍🏫 교수진 아카이브")
        render_gallery(faculty_data, alumni=False)


if __name__ == "__main__":
    main()
