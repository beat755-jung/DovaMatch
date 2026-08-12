"""Evaluates a 20-piece studio-art portfolio against the DoVA sequencing
strategy (Hook -> Body -> Climax -> Open Ending), checks each slot's
title/year/size/material/description fields as a "mini artist statement"
(not just Slideroom metadata), and — given an SOP essay — measures how well
the portfolio and the essay cover each other's ground (the "visual thesis"
should make claims the essay proves, and the essay should supply context the
images can't carry on their own).

Reuses src.matcher's embedding backends (tfidf / sentence-transformers /
openai) and cosine_similarity so portfolio cohesion and essay-portfolio
complementarity are scored the same way essay-faculty matching is.
"""

import statistics

from .matcher import cosine_similarity, split_paragraphs

PORTFOLIO_SIZE = 20

STAGES = [
    {"key": "hook", "label": "1~3번 · The Hook", "lo": 1, "hi": 3},
    {"key": "body", "label": "4~15번 · The Body (Process & Expansion)", "lo": 4, "hi": 15},
    {"key": "climax", "label": "16~19번 · The Climax & Detail", "lo": 16, "hi": 19},
    {"key": "ending", "label": "20번 · The Open Ending", "lo": 20, "hi": 20},
]

PITFALL_KEYWORDS = [
    "습작", "크로키", "누드 드로잉", "인체 드로잉 연습", "인체 크로키", "투시도 연습",
    "수업 과제", "학교 과제", "과제로 제출", "기초 실기", "정물 연습",
    "figure drawing exercise", "life drawing study", "perspective study",
    "class assignment", "school assignment", "technical exercise", "gesture drawing practice",
]

DESCRIPTION_CUE_WORDS = [
    "개념", "탐구", "비평", "질문", "실험", "에세이", "스테이트먼트", "이론", "맥락",
    "critique", "inquiry", "concept", "statement", "theory", "context",
]

ENDING_CUE_WORDS = [
    "다음 단계", "스케치", "실험작", "진행 중", "습작이 아닌 실험", "발전시키고 싶은",
    "work in progress", "study for", "next step", "ongoing", "sketch",
]

UNTITLED_VALUES = {"", "무제", "untitled", "untitled work", "무제(untitled)"}


def empty_portfolio(size=PORTFOLIO_SIZE):
    return [
        {
            "index": i,
            "title": "",
            "year": "",
            "size": "",
            "material": "",
            "medium": "",
            "description": "",
            "detail_shot": False,
            "cross_media": False,
        }
        for i in range(1, size + 1)
    ]


def _is_empty(item):
    return not (
        (item.get("title") or "").strip()
        or (item.get("description") or "").strip()
        or (item.get("material") or "").strip()
    )


def _stage_items(items, lo, hi):
    return [it for it in items if lo <= it["index"] <= hi]


def _pitfall_hits(item):
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    return [kw for kw in PITFALL_KEYWORDS if kw.lower() in text]


def _title_is_untitled(item):
    return (item.get("title") or "").strip().lower() in UNTITLED_VALUES


def _material_is_thin(item):
    material = (item.get("material") or "").strip()
    if not material:
        return None  # handled as "missing" separately
    return len(material.split()) <= 3


def _description_quality(item):
    desc = (item.get("description") or "").strip()
    if len(desc) < 10:
        return "missing"
    has_cue = any(c in desc for c in DESCRIPTION_CUE_WORDS)
    if has_cue or len(desc) >= 40:
        return "ok"
    return "weak"


def _item_issues(item):
    """Per-slot mini-statement feedback: title / material / description /
    academic-exercise pitfalls."""
    issues = []
    if _title_is_untitled(item):
        issues.append("제목이 '무제(Untitled)'입니다. 작업의 태도를 드러내는 제목을 붙이는 것을 고려하세요.")

    thin = _material_is_thin(item)
    if thin is None:
        issues.append("재료(Material) 란이 비어 있습니다.")
    elif thin:
        issues.append(
            "재료 란이 단순 재료명뿐입니다. 매체적 맥락을 더해보세요 "
            "(예: \"Oil and collected domestic dust on canvas\")."
        )

    dq = _description_quality(item)
    if dq == "missing":
        issues.append("설명(미니 에세이)이 비어 있거나 너무 짧습니다.")
    elif dq == "weak":
        issues.append("설명에 이론적 배경/에세이와의 연결 고리가 약해 보입니다.")

    hits = _pitfall_hits(item)
    if hits:
        issues.append(
            f"기술 과시용 습작으로 보일 수 있는 표현이 감지되었습니다 ({', '.join(hits)}). "
            "자기주도적 탐구를 보여주는 작업인지 다시 검토하세요."
        )
    return issues


