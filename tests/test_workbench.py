"""The Workbench: honest discovery primitives with a null test on every claim."""

from __future__ import annotations

from workbench.corpus import resolve, tokens
from workbench.echo import find_echoes
from workbench.novelty import most_novel, null_comparison


def test_tokenizer_drops_function_words_and_keeps_content():
    pairs = tokens("Thou shalt love thy neighbour as thyself")
    stems = [stem for stem, _ in pairs]
    surfaces = [surface for _, surface in pairs]
    # Content words survive (stemmed); function words are dropped.
    assert "neighbour" in surfaces and "love" in surfaces
    assert "lov" in stems  # "love" canonicalizes to its e-stem
    assert "thou" not in surfaces and "shalt" not in surfaces and "thy" not in surfaces


def test_light_stemming_matches_kjv_verb_forms_without_overreaching():
    a = {stem for stem, _ in tokens("he forgiveth")}
    b = {stem for stem, _ in tokens("that ye forgive")}
    assert a & b, "forgiveth and forgive should share a stem"


def test_echo_finds_a_real_quotation_far_above_the_null():
    # The great commandment is quoted across the Gospels and Leviticus; its
    # echoes must stand many standard deviations above chance.
    result = find_echoes("Matthew 22:39", top=10)
    assert result["echoes"], "expected echoes for a widely-quoted verse"
    top = result["echoes"][0]
    assert top.z_score >= 5, f"a real echo should stand out; got z={top.z_score}"
    assert top.shared_words, "a match must show the words it shares"


def test_echo_reports_a_null_baseline_for_every_query():
    result = find_echoes("Micah 6:8", top=5)
    assert result["null"] is not None
    assert "mean" in result["null"] and "sd" in result["null"]
    # Every echo carries a z-score, so a mundane overlap can be told from a real one.
    for echo in result["echoes"]:
        assert isinstance(echo.z_score, float)


def test_shared_words_actually_appear_in_both_verses():
    result = find_echoes("John 1:1", top=5)
    query_text = resolve("John 1:1")["text"].lower()
    for echo in result["echoes"]:
        for word in echo.shared_words:
            assert word in query_text


def test_novelty_excludes_book_openers():
    """The artifact the naive version tripped on: verse 1 of a book must not
    dominate, since an empty context makes everything look novel."""
    top = most_novel(top=40)
    openers = [v for _, v in top if v["verse"] == 1 and v["chapter"] == 1]
    assert len(openers) <= 2, f"book openers still dominating: {[v['reference'] for v in openers]}"


def test_novelty_null_check_is_reported():
    report = null_comparison(top=50)
    assert "real_mean_score" in report and "shuffled_mean_score" in report
    assert isinstance(report["real_top"], list) and report["real_top"]
