"""Scope evidence to article and clause and check verbatim support for answers."""
import re
import unicodedata
from difflib import SequenceMatcher


AMOUNT = re.compile(r"\d+(?:[.,]\d+)*")


def normalized(text):
    accents = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return " ".join("".join(c for c in accents if not unicodedata.combining(c)).split())


def requested_scope(question):
    query = normalized(question)
    article = re.search(r"\bdieu\s+(\d+)\b", query)
    clause = re.search(r"\bkhoan\s+(\d+)\b", query)
    return (int(article[1]), int(clause[1]) if clause else None) if article else None


def location(row):
    return row["source_id"], row["page"], row["metadata"]["start"]


def scope_chunks(question, ranked, corpus):
    scope = requested_scope(question)
    if not scope:
        return ranked, []
    article, clause = scope
    ordered = sorted((row for row in corpus if article in row["metadata"]["article"]), key=location)
    if clause is None:
        ranked_ids = {row["id"] for row in ranked}
        return ([row for row in ranked if article in row["metadata"]["article"]]
                + [row for row in ordered if row["id"] not in ranked_ids]), []
    # Any later chunk belongs to the same clause until the next numbered paragraph.
    # Keep the indexed chunks and their original offsets for citations.
    active = False
    scoped = []
    anchors = []
    for row in ordered:
        text = re.sub(r"\bĐiều\s+\d+\.", "", row["text"], flags=re.IGNORECASE)
        markers = [int(item) for item in re.findall(r"(?<!\S)(\d+)\.\s+(?=[A-ZÀ-ỸĐ])", text)]
        if clause in markers:
            active = True
            anchors.append(row["id"])
        if active and (not markers or clause in markers):
            scoped.append(row)
        if active and markers and markers[-1] != clause:
            active = False
    return scoped, anchors


def linked_text(selected):
    """Combine only immediately adjacent chunks from the same normalized page."""
    segments = []
    previous = None
    for row in sorted(selected, key=location):
        if (previous and location(previous)[:2] == location(row)[:2]
                and row["metadata"]["start"] == previous["metadata"]["end"] + 1):
            segments[-1] += " " + row["text"]
        else:
            segments.append(row["text"])
        previous = row
    return [normalized(text) for text in segments]


def validate_quote(question, answer, quote, selected):
    if not isinstance(quote, str) or not normalized(quote):
        return "missing_evidence_quote"
    quoted = normalized(quote)
    if not any(quoted in evidence for evidence in linked_text(selected)):
        return "quote_outside_cited_evidence"
    query = normalized(question)
    currency = r"\d[\d., ]*\s*(?:(?:nghin|ngan|trieu|ty)\s+)?(?:dong|vnd)\b"
    if re.search(r"\b(?:bao nhieu dong|bang dong|muc tien|tien thuong)\b", query) and not re.search(currency, quoted):
        return "requested_currency_not_supported"
    if not answer_amounts(answer) <= answer_amounts(quoted):
        return "quoted_values_do_not_support_answer"
    return None


def answer_amounts(answer):
    # Article numbers and the regulation number name sources, not quantities.
    statement = re.sub(r"\b(?:dieu|khoan|quy che)\s+\d+\b", "", normalized(answer))
    return {value.replace(",", ".") for value in AMOUNT.findall(statement)}


def recover_scoped_quote(question, answer, quote, selected):
    scope = requested_scope(question)
    if not scope or scope[1] is None or not answer_amounts(answer) or not isinstance(quote, str):
        return None
    # A model may add the subject to a quotation. Retain a contiguous source
    # span when it includes every quantity in the answer and at least five words.
    proposed = normalized(quote).split()
    for evidence in linked_text(selected):
        tokens = evidence.split()
        matcher = SequenceMatcher(None, proposed, tokens, autojunk=False)
        for match in sorted(matcher.get_matching_blocks(), key=lambda block: -block.size):
            if match.size < 5:
                break
            span = " ".join(tokens[match.b:match.b + match.size])
            if validate_quote(question, answer, span, selected) is None:
                return span
    return None
