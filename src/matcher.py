"""Matches a Statement of Purpose (SOP) essay against the 9 DoVA professors'
philosophy / visual_languages fields (produced by src/analyzer.py) and reports
the strongest academic/artistic fits. It also scores the essay against
data/alumni_data.json (Korean DoVA/DoVA-affiliated alumni) and surfaces those
as a separate "alumni reference" section — inspirational precedent, not
professors to rank the essay's fit against.

Embedding backend (in order of preference, first one that loads wins):
  1. sentence-transformers, model "paraphrase-multilingual-MiniLM-L12-v2"
     (local, no network calls after the model is cached, handles Korean+English).
  2. Pure-Python TF-IDF + cosine similarity (no extra dependencies, always works,
     but only finds *lexical* overlap — an English SOP paragraph won't match a
     Korean keyword and vice versa).

OpenAI's embedding API is supported too (`--backend openai`), but is never
selected automatically: your essay is personal, unpublished material, and using
it means sending its full text to an external API. Only pass `--backend openai`
if you're fine with that; it also requires `pip install openai` and an
`OPENAI_API_KEY` environment variable.

Usage:
    python -m src.matcher path/to/essay.txt
    python -m src.matcher path/to/essay.txt --backend openai --top-k 5 --json
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

from .analyzer import ALUMNI_DATA_FILE, DATA_DIR, load_faculty_data

DEFAULT_ST_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_OPENAI_MODEL = "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Embedding backends
# ---------------------------------------------------------------------------

class EmbeddingBackend:
    name = "base"

    def embed(self, texts):
        """Return a list of equal-length float vectors, one per input text."""
        raise NotImplementedError


class SentenceTransformerBackend(EmbeddingBackend):
    def __init__(self, model_name=DEFAULT_ST_MODEL):
        from sentence_transformers import SentenceTransformer

        self.name = f"sentence-transformers ({model_name})"
        self._model = SentenceTransformer(model_name)

    def embed(self, texts):
        return self._model.encode(list(texts), convert_to_numpy=False)


class OpenAIEmbeddingBackend(EmbeddingBackend):
    def __init__(self, model_name=DEFAULT_OPENAI_MODEL):
        from openai import OpenAI

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. --backend openai sends your essay "
                "text to OpenAI's API, so it must be explicitly configured."
            )
        self.name = f"openai ({model_name})"
        self._model_name = model_name
        self._client = OpenAI()

    def embed(self, texts):
        texts = list(texts)
        response = self._client.embeddings.create(model=self._model_name, input=texts)
        return [item.embedding for item in response.data]


_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is",
    "are", "was", "were", "be", "been", "being", "as", "at", "by", "from",
    "that", "this", "these", "those", "it", "its", "i", "my", "me", "we", "our",
    "he", "she", "they", "their", "his", "her", "not", "but", "have", "has",
    "had", "will", "would", "can", "could", "which", "who", "what", "how",
}
_TOKEN_RE = re.compile(r"[A-Za-z']+|[가-힣]+")


def _tokenize(text):
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS]


class TfidfBackend(EmbeddingBackend):
    """Dependency-free fallback: TF-IDF vectors over the vocabulary of the
    exact batch of texts passed to `embed()`. Only captures lexical overlap —
    no cross-language or synonym matching — which is why it's the last resort.
    """

    name = "tfidf (fallback, no embedding model installed)"

    def embed(self, texts):
        texts = list(texts)
        tokenized = [_tokenize(t) for t in texts]
        doc_freq = Counter()
        for tokens in tokenized:
            doc_freq.update(set(tokens))

        n_docs = len(texts)
        vocab = {term: i for i, term in enumerate(doc_freq)}
        idf = {
            term: math.log((1 + n_docs) / (1 + df)) + 1.0
            for term, df in doc_freq.items()
        }

        vectors = []
        for tokens in tokenized:
            vec = [0.0] * len(vocab)
            counts = Counter(tokens)
            for term, tf in counts.items():
                vec[vocab[term]] = tf * idf[term]
            vectors.append(vec)
        return vectors


def get_backend(name="auto", model=None):
    """Resolve a backend by name. 'auto' tries sentence-transformers, then
    falls back to TF-IDF; 'openai' must be requested explicitly (see module
    docstring for why).
    """
    if name in ("auto", "sentence-transformers"):
        try:
            return SentenceTransformerBackend(model or DEFAULT_ST_MODEL)
        except Exception as e:
            if name == "sentence-transformers":
                raise RuntimeError(f"sentence-transformers backend unavailable: {e}") from e
            print(
                f"[matcher] sentence-transformers unavailable ({e}); "
                "falling back to TF-IDF.",
                file=sys.stderr,
            )
    if name == "openai":
        return OpenAIEmbeddingBackend(model or DEFAULT_OPENAI_MODEL)
    if name in ("auto", "tfidf"):
        return TfidfBackend()
    raise ValueError(f"unknown backend: {name}")


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Essay / professor text prep
# ---------------------------------------------------------------------------

def split_paragraphs(essay_text):
    paragraphs = re.split(r"\n\s*\n", essay_text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def load_alumni_data(filename=ALUMNI_DATA_FILE):
    """Load data/alumni_data.json; returns [] if the file doesn't exist (optional)."""
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_professor_profile_text(record, bio_chars=400):
    """Text representing a person (faculty or alumni) for matching:
    philosophy + visual_languages weighted first, with a bio excerpt appended
    for records whose analyzer-extracted fields are thin (e.g. bios with
    little explicit philosophy language).
    """
    parts = []
    if record.get("philosophy"):
        parts.append(record["philosophy"])
    if record.get("visual_languages"):
        parts.append("Keywords: " + ", ".join(record["visual_languages"]))
    if record.get("bio"):
        parts.append(record["bio"][:bio_chars])
    return " ".join(parts)


