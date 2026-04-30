"""
아리텍 영업·경쟁사 크롤링 대시보드

실행:  streamlit run dashboard.py
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── 경로 설정 ────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import database
import config as cfg

# 카카오·구글은 선택적 import (키 없어도 동작)
try:
    import kakao_api
    KAKAO_OK = kakao_api.KAKAO_AVAILABLE
except Exception:
    KAKAO_OK = False

try:
    import google_rss
    GOOGLE_OK = True
except Exception:
    GOOGLE_OK = False

try:
    import naver_api
    NAVER_OK = True
except RuntimeError:
    NAVER_OK = False

# ── 환경변수 ─────────────────────────────────────────────────
DASHBOARD_PW = os.getenv("DASHBOARD_PASSWORD", "aritech2024")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── 페이지 기본 설정 ──────────────────────────────────────────
st.set_page_config(
    page_title="아리텍 크롤링 대시보드",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
  .main .block-container { padding-top: 1.5rem; }
  .metric-card { background:#f0f4ff; border-radius:10px;
                 padding:14px 20px; text-align:center; }
  .metric-num  { font-size:2rem; font-weight:700; color:#0066cc; }
  .metric-lbl  { font-size:0.85rem; color:#555; }
  .badge { display:inline-block; padding:2px 10px; border-radius:12px;
           font-size:11px; font-weight:600; margin-right:4px; }
  .badge-news         { background:#ffe5e5; color:#c00; }
  .badge-blog         { background:#e5f0ff; color:#06c; }
  .badge-cafearticle  { background:#e8f5e5; color:#2a7; }
  .badge-kakao_news   { background:#fff3cd; color:#856404; }
  .badge-kakao_blog   { background:#fde8ff; color:#6f42c1; }
  .badge-kakao_cafe   { background:#e8fff3; color:#1a7a4a; }
  .badge-google_news  { background:#fce8e6; color:#d93025; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# 비밀번호 로그인
# ════════════════════════════════════════════════════════════
def check_login():
    if st.session_state.get("logged_in"):
        return True

    st.markdown("## 🔐 아리텍 크롤링 대시보드")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        pw = st.text_input("비밀번호를 입력하세요", type="password", key="pw_input")
        if st.button("로그인", use_container_width=True):
            if pw == DASHBOARD_PW:
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    return False


# ════════════════════════════════════════════════════════════
# 수집 실행
# ════════════════════════════════════════════════════════════
def run_crawler(progress_bar, status_text):
    database.init_db()
    database.init_keywords_table()
    keywords = database.get_keywords()

    all_kw = [(cat, kw) for cat, kws in keywords.items() for kw in kws]
    total = len(all_kw)
    added_total = 0

    for i, (cat, kw) in enumerate(all_kw):
        status_text.text(f"수집 중... [{i+1}/{total}] '{kw}'")
        progress_bar.progress((i + 1) / total)

        items = []

        # 네이버
        if NAVER_OK:
            try:
                items += naver_api.search_all_platforms(
                    kw, display=cfg.DISPLAY_PER_KEYWORD,
                    platforms=cfg.PLATFORMS, sort=cfg.SORT_ORDER)
            except Exception as e:
                st.warning(f"네이버 오류: {e}")

        # 카카오
        if KAKAO_OK:
            try:
                items += kakao_api.search_all_platforms(kw, size=30)
            except Exception as e:
                st.warning(f"카카오 오류: {e}")

        # 구글 RSS
        if GOOGLE_OK:
            try:
                items += google_rss.search(kw, max_results=20)
            except Exception as e:
                st.warning(f"구글 오류: {e}")

        # 카카오·구글 items는 url 필드가 다름 — 정규화
        for it in items:
            if "url" in it and "link" not in it:
                it["link"] = it["url"]

        added = database.save_items(items, query_category=cat)
        added_total += added

    status_text.text(f"✅ 완료! 신규 {added_total}건 저장")
    return added_total


# ════════════════════════════════════════════════════════════
# AI 요약
# ════════════════════════════════════════════════════════════
def ai_summarize(items: list) -> str:
    if not ANTHROPIC_KEY:
        return "ANTHROPIC_API_KEY 가 .env 에 없습니다. AI 요약을 사용하려면 키를 추가해주세요."
    if not items:
        return "요약할 항목이 없습니다."

    try:
        import requests as req
        sample = items[:40]
        text_lines = []
        for it in sample:
            text_lines.append(f"[{it.get('query_category','')} / {it.get('query','')}] "
                              f"{it.get('title','')} — {it.get('description','')[:80]}")
        combined = "\n".join(text_lines)

        prompt = f"""다음은 음식물쓰레기 처리 업계 크롤링 결과입니다.
