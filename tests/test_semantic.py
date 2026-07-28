"""The semantic microscope.

These need the local embedding model and its cache, which are a personal-study
dependency (requirements-workbench.txt), not part of Gateway's deploy. The
tests skip cleanly where that dependency is absent, so CI stays lean.
"""

from __future__ import annotations

import pytest

pytest.importorskip("sentence_transformers")

from pathlib import Path  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "workbench" / ".cache" / "verse_embeddings.npy"
if not CACHE.exists():
    pytest.skip("embedding cache not built; run workbench.embed once", allow_module_level=True)

from workbench.semantic import bridges, neighbors, outliers  # noqa: E402


def test_neighbors_find_a_real_theological_twin():
    result = neighbors("John 3:16", top=5)
    refs = [m.reference for m in result["matches"]]
    # 1 John 4:9 -- "God sent his only begotten Son" -- is John 3:16's twin.
    assert "1 John 4:9" in refs
    assert result["matches"][0].z_score > 2


def test_bridges_share_no_significant_words():
    """A bridge is a cross-vocabulary connection by definition; if it shares
    content words it is an echo, not a bridge."""
    result = bridges("Ecclesiastes 1:9", top=8)
    for match in result["bridges"]:
        assert match.shared_words == []


def test_bridges_surface_the_ecclesiastes_recurrence_twin():
    """Ecc 1:9 and Ecc 3:15 teach the same cyclical-time doctrine in different
    words -- a genuine bridge, and the tool should rank it first."""
    result = bridges("Ecclesiastes 1:9", top=5)
    assert result["bridges"], "expected at least one bridge"
    assert result["bridges"][0].reference == "Ecclesiastes 3:15"


def test_every_semantic_result_carries_a_z_score():
    for match in neighbors("Micah 6:8", top=5)["matches"]:
        assert isinstance(match.z_score, float)


def test_outliers_are_distinctive_verses():
    rows = outliers(top=15)
    assert rows and all(0 < r["isolation"] < 1 for r in rows)
    # Ecclesiastes 12:6 (silver cord / golden bowl) is among Scripture's most
    # singular metaphor-verses; it should surface as an outlier.
    assert any("Ecclesiastes 12:6" == r["reference"] for r in rows)