def _has_batchim(word):
    """True if `word`'s last syllable ends in a Hangul final consonant."""
    if not word:
        return False
    code = ord(word[-1])
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 != 0
    return False  # non-Hangul (e.g. an English name) — assume no batchim


def _josa(word, batchim_form, no_batchim_form):
    return batchim_form if _has_batchim(word) else no_batchim_form


def build_guide_feedback(record, best_paragraph, recommended_keywords, role_label="교수"):
    name = record["name"]
    philosophy = record.get("philosophy", "").strip()
    kw_text = ", ".join(f"'{k}'" for k in recommended_keywords) if recommended_keywords else ""
    ga_i = _josa(role_label, "이", "가")
    gwa_wa = _josa(role_label, "과", "와")

    lines = []
    if philosophy:
        lines.append(f"{name} {role_label}의 예술 철학: \"{philosophy}\"")
    if best_paragraph:
        excerpt = best_paragraph if len(best_paragraph) <= 200 else best_paragraph[:200] + "..."
        lines.append(f"에세이에서 가장 맞닿아 있는 문단: \"{excerpt}\"")
    if kw_text:
        lines.append(
            f"이 지점에서 {name} {role_label}{ga_i} 자주 쓰는 표현 언어인 {kw_text} 등을 "
            "구체적으로 인용하거나 연계해 서술하면, 두 사람의 관심사가 겹치는 지점을 "
            "더 뚜렷하게 드러낼 수 있습니다."
        )
    else:
        lines.append(
            f"{name} {role_label}{gwa_wa}의 접점을 명확히 하려면, 에세이에 매체/기법/개념 관련 "
            "구체적 어휘를 추가해 비교할 수 있는 지점을 늘리는 것이 좋습니다."
        )
    return " ".join(lines)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _build_matches(essay_vec, records, record_vecs, keyword_index, keyword_vecs,
                    paragraphs, para_vecs, role_label, limit=None):
    """Score `records` against the essay and return match dicts, best first.

    Shared between faculty ranking (limited to top_k) and alumni reference
    scoring (all records, no truncation) so both use identical logic.
    """
    scores = [cosine_similarity(essay_vec, rv) for rv in record_vecs]
    order = sorted(range(len(records)), key=lambda i: -scores[i])
    if limit is not None:
        order = order[:limit]

    matches = []
    for rank_pos, i in enumerate(order, start=1):
        record = records[i]

        kw_scored = [
            (kw, cosine_similarity(essay_vec, keyword_vecs[keyword_index[kw]]))
            for kw in record.get("visual_languages", [])
        ]
        kw_scored.sort(key=lambda pair: -pair[1])
        recommended_keywords = [kw for kw, _ in kw_scored[:5]]

        best_paragraph, best_paragraph_score = "", 0.0
        if paragraphs:
            para_scores = [cosine_similarity(record_vecs[i], pv) for pv in para_vecs]
            best_idx = max(range(len(paragraphs)), key=lambda j: para_scores[j])
            best_paragraph = paragraphs[best_idx]
            best_paragraph_score = para_scores[best_idx]

        matches.append({
            "rank": rank_pos,
            "name": record["name"],
            "match_score": round(scores[i] * 100, 1),
            "philosophy": record.get("philosophy", ""),
            "recommended_keywords": recommended_keywords,
            "best_matching_paragraph": best_paragraph,
            "best_matching_paragraph_score": round(best_paragraph_score * 100, 1),
            "guide_feedback": build_guide_feedback(
                record, best_paragraph, recommended_keywords, role_label
            ),
        })
    return matches


