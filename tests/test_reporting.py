import pandas as pd

from src.reporting.explanations import _markdown_table


def test_markdown_table_without_tabulate():
    frame = pd.DataFrame({"a": [1], "b": ["x|y"]})
    rendered = _markdown_table(frame)
    assert "| a | b |" in rendered
    assert r"x\|y" in rendered
