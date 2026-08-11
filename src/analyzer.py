"""Enriches data/faculty_data.json (and data/alumni_data.json, if present) with
artwork_images, philosophy, visual_languages, and key_exhibitions, extracted
from each person's bio text. Same extraction pipeline for faculty and Korean
DoVA/DoVA-affiliated alumni records — the alumni file just has a "type": "alumni"
marker and an extra "current_activity_ko" field that analysis leaves untouched.

Keyword extraction uses spaCy (noun-chunk parsing) when the `spacy` package and an
English model are installed, and falls back to a pure-regex/vocabulary matcher
otherwise (see `_HAS_SPACY` below) — the same extraction logic and output shape
apply either way, so this module runs with or without spaCy installed.

The output is a *research aid*, not a finished write-up: `philosophy` and
`key_exhibitions` are heuristically selected from bio text and are meant to be
reviewed/edited by hand, not quoted verbatim in an application essay.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FACULTY_DATA_FILE = "faculty_data.json"
ALUMNI_DATA_FILE = "alumni_data.json"

try:
    import spacy

    try:
        _NLP = spacy.load("en_core_web_sm")
    except OSError:
        _NLP = None
except ImportError:
    _NLP = None

_HAS_SPACY = _NLP is not None


# Curated vocabulary of media / technique / discourse terms common in contemporary
# art practice and criticism. Matched case-insensitively as whole phrases against
# each bio; hits are ranked by frequency, then by first appearance in the text.
VISUAL_LANGUAGE_VOCAB = [
    # media
    "photography", "photographic", "sculpture", "ceramics", "video", "installation",
    "performance", "painting", "drawing", "printmaking", "collage", "assemblage",
    "mixed media", "stage set", "video installation", "software", "artist book",
    "monograph", "text-based", "sound", "metal", "works on paper", "film", "theater",
    "choreography", "database art", "generative", "algorithmic",
    # technique / formal vocabulary
    "found object", "found material", "appropriation", "re-enactment", "gestural",
    "self-portraiture", "still life", "portraiture", "montage", "archive",
    "ensemble", "improvisation", "site-specific",
    # concept / discourse
    "conceptual art", "minimalism", "post-minimalism", "social practice",
    "social sculpture", "civic discourse", "power relations", "embodiment",
    "temporality", "queer", "black studies", "intersectionality", "postcolonial",
    "biennial", "biennale", "triennial", "critical fabulation", "insurgent architecture",
    "prison culture", "cultural experience", "popular culture", "pattern",
    "knowledge production", "labor", "immigration", "internationalism",
    "fiber art", "hanbok", "postcolonial feminism", "immigrant experience",
    "motherhood", "national archive", "maintenance art", "operational labor",
    "art preparator",
]

# Sentences containing these cue phrases are treated as statements of artistic
# philosophy / research stance rather than plain biography or exhibition listing.
PHILOSOPHY_CUES = [
    "practice takes up", "practice", "explores", "examines", "interrogate",
    "investigate", "attends to", "questions about", "concerned with",
    "focus on", "focuses on", "seeks to", "meditation on", "engage",
    "engages", "reflecting", "metaphors for", "posit", "posits", "proposition",
    "research investigates", "generates and reconfigures", "coping with",
    "regularly incorporates", "true medium",
]

# Words/phrases whose presence marks a sentence as an exhibition/venue listing
# rather than a philosophy statement, so they don't get double-counted.
_EXHIBITION_NOISE = re.compile(
    r"\b(BFA|MFA|B\.A\.|M\.A\.|Ph\.D\.|awarded|fellowship|graduated)\b", re.IGNORECASE
)

_VENUE_BASE = (
    r"Museum|Gallery|Galerie|Biennial|Biennale|Triennial|Kunstverein|Institute|"
    r"Center|Foundation|Festival|Armory|Whitney|MoMA PS1|Tate Modern"
)
_CAP_WORD = r"[A-Z][\w'\-]*"
# A run of capitalized words (proper-noun prefix), the institution-type noun,
# then an optional "of/for <Proper Noun phrase>" suffix. Restricting every
# word to start with a capital letter keeps this from swallowing lowercase
# connective clauses (e.g. "... and a BA from Smith College").
_VENUE_RE = re.compile(
    r"(?:" + _CAP_WORD + r"\s+){0,4}(?:" + _VENUE_BASE + r")"
    r"(?:\s+(?:of|for)\s+" + _CAP_WORD + r"(?:\s+" + _CAP_WORD + r"){0,3})?"
)


def _split_sentences(text):
    """Split bio text into sentences, preferring spaCy's sentencizer when available."""
    if not text:
        return []
    if _HAS_SPACY:
        return [s.text.strip() for s in _NLP(text).sents if s.text.strip()]
    # Fallback: split on '.', '!', '?' followed by whitespace + capital letter,
    # while tolerating common abbreviations that shouldn't end a sentence.
    text = re.sub(r"\b(Mr|Mrs|Ms|Dr|St|vs|e\.g|i\.e)\.\s", r"\1<DOT> ", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]


