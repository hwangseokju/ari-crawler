"""
네이버 검색 API 호출 모듈

뉴스, 블로그, 카페글 검색을 네이버 오픈 API로 수행합니다.
공식 문서: https://developers.naver.com/docs/serviceapi/search/
"""

import os
import time
import requests
from typing import List, Dict
from dotenv import load_dotenv

# .env 파일에서 API 키 로드
load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
    raise RuntimeError(
        "[환경설정 오류] .env 파일에 NAVER_CLIENT_ID 와 NAVER_CLIENT_SECRET 이 없습니다.\n"
        ".env.example 파일을 .env 로 복사한 뒤, 네이버 개발자센터에서 발급받은 값을 입력하세요."
    )

# 키 값이 템플릿 상태 그대로인 경우 감지
if "여기에_발급받은" in NAVER_CLIENT_ID or "여기에_발급받은" in NAVER_CLIENT_SECRET:
    raise RuntimeError(
        "[환경설정 오류] .env 파일의 값이 아직 교체되지 않았습니다.\n"
        "네이버 개발자센터에서 발급받은 Client ID / Secret 으로 교체해주세요."
    )

API_BASE = "https://openapi.naver.com/v1/search"
HEADERS = {
    "X-Naver-Client-Id": NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
}

# 플랫폼 코드 → API 엔드포인트 매핑
PLATFORM_ENDPOINTS = {
    "news": "/news.json",
    "blog": "/blog.json",
    "cafearticle": "/cafearticle.json",
}


def search(query: str, platform: str, display: int = 30,
           start: int = 1, sort: str = "date") -> Dict:
    """네이버 검색 API 1회 호출.

    Args:
        query: 검색어
        platform: "news", "blog", "cafearticle" 중 하나
        display: 가져올 결과 수 (최대 100)
        start: 시작 인덱스 (1~1000)
        sort: "date"(날짜순) 또는 "sim"(정확도순)

    Returns:
        API 응답 JSON (dict). 오류 시 {"items": []}.
    """
    if platform not in PLATFORM_ENDPOINTS:
        print(f"[오류] 지원하지 않는 플랫폼: {platform}")
        return {"items": []}

    url = API_BASE + PLATFORM_ENDPOINTS[platform]
    params = {
        "query": query,
        "display": min(display, 100),
        "start": start,
        "sort": sort,
    }

    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.HTTPError:
        # 429 = 쿼터 초과, 401 = 인증 오류
        print(f"  [오류] {platform} / '{query}': HTTP {res.status_code} - {res.text[:200]}")
        return {"items": []}
    except requests.exceptions.RequestException as e:
        print(f"  [오류] {platform} / '{query}': {e}")
        return {"items": []}


def search_all_platforms(query: str, display: int = 30,
                         platforms: List[str] = None,
                         sort: str = "date") -> List[Dict]:
    """한 키워드를 모든 플랫폼에서 검색해서 통합 결과 반환.

    각 item 에는 플랫폼 정보와 검색어를 추가로 기록해둡니다.
    """
    if platforms is None:
        platforms = list(PLATFORM_ENDPOINTS.keys())

    results = []
    for platform in platforms:
        data = search(query, platform, display=display, sort=sort)
        for item in data.get("items", []):
            item["_platform"] = platform
            item["_query"] = query
            results.append(item)
        # 과도한 연속 호출 방지 (짧은 딜레이)
        time.sleep(0.1)

    return results
