"""
HTML 리포트 생성 모듈

DB 에 저장된 신규 항목을 카테고리 → 키워드 → 플랫폼 순으로 묶어서
한 개의 HTML 파일로 출력합니다. 브라우저에서 바로 열립니다.
"""

from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict

REPORT_DIR = Path(__file__).parent / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>아리텍 영업·경쟁사 리포트 ({date})</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
          max-width: 1000px; margin: 0 auto; padding: 24px;
          color: #222; background: #fafafa; line-height: 1.5; }}
  h1 {{ border-bottom: 3px solid #0066cc; padding-bottom: 10px; margin-bottom: 6px; }}
  h2 {{ margin-top: 36px; padding: 10px 14px; background: #0066cc; color: white;
        border-radius: 4px; font-size: 18px; }}
  h3 {{ margin-top: 22px; color: #0066cc; border-left: 4px solid #0066cc;
        padding-left: 10px; font-size: 15px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 20px; }}
  .summary {{ background: white; border: 1px solid #ddd; padding: 14px 18px;
              border-radius: 6px; margin-bottom: 24px; }}
  .summary-item {{ display: inline-block; margin-right: 24px; font-weight: bold; font-size: 14px; }}
  .summary-item .num {{ font-size: 20px; color: #0066cc; }}
  .item {{ background: white; border: 1px solid #e0e0e0; border-radius: 6px;
           padding: 12px 16px; margin-bottom: 10px; }}
  .item-title {{ font-weight: bold; font-size: 15px; margin-bottom: 6px; }}
  .item-title a {{ color: #0066cc; text-decoration: none; }}
  .item-title a:hover {{ text-decoration: underline; }}
  .item-desc {{ color: #444; font-size: 13px; margin-bottom: 6px; }}
  .item-meta {{ color: #888; font-size: 12px; }}
  .badge {{ display: inline-block; padding: 2px 9px; border-radius: 10px;
            font-size: 11px; margin-right: 6px; font-weight: bold; }}
  .badge-news {{ background: #ffe5e5; color: #c00; }}
  .badge-blog {{ background: #e5f0ff; color: #06c; }}
  .badge-cafearticle {{ background: #e8f5e5; color: #3a3; }}
  .empty {{ color: #999; font-style: italic; padding: 10px; text-align: center; }}
  .footer {{ margin-top: 60px; text-align: center; font-size: 11px; color: #999; }}
</style>
</head>
<body>
<h1>아리텍 영업·경쟁사 크롤링 리포트</h1>
<p class="meta">생성: {timestamp} | 신규 기준: 최근 {days}일</p>

<div class="summary">
  <span class="summary-item">신규 항목 <span class="num">{total_new}</span>건</span>
  <span class="summary-item">DB 누적 <span class="num">{total_all}</span>건</span>
</div>

{body}

<p class="footer">
  ⚠ 본 리포트는 네이버 검색 API 자동 수집 결과이며, 원문 확인이 필요합니다.
</p>
</body>
</html>
"""


def render_report(new_items: List[Dict], stats: Dict, days: int = 7) -> Path:
    """신규 항목을 HTML 리포트로 렌더링.

    Returns:
        생성된 HTML 파일 경로
    """
    # 카테고리 → 키워드 → 항목 리스트
    grouped = defaultdict(lambda: defaultdict(list))
    for item in new_items:
        cat = item.get("query_category", "기타")
        query = item.get("query", "")
        grouped[cat][query].append(item)

    body_parts = []

    # 고정 카테고리 순서
    cat_order = ["경쟁사", "기술·시설", "업계·정책"]
    for cat in cat_order:
        if cat in grouped:
            body_parts.append(_render_category(cat, grouped[cat]))

    # 그 외 카테고리
    for cat, queries in grouped.items():
        if cat not in cat_order:
            body_parts.append(_render_category(cat, queries))

    if not new_items:
        body_parts.append('<p class="empty">최근 신규 항목이 없습니다.</p>')

    html = _HTML_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d"),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        days=days,
        total_new=len(new_items),
        total_all=stats.get("total", 0),
        body="\n".join(body_parts),
    )

    out_path = REPORT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------
# 내부 렌더러
# ---------------------------------------------------------------
def _render_category(cat: str, queries: Dict[str, List[Dict]]) -> str:
    total = sum(len(v) for v in queries.values())
    parts = [f'<h2>📌 {cat} ({total}건)</h2>']
    for query, items in queries.items():
        parts.append(f'<h3>{_escape(query)} ({len(items)}건)</h3>')
        for item in items:
            parts.append(_render_item(item))
    return "\n".join(parts)


def _render_item(item: Dict) -> str:
    platform = item.get("platform", "")
    platform_kr = {
        "news": "뉴스",
        "blog": "블로그",
        "cafearticle": "카페",
    }.get(platform, platform)
    source = item.get("blogger_name") or item.get("cafe_name") or ""
    pub = _format_date(item.get("pub_date") or "")

    return (
        '<div class="item">'
        f'<div class="item-title"><a href="{_escape(item.get("url", "#"))}" '
        f'target="_blank" rel="noopener noreferrer">{_escape(item.get("title", ""))}</a></div>'
        f'<div class="item-desc">{_escape(item.get("description", ""))}</div>'
        f'<div class="item-meta">'
        f'<span class="badge badge-{platform}">{platform_kr}</span>'
        f'{_escape(source)} {_escape(pub)}'
        '</div>'
        '</div>'
    )


def _escape(s: str) -> str:
    if not s:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
