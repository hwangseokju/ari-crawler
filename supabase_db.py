"""
Supabase DB 모듈
SQLite 대신 Supabase(PostgreSQL)를 사용합니다.
"""

import os
import hashlib
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def _get_secret(key: str) -> str:
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, ""))
    except Exception:
        return os.getenv(key, "")

SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_ANON_KEY")

try:
    from supabase import create_client, Client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    SUPABASE_OK = supabase is not None
except Exception as e:
    supabase = None
    SUPABASE_OK = False
    print(f"[Supabase 연결 실패] {e}")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ── 사용자 관리 ──────────────────────────────────────────────

def get_user(username: str, password: str) -> Optional[Dict]:
    """로그인 검증. 성공 시 user dict 반환, 실패 시 None."""
    if not SUPABASE_OK:
        return None
    try:
        pw_hash = _hash_password(password)
        res = supabase.table("users").select("*").eq("username", username).eq("password_hash", pw_hash).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        print(f"[get_user 오류] {e}")
        return None


def create_user(username: str, password: str, role: str = "user") -> bool:
    """신규 사용자 생성."""
    if not SUPABASE_OK:
        return False
    try:
        pw_hash = _hash_password(password)
        supabase.table("users").insert({
            "username": username,
            "password_hash": pw_hash,
            "role": role
        }).execute()
        return True
    except Exception as e:
        print(f"[create_user 오류] {e}")
        return False


def get_all_users() -> List[Dict]:
    """전체 사용자 목록 (admin용)."""
    if not SUPABASE_OK:
        return []
    try:
        res = supabase.table("users").select("id, username, role, created_at").execute()
        return res.data or []
    except Exception as e:
        print(f"[get_all_users 오류] {e}")
        return []


def delete_user(user_id: int) -> bool:
    if not SUPABASE_OK:
        return False
    try:
        supabase.table("users").delete().eq("id", user_id).execute()
        return True
    except Exception as e:
        print(f"[delete_user 오류] {e}")
        return False


# ── 키워드 관리 (사용자별) ────────────────────────────────────

def get_keywords(user_id: int) -> Dict[str, List[str]]:
    """사용자별 키워드 반환."""
    if not SUPABASE_OK:
        return {}
    try:
        res = supabase.table("keywords").select("*").eq("user_id", user_id).order("id").execute()
        result: Dict[str, List[str]] = {}
        for row in (res.data or []):
            cat = row["category"]
            kw = row["keyword"]
            result.setdefault(cat, []).append(kw)
        return result
    except Exception as e:
        print(f"[get_keywords 오류] {e}")
        return {}


def get_default_keywords() -> Dict[str, List[str]]:
    """기본 키워드 (로그인 전 또는 비어있을 때)."""
    import config
    return {cat: list(kws) for cat, kws in config.CORE_KEYWORDS.items()}


def add_keyword(user_id: int, category: str, keyword: str) -> bool:
    if not SUPABASE_OK:
        return False
    try:
        supabase.table("keywords").insert({
            "user_id": user_id,
            "category": category,
            "keyword": keyword
        }).execute()
        return True
    except Exception as e:
        print(f"[add_keyword 오류] {e}")
        return False


def delete_keyword(user_id: int, category: str, keyword: str) -> bool:
    if not SUPABASE_OK:
        return False
    try:
        supabase.table("keywords").delete()\
            .eq("user_id", user_id)\
            .eq("category", category)\
            .eq("keyword", keyword).execute()
        return True
    except Exception as e:
        print(f"[delete_keyword 오류] {e}")
        return False


def copy_default_keywords_to_user(user_id: int):
    """신규 사용자에게 기본 키워드 복사."""
    defaults = get_default_keywords()
    for cat, kws in defaults.items():
        for kw in kws:
            add_keyword(user_id, cat, kw)


# ── 수집 결과 저장 ────────────────────────────────────────────

def save_items(items: List[Dict], query_category: str) -> int:
    """수집 결과 저장 (URL 기준 중복 제거)."""
    if not SUPABASE_OK or not items:
        return 0

    now = datetime.now().isoformat(timespec="seconds")
    added = 0

    for item in items:
        url = item.get("link") or item.get("url", "")
        if not url:
            continue
        try:
            # URL 중복 확인
            existing = supabase.table("items").select("id").eq("url", url).execute()
            if existing.data:
                continue

            supabase.table("items").insert({
                "url": url,
                "title": item.get("title", "")[:500],
                "description": item.get("description", "")[:1000],
                "platform": item.get("_platform", ""),
                "query": item.get("_query", ""),
                "query_category": query_category,
                "pub_date": (item.get("pubDate") or item.get("pub_date") or "")[:50],
                "blogger_name": (item.get("bloggername") or item.get("blogger_name") or "")[:200],
                "cafe_name": (item.get("cafename") or item.get("cafe_name") or "")[:200],
                "first_seen": now,
            }).execute()
            added += 1
        except Exception as e:
            print(f"  [save 오류] {e}: {url[:80]}")

    return added


def get_items(days: int = None, category: str = None,
              platform: str = None, keyword: str = None) -> List[Dict]:
    """수집 결과 조회."""
    if not SUPABASE_OK:
        return []
    try:
        query = supabase.table("items").select("*")

        if days:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
            query = query.gte("first_seen", cutoff)
        if category:
            query = query.eq("query_category", category)
        if platform:
            query = query.eq("platform", platform)

        query = query.order("first_seen", desc=True).limit(500)
        res = query.execute()
        items = res.data or []

        # 키워드 필터는 클라이언트 사이드
        if keyword:
            kw_lower = keyword.lower()
            items = [it for it in items
                     if kw_lower in (it.get("title", "") + it.get("description", "")).lower()]
        return items
    except Exception as e:
        print(f"[get_items 오류] {e}")
        return []


def get_stats() -> Dict:
    """통계 데이터."""
    if not SUPABASE_OK:
        return {"total": 0, "by_category": {}, "by_platform": {}, "top_queries": [], "daily_trend": []}
    try:
        # 전체 수
        total_res = supabase.table("items").select("id", count="exact").execute()
        total = total_res.count or 0

        # 카테고리별
        items_all = supabase.table("items").select("query_category, platform, query, first_seen").execute().data or []

        by_cat = {}
        by_plat = {}
        query_count = {}
        daily = {}

        for it in items_all:
            cat = it.get("query_category", "기타")
            plat = it.get("platform", "")
            qry = it.get("query", "")
            date = (it.get("first_seen") or "")[:10]

            by_cat[cat] = by_cat.get(cat, 0) + 1
            by_plat[plat] = by_plat.get(plat, 0) + 1
            query_count[qry] = query_count.get(qry, 0) + 1
            if date:
                daily[date] = daily.get(date, 0) + 1

        top_queries = sorted(
            [{"query": k, "count": v} for k, v in query_count.items()],
            key=lambda x: x["count"], reverse=True
        )[:20]

        daily_trend = sorted(
            [{"date": k, "count": v} for k, v in daily.items()],
            key=lambda x: x["date"]
        )[-30:]

        return {
            "total": total,
            "by_category": by_cat,
            "by_platform": by_plat,
            "top_queries": top_queries,
            "daily_trend": daily_trend,
        }
    except Exception as e:
        print(f"[get_stats 오류] {e}")
        return {"total": 0, "by_category": {}, "by_platform": {}, "top_queries": [], "daily_trend": []}
