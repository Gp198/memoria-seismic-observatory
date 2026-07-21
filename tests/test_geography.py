from src.geography.tectonic_domains import classify_point


def test_sw_margin_point():
    domain, confidence = classify_point(36.5, -10.0)
    assert domain == "Margem Sudoeste Ibérica"
    assert confidence >= 0.8


def test_lower_tagus_point():
    domain, confidence = classify_point(38.9, -9.0)
    assert domain == "Vale Inferior do Tejo"
    assert confidence >= 0.8
