"""
Supabase DB 모듈 (service_role 키 사용)
"""

import os
import hashlib
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# 키 읽기 (Streamlit Cloud 또는 로컬 .env)
def _get_secret(key: str) -> str:
    # Streamlit Cloud secrets 먼저 시도
    try:
        import streamlit as st
        val = st.secrets.get(key, "")
        if val:
            return val
    except Exception:
        pass
    # 로컬 .env fallback
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv(key, "")

# Supabase 연결
supabase = None
SUPABASE_OK = False

try:
    from supabase import create_client
    _url = _get_secret("SUPABASE_URL")
    _key = _get_secret("SUPABASE_ANON_KEY") or _get_secret("SUPABASE_KEY")
    if _url and _key:
        supabase = create_client(_url, _key)
        SUPABASE_OK = True
except Exception as e:
    print(f"[Supabase 연결 실패] {e}")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_user(username: str, password: str) -> Optional[Dict]:
    if not SUPABASE_OK:
        return None
    try:
        pw_hash = _hash_password(password)
        res = supabase.table("users").select("*").eq("username", username).eq("password_hash", pw_hash).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[get_user 오류] {e}")
        return None


def create_user(username: str, password: str, role: str = "user") -> bool:
    if not SUPABASE_OK:
        return False
    try:
        supabase.table("users").insert({
            "username": username,
            "password_hash": _hash_password(password),
            "role": role
        }).execute()
        return True
    except Exception as e:
        print(f"[create_user 오류] {e}")
        return False


def get_all_users() -> List[Dict]:
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


def get_keywords(user_id: int) -> Dict[str, List[str]]:
    if not SUPABASE_OK:
        return {}
    try:
        res = supabase.table("keywords").select("*").eq("user_id", user_id).order("id").execute()
        result: Dict[str, List[str]] = {}
        for row in (res.data or []):
            result.setdefault(row["category"], []).append(row["keyword"])
        return result
    except Exception as e:
        print(f"[get_keywords 오류] {e}")
        return {}


def get_default_keywords() -> Dict[str, List[str]]:
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
    defaults = get_default_keywords()
    for cat, kws in defaults.items():
        for kw in kws:
            add_keyword(user_id, cat, kw)


def save_items(items: List[Dict], query_category: str, user_id: int = None) -> int:
    if not SUPABASE_OK or not items:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    added = 0
    for item in items:
        url = item.get("link") or item.get("url", "")
        if not url:
            continue
        try:
            q = supabase.table("items").select("id").eq("url", url)
            if user_id:
                q = q.eq("user_id", user_id)
            if q.execute().data:
                continue
            row = {
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
            }
            if user_id:
                row["user_id"] = user_id
            supabase.table("items").insert(row).execute()
            added += 1
        except Exception as e:
            print(f"  [save 오류] {e}: {url[:80]}")
    return added


def get_items(days: int = None, category: str = None,
              platform: str = None, keyword: str = None,
              user_id: int = None) -> List[Dict]:
    if not SUPABASE_OK:
        return []
    try:
        query = supabase.table("items").select("*")
        if user_id:
            query = query.eq("user_id", user_id)
        if days:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
            query = query.gte("first_seen", cutoff)
        if category:
            query = query.eq("query_category", category)
        if platform:
            query = query.eq("platform", platform)
        items = query.order("first_seen", desc=True).limit(500).execute().data or []
        if keyword:
            kl = keyword.lower()
            items = [it for it in items if kl in (it.get("title","") + it.get("description","")).lower()]
        return items
    except Exception as e:
        print(f"[get_items 오류] {e}")
        return []


def get_stats(user_id: int = None) -> Dict:
    if not SUPABASE_OK:
        return {"total": 0, "by_category": {}, "by_platform": {}, "top_queries": [], "daily_trend": []}
    try:
        q_total = supabase.table("items").select("id", count="exact")
        if user_id:
            q_total = q_total.eq("user_id", user_id)
        total = q_total.execute().count or 0

        q = supabase.table("items").select("query_category, platform, query, first_seen")
        if user_id:
            q = q.eq("user_id", user_id)
        items_all = q.execute().data or []

        by_cat, by_plat, query_count, daily = {}, {}, {}, {}
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

        return {
            "total": total,
            "by_category": by_cat,
            "by_platform": by_plat,
            "top_queries": sorted([{"query":k,"count":v} for k,v in query_count.items()], key=lambda x:x["count"], reverse=True)[:20],
            "daily_trend": sorted([{"date":k,"count":v} for k,v in daily.items()], key=lambda x:x["date"])[-30:],
        }
    except Exception as e:
        print(f"[get_stats 오류] {e}")
        return {"total": 0, "by_category": {}, "by_platform": {}, "top_queries": [], "daily_trend": []}