def _stage_feedback(items):
    feedback = []
    filled_by_stage = {}

    for stage in STAGES:
        stage_items = _stage_items(items, stage["lo"], stage["hi"])
        filled = [it for it in stage_items if not _is_empty(it)]
        filled_by_stage[stage["key"]] = filled
        messages = []

        if not filled:
            messages.append("이 구간이 아직 비어 있습니다.")
            feedback.append({"stage": stage["label"], "range": f"{stage['lo']}-{stage['hi']}",
                              "status": "empty", "messages": messages})
            continue

        if stage["key"] == "hook":
            missing_desc = [it for it in filled if _description_quality(it) == "missing"]
            if missing_desc:
                messages.append(
                    "가장 먼저 보이는 1~3번은 질문이 명확해야 합니다. "
                    f"{len(missing_desc)}개 작품의 설명이 비어 있어 개념이 즉시 읽히지 않을 수 있습니다."
                )
            pitfalls = [it for it in filled if _pitfall_hits(it)]
            if pitfalls:
                messages.append("첫인상을 좌우하는 구간에 기술 연습작으로 보이는 작품이 섞여 있습니다.")

        elif stage["key"] == "body":
            media = {it.get("medium") for it in filled if (it.get("medium") or "").strip()}
            if len(media) < 2:
                messages.append(
                    "본문(4~15번) 구간의 매체가 한 가지로 고정되어 있습니다. "
                    "다른 매체·다른 각도의 실험을 교차 배치하면 DoVA가 중시하는 융합 역량이 드러납니다."
                )
            cross_media_count = sum(1 for it in filled if it.get("cross_media"))
            if cross_media_count == 0:
                messages.append(
                    "'교차 매체' 표시가 된 작품이 없습니다. 과정 퍼포먼스 영상 컷, 조각을 왜곡해 찍은 사진 등 "
                    "초반 개념을 다른 매체로 확장한 작업이 있다면 체크해 표시하세요."
                )
            pitfalls = [it for it in filled if _pitfall_hits(it)]
            if pitfalls:
                messages.append(f"{len(pitfalls)}개 작품에서 기술 연습작으로 보이는 표현이 감지되었습니다.")

        elif stage["key"] == "climax":
            detail_count = sum(1 for it in filled if it.get("detail_shot"))
            if detail_count == 0:
                messages.append(
                    "16~19번 구간에 클로즈업/디테일 컷(마감, 접합부, 질감 등)으로 표시된 작품이 없습니다. "
                    "물질에 대한 집요함(Material Intelligence)을 보여줄 매크로 샷을 최소 1~2점 포함하세요."
                )

        elif stage["key"] == "ending":
            item20 = filled[0]
            text = f"{item20.get('title', '')} {item20.get('description', '')}".lower()
            if not any(c.lower() in text for c in ENDING_CUE_WORDS):
                messages.append(
                    "완결된 작품보다 '다음 2년 동안 파고들고 싶은' 스케치·실험작을 배치하면 "
                    "발전 가능성을 암시하는 오픈 엔딩으로 마무리할 수 있습니다."
                )

        feedback.append({
            "stage": stage["label"], "range": f"{stage['lo']}-{stage['hi']}",
            "status": "warn" if messages else "ok", "messages": messages,
        })

    return feedback, filled_by_stage


def _cohesion(non_empty_items, core_concept, backend):
    if not core_concept.strip() or backend is None or len(non_empty_items) < 2:
        return {"available": False}

    texts = [core_concept] + [
        f"{it['title']}. {it['material']}. {it['description']}" for it in non_empty_items
    ]
    vectors = backend.embed(texts)
    core_vec, item_vecs = vectors[0], vectors[1:]
    scores = [cosine_similarity(core_vec, v) for v in item_vecs]

    mean = statistics.mean(scores)
    stdev = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    threshold = mean - 0.5 * stdev

    outliers = sorted(
        (
            {"index": it["index"], "title": it["title"] or f"{it['index']}번", "score": round(s * 100, 1)}
            for it, s in zip(non_empty_items, scores)
            if s < threshold
        ),
        key=lambda o: o["score"],
    )[:5]

    return {
        "available": True,
        "mean_score": round(mean * 100, 1),
        "outliers": outliers,
    }


