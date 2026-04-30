"""
카카오 검색 API 모듈 (Daum 검색)
공식 문서: https://developers.kakao.com/docs/latest/ko/daum-search/dev-guide
"""

import os
import time
import requests
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
KAKAO_AVAILABLE = bool(KAKAO_REST_API_KEY and "여기에" not in KAKAO_REST_API_KEY)

API_BASE = "https://dapi.kakao.com/v2/search"
PLATFORM_ENDPOINTS = {
    "news": "/news",
    "blog": "/blog",
    "cafe": "/cafe",
}


def search(query: str, platform: str, size: int = 30, sort: str = "recency") -> Dict:
    if not KAKAO_AVAILABLE:
        return {"documents": []}
    if platform not in PLATFORM_ENDPOINTS:
        return {"documents": []}

    url = API_BASE + PLATFORM_ENDPOINTS[platform]
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": query, "size": min(size, 50), "sort": sort}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"  [카카오 오류] {platform} / '{query}': {e}")
        return {"documents": []}


def search_all_platforms(query: str, size: int = 30,
                         platforms: List[str] = None) -> List[Dict]:
    if not KAKAO_AVAILABLE:
        return []
    if platforms is None:
        platforms = list(PLATFORM_ENDPOINTS.keys())

    results = []
    platform_map = {"news": "카카오뉴스", "blog": "카카오블로그", "cafe": "카카오카페"}

    for platform in platforms:
        data = search(query, platform, size=size)
        for doc in data.get("documents", []):
            results.append({
                "_platform": f"kakao_{platform}",
                "_query": query,
                "title": doc.get("title", ""),
                "description": doc.get("contents", ""),
                "url": doc.get("url", ""),
                "pub_date": doc.get("datetime", "")[:10],
                "blogger_name": doc.get("blogname", "") or doc.get("cafename", ""),
                "cafe_name": doc.get("cafename", ""),
                "source": platform_map.get(platform, platform),
            })
        time.sleep(0.1)

    return results
