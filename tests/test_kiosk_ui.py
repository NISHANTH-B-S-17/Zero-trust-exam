import pytest
import os
import sys

# Ensure backend path is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

def test_kiosk_app_js_api_base_resolution():
    app_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../kiosk/app.js'))
    with open(app_js_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check that API_BASE resolves correctly for file protocol / null origin (opening index.html directly) and standard local browser ports
    assert "currentOrigin === 'null'" in content
    assert "includes('5500')" in content
    assert "includes('3000')" in content
    assert "includes('8080')" in content
    assert "const API_BASE = (isLocal || isFileProtocol) ? 'http://127.0.0.1:8080/api/v1/student' :" in content

def test_kiosk_app_js_single_choice_no_double_render():
    app_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../kiosk/app.js'))
    with open(app_js_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Ensure static renderSingleChoice click listener calls onAnswerChange(val) without an extra renderQuestion() call inside the click listener
    single_choice_method_idx = content.find("static renderSingleChoice")
    multi_choice_method_idx = content.find("static renderMultipleChoice")
    single_choice_block = content[single_choice_method_idx:multi_choice_method_idx]

    assert "onAnswerChange(val);" in single_choice_block
    assert "renderQuestion();" not in single_choice_block

def test_kiosk_app_js_on_answer_change_renders_question():
    app_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../kiosk/app.js'))
    with open(app_js_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Ensure QuestionRenderer.render callback invokes renderQuestion() to update UI
    render_call_idx = content.find("QuestionRenderer.render(q, ansArea, currentAns, (newAnswer) => {")
    assert render_call_idx != -1
    callback_block = content[render_call_idx:render_call_idx + 300]
    assert "renderQuestion();" in callback_block
