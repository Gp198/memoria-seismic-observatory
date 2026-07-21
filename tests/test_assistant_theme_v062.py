from pathlib import Path


def _app_source() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "app"
        / "streamlit_app.py"
    ).read_text(encoding="utf-8")


def test_sidebar_text_controls_have_explicit_light_surface_contrast():
    source = _app_source()
    assert '[data-testid="stSidebar"] textarea' in source
    assert '-webkit-text-fill-color:#102A3D!important' in source
    assert 'caret-color:#0D5578!important' in source
    assert 'background:#FFFFFF!important' in source


def test_sidebar_secondary_and_primary_buttons_have_visible_text():
    source = _app_source()
    assert '[data-testid="stBaseButton-secondary"]' in source
    assert '[data-testid="stBaseButton-primary"]' in source
    assert '-webkit-text-fill-color:#FFFFFF!important' in source


def test_portalled_select_options_are_readable():
    source = _app_source()
    assert '[data-baseweb="popover"] [role="option"]' in source
    assert '[data-baseweb="menu"] [role="option"]' in source
