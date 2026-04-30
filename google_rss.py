"""
구글 뉴스 RSS 수집 모듈 (API 키 불필요)
"""

import time
import xml.etree.ElementTree as ET
from typing import List, Dict
import requests

RSS_BASE = "https://news.google.com/rss/search"


def _clean(text: str) -> str:
    if not text:
        return ""
    import re
    text = re.sub(r"<[^>]+>", "", text)
    for ent, rep in {"&quot;": '"', "&amp;": "&", "&lt;": "<",
                     "&gt;": ">", "&#39;": "'", "&nbsp;": " "}.items():
        text = text.replace(ent, rep)
    return text.strip()


def search(query: str, max_results: int = 30) -> List[Dict]:
    params = {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    try:
        res = requests.get(RSS_BASE, params=params, timeout=10,
                           headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        root = ET.fromstring(res.content)
    except Exception as e:
        print(f"  [구글RSS 오류] '{query}': {e}")
        return []

    items = []
    for item in root.findall(".//item")[:max_results]:
        title = _clean(item.findtext("title", ""))
        link = item.findtext("link", "")
        desc = _clean(item.findtext("description", ""))
        pub = item.findtext("pubDate", "")[:16]
        source_el = item.find("{https://news.google.com/rss}source")
        source = source_el.text if source_el is not None else ""

        items.append({
            "_platform": "google_news",
            "_query": query,
            "title": title,
            "description": desc,
            "url": link,
            "pub_date": pub,
            "blogger_name": source,
            "cafe_name": "",
            "source": "구글뉴스",
        })

    time.sleep(0.1)
    return items
