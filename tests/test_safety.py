from app.safety import classify_safety


def test_immediate_self_harm_routes_to_emergency_and_crisis():
    result = classify_safety("I have a plan to end my life tonight")
    assert result.level == "immediate"
    assert result.category == "self_harm"
    assert any("911" in item for item in result.resources)
    assert any("988" in item for item in result.resources)


def test_poisoning_routes_to_poison_control():
    result = classify_safety("Someone swallowed bleach")
    assert result.level == "urgent"
    assert result.category == "poisoning"
    assert any("1-800-222-1222" in item for item in result.resources)


def test_ordinary_theology_does_not_trigger_crisis():
    result = classify_safety("What did Paul mean by dying to the old self?")
    assert result.level == "none"
