"""Verify Sprint 3 runtime deps import cleanly."""

def test_streamlit_importable():
    import streamlit  # noqa: F401


def test_plotly_importable():
    import plotly.express  # noqa: F401


def test_jinja2_importable():
    from jinja2 import Template
    assert Template("hello {{ name }}").render(name="world") == "hello world"
