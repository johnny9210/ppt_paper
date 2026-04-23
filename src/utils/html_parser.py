"""HTML/CSS 파싱 유틸리티 — 생성된 HTML에서 시각 요소를 추출."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from bs4 import BeautifulSoup


@dataclass
class CSSProperties:
    """파싱된 CSS 속성 모음."""
    box_shadows: list[str] = field(default_factory=list)
    border_radii: list[str] = field(default_factory=list)
    gradients: list[str] = field(default_factory=list)
    opacities: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    backdrop_filters: list[str] = field(default_factory=list)
    transforms: list[str] = field(default_factory=list)
    z_indices: list[str] = field(default_factory=list)
    positions: list[str] = field(default_factory=list)
    clip_paths: list[str] = field(default_factory=list)

    @property
    def effect_count(self) -> int:
        return (len(self.box_shadows) + len(self.gradients) +
                len(self.opacities) + len(self.filters) +
                len(self.backdrop_filters) + len(self.transforms))

    @property
    def total_properties(self) -> int:
        return sum(len(getattr(self, f.name)) for f in self.__dataclass_fields__.values())


@dataclass
class IconInfo:
    """아이콘 요소 정보."""
    proper: int = 0      # FontAwesome, emoji 등 정상 렌더링
    broken: int = 0      # 깨진 img 태그 (존재하지 않는 src)
    empty: int = 0       # 빈 컨테이너 (아이콘 크기 CSS만 있고 내용 없음)

    @property
    def total(self) -> int:
        return self.proper + self.broken + self.empty

    @property
    def integrity_rate(self) -> float:
        return self.proper / self.total if self.total > 0 else 1.0


def extract_all_css(html: str) -> str:
    """HTML에서 모든 CSS를 추출 (style 태그 + 인라인 style 속성)."""
    css_parts = []

    # <style> 태그 내용
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)
    css_parts.extend(style_blocks)

    # 인라인 style 속성
    inline_styles = re.findall(r'style="([^"]*)"', html)
    css_parts.extend(inline_styles)

    return "\n".join(css_parts)


def parse_css_properties(html: str) -> CSSProperties:
    """HTML에서 모든 CSS 속성을 파싱."""
    css = extract_all_css(html)

    return CSSProperties(
        box_shadows=re.findall(r'box-shadow:\s*([^;]+)', css),
        border_radii=re.findall(r'border-radius:\s*([^;]+)', css),
        gradients=re.findall(r'(?:linear|radial)-gradient\([^)]+\)', css),
        opacities=[m for m in re.findall(r'opacity:\s*([\d.]+)', css) if float(m) < 1.0],
        filters=re.findall(r'(?<!backdrop-)filter:\s*([^;]+)', css),
        backdrop_filters=re.findall(r'backdrop-filter:\s*([^;]+)', css),
        transforms=re.findall(r'transform:\s*([^;]+)', css),
        z_indices=re.findall(r'z-index:\s*(\d+)', css),
        positions=[p for p in re.findall(r'position:\s*(absolute|relative|fixed)', css)],
        clip_paths=re.findall(r'clip-path:\s*([^;]+)', css),
    )


def parse_icons(html: str) -> IconInfo:
    """HTML에서 아이콘 요소를 분석."""
    soup = BeautifulSoup(html, 'html.parser')
    info = IconInfo()

    # FontAwesome 아이콘 (정상)
    fa_icons = soup.find_all('i', class_=re.compile(r'fa[srlbd]?\s+fa-'))
    info.proper += len(fa_icons)

    # 이모지 (정상) — 텍스트 안의 이모지 카운트
    emoji_pattern = re.compile(
        "[\U0001F300-\U0001F9FF\U00002702-\U000027B0\U0000FE00-\U0000FE0F"
        "\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF"
        "\U0000200D\U00002640\U00002642]+", re.UNICODE
    )
    emoji_matches = emoji_pattern.findall(html)
    info.proper += len(emoji_matches)

    # img 태그 분석
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if not src or src.startswith('data:') or src.startswith('http'):
            # data URI 또는 외부 URL은 의도적일 수 있음
            if src:
                info.proper += 1
            else:
                info.broken += 1
        else:
            # 로컬 파일 참조 (대부분 존재하지 않는 파일)
            info.broken += 1

    # 빈 아이콘 컨테이너 탐지
    # border-radius: 50% + 고정 크기 + 내용 없음 = 빈 아이콘 배지
    for div in soup.find_all(['div', 'span']):
        style = div.get('style', '')
        if ('border-radius' in style and '50%' in style and
                not div.get_text(strip=True) and
                not div.find('i') and not div.find('img')):
            # 크기가 아이콘 수준 (20-80px)인지 확인
            size_match = re.search(r'(?:width|height):\s*(\d+)', style)
            if size_match and 20 <= int(size_match.group(1)) <= 80:
                info.empty += 1

    return info


def extract_colors(html: str) -> list[str]:
    """HTML/CSS에서 사용된 모든 색상 추출."""
    css = extract_all_css(html)
    colors = set()

    # hex 색상
    colors.update(re.findall(r'#[0-9a-fA-F]{3,8}', css))
    # rgb/rgba
    colors.update(re.findall(r'rgba?\([^)]+\)', css))
    # named colors (주요 것만)
    for name in ['white', 'black', 'red', 'blue', 'green', 'gray', 'transparent']:
        if name in css.lower():
            colors.add(name)

    return list(colors)


def load_html(path: str | Path) -> str:
    """HTML 파일 로드."""
    return Path(path).read_text(encoding='utf-8')
