import ast
import re


def _call_count(source: str, func_name: str) -> int:
    tree = ast.parse(source)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
            if name == func_name:
                count += 1
    return count


def test_render_auto_fix_recommendations_called_exactly_once():
    with open("app/ui/streamlit_app.py", "r", encoding="utf-8") as fh:
        source = fh.read()
    assert _call_count(source, "render_auto_fix_recommendations") == 1


def test_only_one_auto_fix_panel_title_present():
    with open("app/ui/streamlit_app.py", "r", encoding="utf-8") as fh:
        source = fh.read()
    assert len(re.findall(r'panel_open\(\s*"Auto-Fix Suggestions"', source)) == 1
    assert "Auto-Fix\"" not in source  # old duplicate tab label removed
