from app.analysis.retrieval import extract_references


def test_extracts_numbered_book_and_range():
    assert extract_references("Read 1 Corinthians 13:4-5 and James 1:19") == [
        "1 Corinthians 13:4",
        "1 Corinthians 13:5",
        "James 1:19",
    ]


def test_normalizes_psalm():
    assert extract_references("Psalm 23:1") == ["Psalms 23:1"]