아리텍바이오(ARIUM 시스템 제조사) 영업팀 관점에서 핵심만 3~5줄로 요약해주세요.
경쟁사 동향, 업계 이슈, 영업 기회 중심으로.

{combined}"""

        res = req.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001",
                  "max_tokens": 500,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        res.raise_for_status()
        return res.json()["content"][0]["text"]
    except Exception as e:
        return f"AI 요약 오류: {e}"


# ════════════════════════════════════════════════════════════
# 플랫폼 배지
# ════════════════════════════════════════════════════════════
PLATFORM_KR = {
    "news": "네이버뉴스", "blog": "네이버블로그", "cafearticle": "네이버카페",
    "kakao_news": "카카오뉴스", "kakao_blog": "카카오블로그", "kakao_cafe": "카카오카페",
    "google_news": "구글뉴스",
}


def badge(platform: str) -> str:
    label = PLATFORM_KR.get(platform, platform)
    cls = f"badge-{platform}" if platform in PLATFORM_KR else "badge"
    return f'<span class="badge {cls}">{label}</span>'


# ════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════
def main():
    if not check_login():
        return

    database.init_db()
    database.init_keywords_table()

    # ── 사이드바 ──────────────────────────────────────────
    with st.sidebar:
        st.image("https://via.placeholder.com/200x60/0066cc/white?text=ARITECH+BIO",
                 use_column_width=True)
        st.markdown("---")

        # 수집 상태 표시
        st.markdown("**플랫폼 연결 상태**")
        st.markdown(f"{'🟢' if NAVER_OK else '🔴'} 네이버")
        st.markdown(f"{'🟢' if KAKAO_OK else '🔴'} 카카오 {'*(키 없음)*' if not KAKAO_OK else ''}")
        st.markdown(f"{'🟢' if GOOGLE_OK else '🔴'} 구글 RSS")
        st.markdown("---")

        # 수집 실행 버튼
        st.markdown("**수집 실행**")
        if st.button("🔄 지금 수집 실행", use_container_width=True, type="primary"):
            st.session_state["run_crawler"] = True

        st.markdown("---")
        st.markdown("**필터**")
        filter_days = st.selectbox("기간", [7, 14, 30, 90, 0],
                                   format_func=lambda x: "전체" if x == 0 else f"최근 {x}일")

    # ── 수집 실행 처리 ────────────────────────────────────
    if st.session_state.get("run_crawler"):
        st.session_state["run_crawler"] = False
        with st.container():
            st.markdown("### 🔄 수집 진행 중...")
            bar = st.progress(0)
            status = st.empty()
            added = run_crawler(bar, status)
            time.sleep(1)
            st.success(f"수집 완료! 신규 {added}건")
            st.rerun()

    # ── 탭 구성 ──────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["📊 분석", "📋 수집 결과", "🔑 키워드 관리", "ℹ️ 정보"])

    stats = database.get_stats()
    days = filter_days if filter_days > 0 else None
    items = database.get_all_items(days=days)

    # ════════════════════════════════════════════════════
    # TAB 1: 분석
    # ════════════════════════════════════════════════════
    with tab1:
        st.markdown(f"### 📊 수집 현황 {'(전체)' if not days else f'(최근 {days}일)'}")

        # 요약 지표
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("누적 수집", f"{stats['total']:,}건")
        with col2:
            st.metric("이번 기간", f"{len(items):,}건")
        with col3:
            st.metric("카테고리 수", f"{len(stats.get('by_category', {})):,}개")
        with col4:
            kws = database.get_keywords()
            total_kw = sum(len(v) for v in kws.values())
            st.metric("추적 키워드", f"{total_kw:,}개")

        st.markdown("---")

        # 차트
        try:
            import plotly.express as px
            import plotly.graph_objects as go
            import pandas as pd

            col_a, col_b = st.columns(2)

            # 카테고리별 언급 수
            with col_a:
                st.markdown("**카테고리별 수집 수**")
                if stats.get("by_category"):
                    df_cat = pd.DataFrame(
                        list(stats["by_category"].items()),
                        columns=["카테고리", "수집수"]
                    ).sort_values("수집수", ascending=True)
                    fig = px.bar(df_cat, x="수집수", y="카테고리",
                                 orientation="h", color="수집수",
                                 color_continuous_scale="Blues")
                    fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0),
                                      showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

            # 플랫폼별 분포
            with col_b:
                st.markdown("**플랫폼별 분포**")
                if stats.get("by_platform"):
                    df_plat = pd.DataFrame(
                        [(PLATFORM_KR.get(k, k), v)
                         for k, v in stats["by_platform"].items()],
                        columns=["플랫폼", "수집수"]
                    )
                    fig2 = px.pie(df_plat, names="플랫폼", values="수집수",
                                  color_discrete_sequence=px.colors.qualitative.Set3)
                    fig2.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
                    st.plotly_chart(fig2, use_container_width=True)

            # 일별 트렌드
            if stats.get("daily_trend"):
                st.markdown("**일별 수집 트렌드**")
                df_trend = pd.DataFrame(stats["daily_trend"])
                df_trend = df_trend.sort_values("date")
                fig3 = px.line(df_trend, x="date", y="count",
                               markers=True, color_discrete_sequence=["#0066cc"])
                fig3.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0),
                                   xaxis_title="날짜", yaxis_title="수집수")
                st.plotly_chart(fig3, use_container_width=True)

            # 키워드별 TOP 10
            if stats.get("top_queries"):
                st.markdown("**키워드별 수집 TOP 10**")
                df_top = pd.DataFrame(stats["top_queries"][:10])
                df_top = df_top.sort_values("count", ascending=True)
                fig4 = px.bar(df_top, x="count", y="query",
                              orientation="h", color="category",
                              color_discrete_sequence=px.colors.qualitative.Pastel)
                fig4.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0),
                                   xaxis_title="수집수", yaxis_title="")
                st.plotly_chart(fig4, use_container_width=True)

        except ImportError:
            st.warning("차트를 보려면 `pip install plotly pandas` 를 실행하세요.")

        # AI 요약
        st.markdown("---")
        st.markdown("**🤖 AI 요약 (영업팀 관점)**")
        if st.button("AI 요약 생성", type="secondary"):
            with st.spinner("Claude가 분석 중..."):
                summary = ai_summarize(items[:50])
            st.info(summary)

    # ════════════════════════════════════════════════════
    # TAB 2: 수집 결과
    # ════════════════════════════════════════════════════
    with tab2:
        st.markdown("### 📋 수집 결과")

        # 필터
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            cats = ["전체"] + sorted(set(it.get("query_category", "") for it in items if it.get("query_category")))
            sel_cat = st.selectbox("카테고리", cats)
        with col2:
            plats = ["전체"] + sorted(set(it.get("platform", "") for it in items if it.get("platform")))
            sel_plat = st.selectbox("플랫폼", plats,
                                    format_func=lambda x: "전체" if x == "전체" else PLATFORM_KR.get(x, x))
        with col3:
            search_kw = st.text_input("🔍 제목/본문 검색", placeholder="키워드 입력...")

        # 필터 적용
        filtered = items
        if sel_cat != "전체":
            filtered = [it for it in filtered if it.get("query_category") == sel_cat]
        if sel_plat != "전체":
            filtered = [it for it in filtered if it.get("platform") == sel_plat]
        if search_kw:
            filtered = [it for it in filtered
                        if search_kw.lower() in (it.get("title", "") + it.get("description", "")).lower()]

        st.markdown(f"**{len(filtered):,}건** 표시 중")

        # 결과 목록
        for it in filtered[:200]:
            url = it.get("url", "#")
            title = it.get("title", "제목 없음")
            desc = it.get("description", "")[:120]
            platform = it.get("platform", "")
            source = it.get("blogger_name") or it.get("cafe_name") or ""
            pub = (it.get("pub_date") or "")[:10]
            query = it.get("query", "")

            st.markdown(
                f'<div style="background:white;border:1px solid #e0e0e0;border-radius:8px;'
                f'padding:12px 16px;margin-bottom:8px;">'
                f'<div style="font-weight:600;margin-bottom:4px;">'
                f'<a href="{url}" target="_blank" style="color:#0066cc;text-decoration:none;">'
                f'{title}</a></div>'
                f'<div style="color:#555;font-size:13px;margin-bottom:6px;">{desc}</div>'
                f'<div style="font-size:12px;color:#888;">'
                f'{badge(platform)} '
                f'<span style="margin-right:12px;">{source}</span>'
                f'<span style="margin-right:12px;">📅 {pub}</span>'
                f'<span>🔎 {query}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        if len(filtered) > 200:
            st.info(f"상위 200건만 표시 중. 전체 {len(filtered)}건.")

    # ════════════════════════════════════════════════════
    # TAB 3: 키워드 관리
    # ════════════════════════════════════════════════════
    with tab3:
        st.markdown("### 🔑 키워드 관리")
        st.caption("키워드를 추가하거나 삭제하세요. 변경사항은 다음 수집 실행 시 반영됩니다.")

        keywords = database.get_keywords()

        # 키워드 추가
        with st.expander("➕ 키워드 추가", expanded=True):
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                cat_options = list(keywords.keys()) + ["새 카테고리 추가..."]
                sel_add_cat = st.selectbox("카테고리", cat_options, key="add_cat")
            with col2:
                if sel_add_cat == "새 카테고리 추가...":
                    new_cat_name = st.text_input("새 카테고리 이름", key="new_cat_name")
                    add_kw = st.text_input("키워드", key="add_kw_new")
                else:
                    new_cat_name = ""
                    add_kw = st.text_input("키워드", key="add_kw")
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("추가", key="btn_add"):
                    cat_to_use = new_cat_name if sel_add_cat == "새 카테고리 추가..." else sel_add_cat
                    kw_to_add = add_kw.strip()
                    if cat_to_use and kw_to_add:
                        ok = database.add_keyword(cat_to_use, kw_to_add)
                        if ok:
                            st.success(f"'{kw_to_add}' 추가 완료!")
                            st.rerun()
                        else:
                            st.warning("이미 존재하는 키워드입니다.")
                    else:
                        st.warning("카테고리와 키워드를 모두 입력해주세요.")

        st.markdown("---")
        st.markdown("**현재 키워드 목록**")

        # 카테고리별 키워드 표시 + 삭제
        for cat, kws in keywords.items():
            with st.expander(f"📌 {cat} ({len(kws)}개)", expanded=True):
                for kw in kws:
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"• {kw}")
                    with col2:
                        if st.button("삭제", key=f"del_{cat}_{kw}"):
                            database.delete_keyword(cat, kw)
                            st.rerun()

    # ════════════════════════════════════════════════════
    # TAB 4: 정보
    # ════════════════════════════════════════════════════
    with tab4:
        st.markdown("### ℹ️ 시스템 정보")
        st.markdown(f"""
| 항목 | 상태 |
|---|---|
| 네이버 API | {'✅ 연결됨' if NAVER_OK else '❌ 키 없음 (.env 확인)'} |
| 카카오 API | {'✅ 연결됨' if KAKAO_OK else '❌ 키 없음 (.env 확인)'} |
| 구글 RSS | {'✅ 사용 가능' if GOOGLE_OK else '❌ 오류'} |
| AI 요약 | {'✅ 사용 가능' if ANTHROPIC_KEY else '❌ ANTHROPIC_API_KEY 없음'} |
| DB 위치 | `{database.DB_PATH}` |
| 누적 수집 | {stats['total']:,}건 |
""")
        st.markdown("---")
        st.markdown("**비밀번호 변경 방법**")
        st.code("DASHBOARD_PASSWORD=새비밀번호  # .env 파일에서 수정")


if __name__ == "__main__":
    main()
