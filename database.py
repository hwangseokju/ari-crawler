"""
SQLite 저장 · 신규 판별 모듈

URL 기준으로 중복을 제거하면서, 처음 발견된 날짜(first_seen)를 기록합니다.
실행을 반복해도 같은 기사가 중복 저장되지 않고, "언제 처음 나타났는가"
만 추적하면 됩니다.
"""

import re
import sqlite3
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent / "data" / "crawler.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------
# DB 초기화
# ---------------------------------------------------------------
def init_db():
    """테이블이 없으면 생성."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            description TEXT,
            platform TEXT,
            query TEXT,
            query_category TEXT,
            pub_date TEXT,
            blogger_name TEXT,
            cafe_name TEXT,
            first_seen TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_query ON items(query)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_first_seen ON items(first_seen)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_category ON items(query_category)")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------
# 저장
# ---------------------------------------------------------------
def save_items(items: List[Dict], query_category: str) -> int:
    """결과 리스트를 DB 에 저장 (URL 기준 중복 제거).

    Returns:
        새로 추가된 항목 수
    """
    if not items:
        return 0

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    added = 0

    for item in items:
        url = item.get("link") or item.get("originallink", "")
        if not url:
            continue

        try:
            c.execute("""
                INSERT OR IGNORE INTO items
                (url, title, description, platform, query, query_category,
                 pub_date, blogger_name, cafe_name, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url,
                _clean_html(item.get("title", "")),
                _clean_html(item.get("description", "")),
                item.get("_platform", ""),
                item.get("_query", ""),
                query_category,
                item.get("pubDate", "") or item.get("postdate", ""),
                item.get("bloggername", ""),
                item.get("cafename", ""),
                now,
            ))
            if c.rowcount > 0:
                added += 1
        except sqlite3.Error as e:
            print(f"  [DB 오류] {e}: {url}")

    conn.commit()
    conn.close()
    return added


# ---------------------------------------------------------------
# 조회
# ---------------------------------------------------------------
def get_new_items(days: int = 7) -> List[Dict]:
    """최근 N일 내에 처음 수집된 항목만 반환."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")

    c.execute("""
        SELECT * FROM items
        WHERE first_seen >= ?
        ORDER BY query_category, query, first_seen DESC
    """, (cutoff,))

    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_all_items(days: int = None, category: str = None,
                  platform: str = None, keyword: str = None) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    sql = "SELECT * FROM items WHERE 1=1"
    params = []
    if days:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        sql += " AND first_seen >= ?"
        params.append(cutoff)
    if category:
        sql += " AND query_category = ?"
        params.append(category)
    if platform:
        sql += " AND platform = ?"
        params.append(platform)
    if keyword:
        sql += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    sql += " ORDER BY first_seen DESC"
    c.execute(sql, params)
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_stats() -> Dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    stats = {}
    c.execute("SELECT COUNT(*) FROM items")
    stats["total"] = c.fetchone()[0]
    c.execute("SELECT query_category, COUNT(*) FROM items GROUP BY query_category")
    stats["by_category"] = dict(c.fetchall())
    c.execute("SELECT platform, COUNT(*) FROM items GROUP BY platform")
    stats["by_platform"] = dict(c.fetchall())
    c.execute("SELECT query, query_category, COUNT(*) as cnt FROM items GROUP BY query ORDER BY cnt DESC LIMIT 20")
    stats["top_queries"] = [{"query": r[0], "category": r[1], "count": r[2]} for r in c.fetchall()]
    c.execute("SELECT substr(first_seen,1,10) as day, COUNT(*) as cnt FROM items GROUP BY day ORDER BY day DESC LIMIT 30")
    stats["daily_trend"] = [{"date": r[0], "count": r[1]} for r in c.fetchall()]
    conn.close()
    return stats


def init_keywords_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            keyword TEXT NOT NULL,
            UNIQUE(category, keyword)
        )
    """)
    conn.commit()
    conn.close()


def get_keywords() -> Dict[str, List[str]]:
    import config
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT category, keyword FROM keywords WHERE keyword != '__placeholder__' ORDER BY category, id")
    rows = c.fetchall()
    conn.close()
    if not rows:
        for cat, kws in config.CORE_KEYWORDS.items():
            for kw in kws:
                add_keyword(cat, kw)
        return {cat: list(kws) for cat, kws in config.CORE_KEYWORDS.items()}
    result: Dict[str, List[str]] = {}
    for cat, kw in rows:
        result.setdefault(cat, []).append(kw)
    return result


def add_keyword(category: str, keyword: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO keywords (category, keyword) VALUES (?, ?)", (category, keyword))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def delete_keyword(category: str, keyword: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM keywords WHERE category=? AND keyword=?", (category, keyword))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ---------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------
_TAG_RE = re.compile(r"<[^>]+>")
_ENTITIES = {
    "&quot;": '"', "&amp;": "&", "&lt;": "<",
    "&gt;": ">", "&#39;": "'", "&nbsp;": " ",
}


def _clean_html(text: str) -> str:
    """네이버 API 응답은 <b> 태그와 HTML 엔티티가 섞여있어 제거."""
    if not text:
        return ""
    text = _TAG_RE.sub("", text)
    for ent, rep in _ENTITIES.items():
        text = text.replace(ent, rep)
    return text.strip()