def extract_visual_languages(bio, top_n=10):
    """Return the top ranked visual/conceptual language keywords found in `bio`."""
    if not bio:
        return []
    text_lower = bio.lower()
    hits = []
    for term in VISUAL_LANGUAGE_VOCAB:
        count = text_lower.count(term.lower())
        if count > 0:
            hits.append((term, count, text_lower.find(term.lower())))

    if _HAS_SPACY:
        # Supplement with frequent multi-word noun chunks (2-3 tokens, no pronouns/stopwords)
        # to surface medium/technique phrases not in the curated vocabulary.
        doc = _NLP(bio)
        seen = {t for t, _, _ in hits}
        chunk_counts = {}
        for chunk in doc.noun_chunks:
            words = [t for t in chunk if not t.is_stop and not t.is_punct]
            if not (2 <= len(words) <= 3):
                continue
            phrase = " ".join(t.lemma_.lower() for t in words)
            if phrase in seen:
                continue
            chunk_counts[phrase] = chunk_counts.get(phrase, 0) + 1
        for phrase, count in chunk_counts.items():
            if count > 1:  # require repetition to filter out one-off noise
                hits.append((phrase, count, text_lower.find(phrase.split()[0])))

    hits.sort(key=lambda h: (-h[1], h[2]))
    return [term for term, _, _ in hits[:top_n]]


def extract_philosophy(bio, max_sentences=2):
    """Pick the sentence(s) most likely to state the professor's artistic philosophy."""
    sentences = _split_sentences(bio)
    scored = []
    for sent in sentences:
        if _EXHIBITION_NOISE.search(sent):
            continue
        score = sum(1 for cue in PHILOSOPHY_CUES if cue in sent.lower())
        if score > 0:
            scored.append((score, sent))

    if not scored:
        return sentences[0] if sentences else ""

    scored.sort(key=lambda s: -s[0])
    best = [sent for _, sent in scored[:max_sentences]]
    # keep original sentence order for readability
    best.sort(key=lambda s: sentences.index(s))
    return " ".join(best)


def extract_key_exhibitions(bio, events=None, max_items=8):
    """Combine structured event records with venue names heuristically found in the bio."""
    items = []
    for ev in events or []:
        title = ev.get("title", "").strip()
        if not title:
            continue
        date = ev.get("date", "").strip()
        items.append(f"{title} ({date})" if date else title)

    for match in _VENUE_RE.finditer(bio or ""):
        venue = match.group(0).strip(" ,.;")
        if venue and venue not in items and len(venue) < 80:
            items.append(venue)

    # dedupe while preserving order
    seen = set()
    deduped = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:max_items]


def build_artwork_images(record):
    """Seed artwork_images from the scraped header/portrait image.

    This is a starting point, not a full gallery: DoVA profile pages only expose
    one representative image each, so additional artwork photos (from a
    professor's homepage or gallery site) should be added here by hand as
    `data/artwork_image_overrides.json` grows.
    """
    images = []
    if record.get("image"):
        images.append(record["image"])
    return images


def analyze_faculty(record):
    """Return a copy of `record` extended with the four DoVA-analysis fields."""
    bio = record.get("bio", "")
    enriched = dict(record)
    enriched["artwork_images"] = build_artwork_images(record)
    enriched["philosophy"] = extract_philosophy(bio)
    enriched["visual_languages"] = extract_visual_languages(bio)
    enriched["key_exhibitions"] = extract_key_exhibitions(bio, record.get("events"))
    return enriched


def load_faculty_data(filename=FACULTY_DATA_FILE):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def save_faculty_data(faculty_data, filename=FACULTY_DATA_FILE):
    output_path = DATA_DIR / filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(faculty_data, f, ensure_ascii=False, indent=2)
    return output_path


def _analyze_file(filename, label):
    records = load_faculty_data(filename)
    enriched = [analyze_faculty(record) for record in records]
    saved_path = save_faculty_data(enriched, filename)
    print(f"Analyzed {len(enriched)} {label} records; saved to {saved_path}")


def main():
    engine = "spaCy" if _HAS_SPACY else "vocabulary fallback (spaCy/model not installed)"
    print(f"[analyzer] extraction engine: {engine}")
    _analyze_file(FACULTY_DATA_FILE, "faculty")
    if (DATA_DIR / ALUMNI_DATA_FILE).exists():
        _analyze_file(ALUMNI_DATA_FILE, "alumni")


if __name__ == "__main__":
    main()
