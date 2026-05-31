"""Behavioral tests for the render CLI (``python -m webdesign_rl.render``).

This is the thin entrypoint that the in-container agent-screenshot renderer
invokes *inside* the sealed verifier image: it renders a served site directory
to one PNG per page (named by the page's ``screenshot`` field) under an output
directory. Running it in-container is how the agent's reference screenshots come
from the same image + OS-level font palette as grading (issue 05). The render
itself is exercised by ``test_render.py``; here we pin the CLI contract.
"""

import json
from pathlib import Path

from PIL import Image

from webdesign_rl.render.__main__ import main

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCE_SITE = FIXTURES / "site5_reference"

PAGE_MAP = {
    "home": {"screenshot": "home.png", "expected_file": "index.html"},
    "about": {"screenshot": "about.png", "expected_file": "about.html"},
}


def test_render_cli_writes_one_png_per_page(tmp_path):
    page_map = tmp_path / "page_map.json"
    page_map.write_text(json.dumps(PAGE_MAP))
    out = tmp_path / "shots"

    code = main([
        "--site", str(REFERENCE_SITE),
        "--page-map", str(page_map),
        "--out", str(out),
        "--viewport", "1280",
    ])

    assert code == 0
    for spec in PAGE_MAP.values():
        png = out / spec["screenshot"]
        assert png.is_file()
        # A real, decodable PNG at the requested viewport width.
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert Image.open(png).width == 1280
