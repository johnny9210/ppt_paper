"""공통 utility: src/ 메소드 호출, HTML 추출, 메타데이터 로딩."""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path
from typing import Any

# Add project root and src to path so we can `import src.methods.*`
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Ensure .env is loaded if user runs scripts directly
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(_ROOT / ".env")
except Exception:
    pass

DATA_DIR = _ROOT / "data" / "experiment_designs"
META_PATH = DATA_DIR / "meta.json"
SPECS_PATH = Path(__file__).resolve().parent.parent / "data" / "slide_specs.jsonl"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def load_active_specs() -> list[dict]:
    """Load 5 active designs from slide_specs.jsonl."""
    with SPECS_PATH.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def load_meta() -> dict:
    """Load full meta.json (all designs with content + style)."""
    with META_PATH.open() as f:
        return json.load(f)


def get_design_by_id(meta: dict, slide_id: str) -> dict:
    for s in meta["slides"]:
        if s["id"] == slide_id:
            return s
    raise KeyError(f"Design {slide_id} not found in meta.json")


def get_image_path(slide_id: str) -> Path:
    return DATA_DIR / f"{slide_id}.png"


def b64_image(slide_id: str) -> str:
    return base64.b64encode(get_image_path(slide_id).read_bytes()).decode()


def extract_html(text: str) -> str:
    """Strip code fences and prelude text."""
    text = (text or "").strip()
    if "```html" in text:
        text = text.split("```html", 1)[1].split("```")[0]
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
    start = re.search(r"<(?:style|div|!DOCTYPE)", text, re.IGNORECASE)
    if start and start.start() > 0:
        text = text[start.start():]
    return text.strip()


def wrap_slide(html_content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body>
<div style="width:1280px;height:720px;overflow:hidden;position:relative;">{html_content}</div>
</body></html>"""


def save_run(method: str, slide_id: str, seed: int, html: str, meta: dict | None = None) -> Path:
    """Save a single run output as standalone HTML file + sidecar metadata."""
    method_dir = RESULTS_DIR / method
    method_dir.mkdir(parents=True, exist_ok=True)
    html_path = method_dir / f"{slide_id}_seed{seed}.html"
    html_path.write_text(wrap_slide(html))
    if meta is not None:
        (method_dir / f"{slide_id}_seed{seed}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return html_path


def get_openai_client(seed: int | None = None):
    """Return a singleton OpenAI client. seed is logged in metadata."""
    from openai import OpenAI
    if not hasattr(get_openai_client, "_c"):
        get_openai_client._c = OpenAI()
    return get_openai_client._c