def analyze_essay(essay_text, faculty_data=None, alumni_data=None, backend=None,
                   backend_name="auto", model=None, top_k=3):
    """Return a structured match report:
      - top_matches: top_k faculty ranked by cosine similarity to the essay
      - alumni_references: all Korean DoVA/DoVA-affiliated alumni, scored the
        same way, for inspiration rather than competitive ranking
    """
    if faculty_data is None:
        faculty_data = load_faculty_data()
    if alumni_data is None:
        alumni_data = load_alumni_data()
    if backend is None:
        backend = get_backend(backend_name, model)

    paragraphs = split_paragraphs(essay_text)
    faculty_profiles = [build_professor_profile_text(r) for r in faculty_data]
    alumni_profiles = [build_professor_profile_text(r) for r in alumni_data]

    keyword_index = {}
    for record in faculty_data + alumni_data:
        for kw in record.get("visual_languages", []):
            if kw not in keyword_index:
                keyword_index[kw] = len(keyword_index)
    keywords = list(keyword_index.keys())

    texts = [essay_text] + faculty_profiles + alumni_profiles + keywords + paragraphs
    vectors = backend.embed(texts)

    pos = 0
    essay_vec = vectors[pos]; pos += 1
    faculty_vecs = vectors[pos:pos + len(faculty_profiles)]; pos += len(faculty_profiles)
    alumni_vecs = vectors[pos:pos + len(alumni_profiles)]; pos += len(alumni_profiles)
    keyword_vecs = vectors[pos:pos + len(keywords)]; pos += len(keywords)
    para_vecs = vectors[pos:pos + len(paragraphs)]; pos += len(paragraphs)

    top_matches = _build_matches(
        essay_vec, faculty_data, faculty_vecs, keyword_index, keyword_vecs,
        paragraphs, para_vecs, role_label="교수", limit=top_k,
    )
    alumni_references = _build_matches(
        essay_vec, alumni_data, alumni_vecs, keyword_index, keyword_vecs,
        paragraphs, para_vecs, role_label="동문", limit=None,
    )

    return {
        "backend": backend.name,
        "top_matches": top_matches,
        "alumni_references": alumni_references,
    }


def format_report(report):
    lines = [f"[matcher] embedding backend: {report['backend']}", ""]
    lines.append("## 교수진 매칭 Top " + str(len(report["top_matches"])))
    for match in report["top_matches"]:
        lines.append(f"#{match['rank']} {match['name']} - 매칭 점수 {match['match_score']}")
        if match["recommended_keywords"]:
            lines.append("  추천 키워드: " + ", ".join(match["recommended_keywords"]))
        lines.append("  가이드: " + match["guide_feedback"])
        lines.append("")

    if report["alumni_references"]:
        lines.append("## 참고: 한국인 DoVA 동문 매칭")
        for match in report["alumni_references"]:
            lines.append(f"- {match['name']} - 매칭 점수 {match['match_score']}")
            if match["recommended_keywords"]:
                lines.append("  참고 키워드: " + ", ".join(match["recommended_keywords"]))
            lines.append("  가이드: " + match["guide_feedback"])
            lines.append("")

    return "\n".join(lines)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("essay_file", help="SOP 에세이 텍스트 파일 경로")
    parser.add_argument(
        "--backend", default="auto",
        choices=["auto", "sentence-transformers", "openai", "tfidf"],
        help="임베딩 백엔드 (기본: auto = sentence-transformers -> tfidf fallback; "
             "openai는 에세이 전문을 외부 API로 전송하므로 명시적으로만 선택됩니다)",
    )
    parser.add_argument("--model", default=None, help="백엔드별 임베딩 모델 이름 오버라이드")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    args = parser.parse_args()

    essay_text = Path(args.essay_file).read_text(encoding="utf-8")
    report = analyze_essay(
        essay_text, backend_name=args.backend, model=args.model, top_k=args.top_k
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))


if __name__ == "__main__":
    main()
