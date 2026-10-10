"""Fast tests that need no database, network or models:  python -m pytest"""
import pytest

from app.pipeline import is_latin, script_language
from tools.docstore import chunk_pages, kind_for
from tools.leads import normalize_phone
from tools.sql_tool import query_academy_db
from tools.tts_groq import MAX_CHARS, _pieces


@pytest.mark.parametrize("raw, expected", [
    ("98765 43210", "9876543210"),
    ("+91 98765-43210", "+919876543210"),
    ("12345", None),
    ("", None),
    ("call me", None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("text", [
    "Short one.",
    "A" * 450,
    ("This is a sentence. " * 30).strip(),
    "word " * 100,
])
def test_tts_pieces_fit_and_keep_all_text(text):
    pieces = _pieces(text)
    assert all(0 < len(p) <= MAX_CHARS for p in pieces)
    assert "".join(text.split()) == "".join("".join(pieces).split())


def test_language_detection():
    assert script_language("What are the fees?") is None
    assert script_language("पायथन कोर्स की फीस") == "Hindi"
    assert script_language("પાયથન કોર્સની ફી") == "Gujarati"
    assert is_latin("Café fees are ₹8,000!")
    assert not is_latin("नमस्ते")


@pytest.mark.parametrize("sql", [
    "SELECT * FROM leads",
    "SELECT message FROM chat_history",
    'SELECT * FROM public."LEADS"',
    "SELECT query_to_xml('select * from le' || 'ads', true, true, '')",
    "SELECT * FROM pg_roles",
    "DELETE FROM courses",
    "SELECT 1; DROP TABLE courses",
])
def test_sql_tool_rejects_unsafe_queries_before_touching_the_db(sql):
    assert query_academy_db.invoke({"sql": sql}).startswith("Error:")


def test_document_kinds_and_chunking():
    assert kind_for("notice.PDF") == "pdf"
    assert kind_for("photo.jpeg") == "image"
    assert kind_for("readme.md") == "text"
    assert kind_for("virus.exe") is None
    chunks = chunk_pages([(1, "word " * 400), (2, "   "), (3, "Short page.")])
    assert {page for page, _ in chunks} == {1, 3}
    assert all(len(c) <= 800 for _, c in chunks)


def test_agent_messages_carry_memory_image_and_language():
    from tools.agent import build_messages
    history = [{"role": "user", "message": "hi", "image_note": None},
               {"role": "assistant", "message": "Hello!", "image_note": None}]
    msgs = build_messages(history, "फीस?", image_note="a fee receipt", language="Hindi")
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert "[Image the user attached: a fee receipt]" in msgs[-1]["content"]
    assert msgs[-1]["content"].endswith("(Reply in Hindi.)")
    assert "Reply in" not in build_messages([], "fees?", language="English")[-1]["content"]
