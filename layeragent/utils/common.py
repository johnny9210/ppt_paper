"""Common utilities — paths, data loading, HTML helpers."""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(_ROOT / ".env")
except Exception:
    pass

DATA_DIR = _ROOT / "data" / "experiment_designs"
META_PATH = DATA_DIR / "meta.json"
SPECS_PATH = _ROOT / "data" / "slide_specs.jsonl"
RESULTS_DIR = _ROOT / "results" / "raw"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────
# Meta & specs loading
# ─────────────────────────────────────────

def load_active_specs() -> list[dict]:
    specs_candidates = [SPECS_PATH, _ROOT / "final_test" / "data" / "slide_specs.jsonl"]
    for p in specs_candidates:
        if p.exists():
            with p.open() as f:
                return [json.loads(line) for line in f if line.strip()]
    raise FileNotFoundError(f"slide_specs.jsonl not found in {specs_candidates}")


def load_meta() -> dict:
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


# ─────────────────────────────────────────
# HTML helpers
# ─────────────────────────────────────────

def extract_html(text: str) -> str:
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


def save_run(method: str, slide_id: str, seed: int, html: str, meta: dict | None = None,
             results_dir: Path | None = None) -> Path:
    out_dir = (results_dir or RESULTS_DIR) / method
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{slide_id}_seed{seed}.html"
    p.write_text(wrap_slide(html))
    if meta is not None:
        (out_dir / f"{slide_id}_seed{seed}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return p


def filter_content(content: dict) -> dict:
    """스크립트성 필드는 제거 (시각 재현과 무관)."""
    skip = {"speaker_script", "infographic_script"}
    return {k: v for k, v in content.items() if k not in skip}