def evaluate_portfolio(items, core_concept="", backend=None):
    """Full portfolio report: completeness, sequencing stage feedback,
    per-slot mini-statement issues, and (if a core concept + backend are
    given) conceptual-cohesion outliers."""
    non_empty = [it for it in items if not _is_empty(it)]
    stage_feedback, _ = _stage_feedback(items)

    item_feedback = []
    for it in non_empty:
        issues = _item_issues(it)
        if issues:
            item_feedback.append({"index": it["index"], "title": it["title"] or f"{it['index']}번", "issues": issues})

    cohesion = _cohesion(non_empty, core_concept, backend)

    total_issues = (
        sum(len(s["messages"]) for s in stage_feedback)
        + sum(len(f["issues"]) for f in item_feedback)
        + len(cohesion.get("outliers", []))
    )
    filled_count = len(non_empty)

    if filled_count == 0:
        grade, message = "미작성", "포트폴리오 슬롯을 채우면 평가가 시작됩니다."
    elif total_issues == 0 and filled_count == PORTFOLIO_SIZE:
        grade, message = "우수", "시퀀싱, 매체 다양성, 미니 에세이가 고르게 잘 갖춰져 있습니다."
    elif total_issues <= 3:
        grade, message = "양호", "전반적으로 탄탄합니다. 아래 세부 항목만 보완하세요."
    elif total_issues <= 8:
        grade, message = "보완 필요", "시퀀싱 또는 미니 에세이 일부를 보강하면 완성도가 크게 올라갑니다."
    else:
        grade, message = "재구성 필요", "여러 구간에서 개념적 일관성과 정보가 부족합니다. 전체 흐름을 다시 검토하세요."

    return {
        "filled_count": filled_count,
        "missing_count": PORTFOLIO_SIZE - filled_count,
        "stage_feedback": stage_feedback,
        "item_feedback": item_feedback,
        "cohesion": cohesion,
        "summary": {"total_issues": total_issues, "grade": grade, "message": message},
    }


# ---------------------------------------------------------------------------
# Essay <-> portfolio complementarity
# ---------------------------------------------------------------------------

def analyze_essay_portfolio_complementarity(essay_text, items, backend):
    """Bidirectional coverage check between the SOP essay and the portfolio's
    mini-statements:
      - visual_gaps: portfolio pieces whose theoretical context isn't picked
        up by any essay paragraph (image says something the text never backs up)
      - text_gaps: essay paragraphs whose claims aren't grounded in any
        portfolio piece (text claims something the images never show)
      - strong_links: best-matching pairs, i.e. where the complementary
        structure is already working
    Returns None if there isn't enough material (empty essay/portfolio, or no
    embedding backend) to say anything meaningful.
    """
    non_empty = [it for it in items if not _is_empty(it)]
    paragraphs = split_paragraphs(essay_text)
    if not paragraphs or not non_empty or backend is None:
        return None

    portfolio_texts = [
        f"{it['title']}. {it['material']}. {it['description']}".strip() for it in non_empty
    ]
    vectors = backend.embed(paragraphs + portfolio_texts)
    para_vecs = vectors[:len(paragraphs)]
    item_vecs = vectors[len(paragraphs):]

    visual_links = []
    for it, iv in zip(non_empty, item_vecs):
        scores = [cosine_similarity(iv, pv) for pv in para_vecs]
        best_idx = max(range(len(scores)), key=lambda j: scores[j])
        visual_links.append({"item": it, "paragraph": paragraphs[best_idx], "score": scores[best_idx]})

    text_links = []
    for para, pv in zip(paragraphs, para_vecs):
        scores = [cosine_similarity(pv, iv) for iv in item_vecs]
        best_idx = max(range(len(scores)), key=lambda j: scores[j])
        text_links.append({"paragraph": para, "item": non_empty[best_idx], "score": scores[best_idx]})

    def _threshold(links):
        scores = [link["score"] for link in links]
        if len(scores) < 3:
            return min(scores) - 1  # not enough data to flag anything
        mean = statistics.mean(scores)
        stdev = statistics.pstdev(scores)
        return mean - 0.5 * stdev

    visual_threshold = _threshold(visual_links)
    text_threshold = _threshold(text_links)

    visual_gaps = sorted(
        [link for link in visual_links if link["score"] < visual_threshold],
        key=lambda link: link["score"],
    )
    text_gaps = sorted(
        [link for link in text_links if link["score"] < text_threshold],
        key=lambda link: link["score"],
    )
    strong_links = sorted(visual_links, key=lambda link: -link["score"])[:3]

    portfolio_coverage_pct = round(100 * (len(visual_links) - len(visual_gaps)) / len(visual_links), 1)
    essay_coverage_pct = round(100 * (len(text_links) - len(text_gaps)) / len(text_links), 1)

    return {
        "portfolio_coverage_pct": portfolio_coverage_pct,
        "essay_coverage_pct": essay_coverage_pct,
        "visual_gaps": visual_gaps,
        "text_gaps": text_gaps,
        "strong_links": strong_links,
    }
