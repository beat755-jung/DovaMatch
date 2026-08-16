"""Sends an uploaded portfolio image to Claude (vision) and asks it to imagine how
each of the 9 DoVA faculty might react to it — what they'd likely say or critique,
and what questions they might ask the applicant.

This is a genuine image analysis (unlike src/matcher.py, which only compares text).
Sending the image means it leaves the machine and goes to Anthropic's API, so this
is only ever called after the user has explicitly consented in the UI.

Usage:
    from src.image_feedback import analyze_portfolio_image
    report = analyze_portfolio_image(image_bytes, "image/jpeg", faculty_data)
"""

import json
import os

MODEL = "claude-opus-5"


def _build_faculty_context(faculty_data, bio_chars=300):
    lines = []
    for person in faculty_data:
        parts = [f"- {person['name']}"]
        if person.get("philosophy"):
            parts.append(f"철학/설명: {person['philosophy'][:bio_chars]}")
        if person.get("visual_languages"):
            parts.append("자주 쓰는 표현 언어: " + ", ".join(person["visual_languages"]))
        lines.append(" | ".join(parts))
    return "\n".join(lines)


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_impression": {
            "type": "string",
            "description": "이미지 자체에 대한 중립적인 시각적 관찰 (매체, 구도, 색, 주제 등), 2~4문장, 한국어.",
        },
        "faculty_feedback": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "교수 이름 (제공된 목록의 이름과 정확히 일치)"},
                    "reaction": {
                        "type": "string",
                        "description": "이 교수가 자신의 예술 철학/표현 언어의 관점에서 이 이미지를 볼 때 할 법한 평가나 코멘트, 2~4문장, 한국어.",
                    },
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "이 교수가 작가에게 던질 법한 질문 2~3개, 한국어.",
                    },
                },
                "required": ["name", "reaction", "questions"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["overall_impression", "faculty_feedback"],
    "additionalProperties": False,
}


def analyze_portfolio_image(image_bytes, media_type, faculty_data, api_key=None, model=MODEL):
    """Returns {"overall_impression": str, "faculty_feedback": [{"name", "reaction", "questions"}]}."""
    import base64

    import anthropic

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY가 설정되어 있지 않습니다. 이미지를 Claude API로 분석하려면 "
            "환경 변수를 설정해야 합니다."
        )

    client = anthropic.Anthropic(api_key=api_key)
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    faculty_context = _build_faculty_context(faculty_data)

    prompt = (
        "당신은 시카고대학교 DoVA(Department of Visual Arts) 대학원 입시 포트폴리오 리뷰를 "
        "돕는 어시스턴트입니다. 아래에 지원자가 업로드한 작품 이미지 한 장과, DoVA 교수진 9인의 "
        "예술 철학/자주 쓰는 표현 언어 목록이 주어집니다.\n\n"
        f"[교수진 목록]\n{faculty_context}\n\n"
        "이미지를 실제로 시각적으로 분석한 뒤, 각 교수가 자신의 철학과 관심사에 비추어 이 이미지를 "
        "볼 때 실제로 할 법한 평가나 코멘트, 그리고 작가에게 던질 법한 질문을 상상해서 작성하세요. "
        "일반적인 칭찬이 아니라 각 교수의 실제 관심사(재료, 개념, 형식, 정체성, 노동, 몸 등)에 "
        "구체적으로 연결된 반응이어야 합니다. 9명 전원에 대해 작성하세요."
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude가 이 요청을 거부했습니다. 다른 이미지로 다시 시도해주세요.")

    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)
