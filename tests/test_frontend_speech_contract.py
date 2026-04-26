"""Frontend speech contract checks for Puter fallback wiring."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_frontend_loads_puter_sdk_before_speech_code():
    html = _read("frontend/templates/index.html")

    assert 'src="https://js.puter.com/v2/"' in html
    assert 'src="{{ url_for(\'static\', filename=\'speech.js\') }}"' in html
    assert 'src="{{ url_for(\'static\', filename=\'app.js\') }}"' in html


def test_speech_js_uses_native_first_then_puter_fallback():
    js = _read("frontend/static/speech.js")

    assert 'const STT_FALLBACK_ORDER = ["native", "puter"];' in js
    assert "window.puter?.ai?.speech2txt" in js
    assert "puter.speech2txt({" in js
    assert "window.puter.speech2txt" not in js


def test_app_js_uses_puter_tts_then_native_fallback_when_needed():
    js = _read("frontend/static/app.js")

    assert "window.puter?.ai?.txt2speech" in js
    assert "async function createPuterTtsHandle(text)" in js
    assert "async function createAssistantTtsHandle(text)" in js
    assert "if (ttsPlaybackSpeed === 0)" in js
    assert "const puterHandle = await createPuterTtsHandle(text);" in js
    assert "const nativeHandle = createNativeTtsHandle(text);" in js
    assert "if (ttsPlaybackSpeed !== 0)" in js
