"""
아리텍 영업·경쟁사 크롤링 대시보드 v3
Supabase 연동 + 사용자별 로그인 + 키워드 관리
실행: streamlit run dashboard.py
"""

import os, sys, time
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import config as cfg
import supabase_db as sdb

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

try:
    import naver_api; NAVER_OK = True
except RuntimeError:
    NAVER_OK = False
try:
    import kakao_api; KAKAO_OK = kakao_api.KAKAO_AVAILABLE
except: KAKAO_OK = False
try:
    import google_rss; GOOGLE_OK = True
except: GOOGLE_OK = False

st.set_page_config(page_title="아리텍 크롤링 대시보드", page_icon="🔍",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
  .main .block-container{padding-top:1.5rem}
  .badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600;margin-right:4px}
  .badge-news{background:#ffe5e5;color:#c00}
  .badge-blog{background:#e5f0ff;color:#06c}
  .badge-cafearticle{background:#e8f5e5;color:#2a7}
  .badge-kakao_news{background:#fff3cd;color:#856404}
  .badge-kakao_blog{background:#fde8ff;color:#6f42c1}
  .badge-kakao_cafe{background:#e8fff3;color:#1a7a4a}
  .badge-google_news{background:#fce8e6;color:#d93025}
</style>""", unsafe_allow_html=True)

PLATFORM_KR = {
    "news":"네이버뉴스","blog":"네이버블로그","cafearticle":"네이버카페",
    "kakao_news":"카카오뉴스","kakao_blog":"카카오블로그","kakao_cafe":"카카오카페",
    "google_news":"구글뉴스",
}

def badge(p):
    return f'<span class="badge badge-{p}">{PLATFORM_KR.get(p,p)}</span>'

def get_cookie(key):
    try:
        import extra_streamlit_components as stx
        cm = stx.CookieManager()
        return cm.get(key)
    except: return None

def set_cookie(key, value):
    try:
        import extra_streamlit_components as stx
        cm = stx.CookieManager()
        cm.set(key, value, max_age=30*24*3600)
    except: pass

def delete_cookie(key):
    try:
        import extra_streamlit_components as stx
        cm = stx.CookieManager()
        cm.delete(key)
    except: pass

def login_page():
    st.markdown("## 🔍 아리텍 크롤링 대시보드")
    st.markdown("---")
    if not sdb.SUPABASE_OK:
        st.error("Supabase 연결 실패. SUPABASE_URL, SUPABASE_ANON_KEY 확인하세요.")
        return

    # 자동 로그인 확인
    saved_user = get_cookie("ari_username")
    saved_pw = get_cookie("ari_password")
    if saved_user and saved_pw:
        user = sdb.get_user(saved_user, saved_pw)
        if user:
            st.session_state["user"] = user
            st.rerun()

    c1,c2,c3 = st.columns([1,1.5,1])
    with c2:
        u = st.text_input("아이디")
        p = st.text_input("비밀번호", type="password")
        remember = st.checkbox("자동 로그인", value=True)
        if st.button("로그인", use_container_width=True, type="primary"):
            user = sdb.get_user(u, p)
            if user:
                st.session_state["user"] = user
                if remember:
                    set_cookie("ari_username", u)
                    set_cookie("ari_password", p)
                else:
                    delete_cookie("ari_username")
                    delete_cookie("ari_password")
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 틀렸습니다.")

def run_crawler(user_id, progress_bar, status_text):
    keywords = sdb.get_keywords(user_id) or sdb.get_default_keywords()
    all_kw = [(cat,kw) for cat,kws in keywords.items() for kw in kws]
    total = len(all_kw); added_total = 0
    for i,(cat,kw) in enumerate(all_kw):
        status_text.text(f"수집 중... [{i+1}/{total}] '{kw}'")
        progress_bar.progress((i+1)/total)
        items = []
        if NAVER_OK:
            try: items += naver_api.search_all_platforms(kw,display=cfg.DISPLAY_PER_KEYWORD,platforms=cfg.PLATFORMS,sort=cfg.SORT_ORDER)
            except: pass
        if KAKAO_OK:
            try: items += kakao_api.search_all_platforms(kw,size=30)
            except: pass
        if GOOGLE_OK:
            try: items += google_rss.search(kw,max_results=20)
            except: pass
        for it in items:
            if "url" in it and "link" not in it: it["link"]=it["url"]
        added_total += sdb.save_items(items, query_category=cat, user_id=user_id)
    status_text.text(f"✅ 완료! 신규 {added_total}건 저장")
    return added_total

def ai_summarize(items):
    if not ANTHROPIC_KEY: return "ANTHROPIC_API_KEY 없음"
    if not items: return "항목 없음"
    try:
        import requests as req
        lines = [f"[{it.get('query_category','')}/{it.get('query','')}] {it.get('title','')} — {it.get('description','')[:80]}" for it in items[:40]]
        prompt = f"음식물쓰레기 처리 업계 크롤링 결과입니다. 아리텍바이오 영업팀 관점에서 경쟁사 동향, 업계 이슈, 영업 기회 중심으로 3~5줄 요약:\n\n" + "\n".join(lines)
        res = req.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":"claude-haiku-4-5-20251001","max_tokens":500,"messages":[{"role":"user","content":prompt}]},timeout=30)
        res.raise_for_status()
        return res.json()["content"][0]["text"]
    except Exception as e:
        return f"오류: {e}"

def main_dashboard():
    user = st.session_state["user"]
    is_admin = user.get("role") == "admin"

    with st.sidebar:
        st.markdown(f"**👤 {user['username']}** {'👑' if is_admin else ''}")
        st.markdown("---")
        st.markdown(f"{'🟢' if NAVER_OK else '🔴'} 네이버")
        st.markdown(f"{'🟢' if KAKAO_OK else '🔴'} 카카오")
        st.markdown(f"{'🟢' if GOOGLE_OK else '🔴'} 구글 RSS")
        st.markdown(f"{'🟢' if sdb.SUPABASE_OK else '🔴'} Supabase DB")
        st.markdown("---")
        if st.button("🔄 지금 수집 실행", use_container_width=True, type="primary"):
            st.session_state["run_crawler"] = True
        st.markdown("---")
        filter_days = st.selectbox("기간", [7,14,30,90,0], format_func=lambda x:"전체" if x==0 else f"최근 {x}일")
        st.markdown("---")
        if st.button("🚪 로그아웃", use_container_width=True):
            delete_cookie("ari_username")
            delete_cookie("ari_password")
            del st.session_state["user"]; st.rerun()

    if st.session_state.get("run_crawler"):
        st.session_state["run_crawler"] = False
        st.markdown("### 🔄 수집 진행 중...")
        bar = st.progress(0); status = st.empty()
        added = run_crawler(user["id"], bar, status)
        time.sleep(1); st.success(f"완료! 신규 {added}건"); st.rerun()

    tabs = ["📊 분석","📋 수집 결과","🔑 키워드 관리"]
    if is_admin: tabs.append("👑 사용자 관리")
    tabs.append("ℹ️ 정보")
    tab_list = st.tabs(tabs)

    days = filter_days if filter_days > 0 else None
    stats = sdb.get_stats(user_id=user["id"])
    items = sdb.get_items(days=days, user_id=user["id"])

    # 분석
    with tab_list[0]:
        st.markdown(f"### 📊 수집 현황")
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("누적 수집", f"{stats['total']:,}건")
        with c2: st.metric("이번 기간", f"{len(items):,}건")
        with c3: st.metric("카테고리 수", f"{len(stats.get('by_category',{})):,}개")
        with c4:
            kws = sdb.get_keywords(user["id"])
            st.metric("내 키워드", f"{sum(len(v) for v in kws.values()):,}개")
        st.markdown("---")
        try:
            import plotly.express as px, pandas as pd
            ca, cb = st.columns(2)
            with ca:
                st.markdown("**카테고리별**")
                if stats.get("by_category"):
                    df = pd.DataFrame(list(stats["by_category"].items()),columns=["카테고리","수집수"]).sort_values("수집수")
                    fig = px.bar(df,x="수집수",y="카테고리",orientation="h",color="수집수",color_continuous_scale="Blues")
                    fig.update_layout(height=300,margin=dict(l=0,r=0,t=20,b=0),showlegend=False)
                    st.plotly_chart(fig,use_container_width=True)
            with cb:
                st.markdown("**플랫폼별**")
                if stats.get("by_platform"):
                    df2 = pd.DataFrame([(PLATFORM_KR.get(k,k),v) for k,v in stats["by_platform"].items()],columns=["플랫폼","수집수"])
                    fig2 = px.pie(df2,names="플랫폼",values="수집수",color_discrete_sequence=px.colors.qualitative.Set3)
                    fig2.update_layout(height=300,margin=dict(l=0,r=0,t=20,b=0))
                    st.plotly_chart(fig2,use_container_width=True)
            if stats.get("daily_trend"):
                st.markdown("**일별 트렌드**")
                df3 = pd.DataFrame(stats["daily_trend"]).sort_values("date")
                fig3 = px.line(df3,x="date",y="count",markers=True,color_discrete_sequence=["#0066cc"])
                fig3.update_layout(height=250,margin=dict(l=0,r=0,t=10,b=0))
                st.plotly_chart(fig3,use_container_width=True)
        except ImportError:
            st.warning("차트: pip install plotly pandas")
        st.markdown("---")
        if st.button("🤖 AI 요약 생성"):
            with st.spinner("분석 중..."):
                st.info(ai_summarize(items[:50]))

    # 수집 결과
    with tab_list[1]:
        st.markdown("### 📋 수집 결과")
        c1,c2,c3 = st.columns([2,2,3])
        with c1:
            cats = ["전체"]+sorted(set(it.get("query_category","") for it in items if it.get("query_category")))
            sel_cat = st.selectbox("카테고리", cats)
        with c2:
            plats = ["전체"]+sorted(set(it.get("platform","") for it in items if it.get("platform")))
            sel_plat = st.selectbox("플랫폼", plats, format_func=lambda x:"전체" if x=="전체" else PLATFORM_KR.get(x,x))
        with c3:
            search_kw = st.text_input("🔍 검색")
        filtered = items
        if sel_cat != "전체": filtered = [it for it in filtered if it.get("query_category")==sel_cat]
        if sel_plat != "전체": filtered = [it for it in filtered if it.get("platform")==sel_plat]
        if search_kw: filtered = [it for it in filtered if search_kw.lower() in (it.get("title","")+it.get("description","")).lower()]
        st.markdown(f"**{len(filtered):,}건**")
        for it in filtered[:200]:
            st.markdown(
                f'<div style="background:white;border:1px solid #e0e0e0;border-radius:8px;padding:12px 16px;margin-bottom:8px;">'
                f'<div style="font-weight:600;margin-bottom:4px;"><a href="{it.get("url","#")}" target="_blank" style="color:#0066cc;text-decoration:none;">{it.get("title","")}</a></div>'
                f'<div style="color:#555;font-size:13px;margin-bottom:6px;">{(it.get("description") or "")[:120]}</div>'
                f'<div style="font-size:12px;color:#888;">{badge(it.get("platform",""))}'
                f'<span style="margin-right:12px;">{it.get("blogger_name") or it.get("cafe_name") or ""}</span>'
                f'<span style="margin-right:12px;">📅 {(it.get("pub_date") or "")[:10]}</span>'
                f'<span>🔎 {it.get("query","")}</span></div></div>',
                unsafe_allow_html=True)
        if len(filtered) > 200: st.info(f"상위 200건만 표시. 전체 {len(filtered)}건.")

    # 키워드 관리
    with tab_list[2]:
        st.markdown(f"### 🔑 {user['username']}님의 키워드")
        keywords = sdb.get_keywords(user["id"])
        if not keywords:
            st.warning("아직 키워드가 없습니다.")
            if st.button("기본 키워드로 시작하기"):
                sdb.copy_default_keywords_to_user(user["id"])
                st.success("기본 키워드 추가 완료!"); st.rerun()
        else:
            with st.expander("➕ 키워드 추가", expanded=True):
                c1,c2,c3 = st.columns([2,3,1])
                with c1:
                    cat_opts = list(keywords.keys())+["새 카테고리..."]
                    sel = st.selectbox("카테고리", cat_opts, key="add_cat")
                with c2:
                    if sel == "새 카테고리...":
                        nc = st.text_input("새 카테고리", key="nc"); kw_in = st.text_input("키워드", key="kw_nc")
                    else:
                        nc = ""; kw_in = st.text_input("키워드", key="kw_in")
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("추가"):
                        cat_use = nc if sel=="새 카테고리..." else sel
                        kw_use = kw_in.strip()
                        if cat_use and kw_use:
                            if sdb.add_keyword(user["id"], cat_use, kw_use):
                                st.success(f"추가!"); st.rerun()
                            else: st.warning("이미 존재합니다.")
                        else: st.warning("입력하세요.")
            for cat, kws in keywords.items():
                with st.expander(f"📌 {cat} ({len(kws)}개)", expanded=True):
                    for kw in kws:
                        c1,c2 = st.columns([5,1])
                        with c1: st.markdown(f"• {kw}")
                        with c2:
                            if st.button("삭제", key=f"d_{cat}_{kw}"):
                                sdb.delete_keyword(user["id"], cat, kw); st.rerun()

    # 사용자 관리 (admin)
    if is_admin:
        with tab_list[3]:
            st.markdown("### 👑 사용자 관리")
            with st.expander("➕ 새 사용자 추가", expanded=True):
                c1,c2,c3,c4 = st.columns([2,2,2,1])
                with c1: nu = st.text_input("아이디", key="nu")
                with c2: np = st.text_input("비밀번호", key="np", type="password")
                with c3: nr = st.selectbox("권한", ["user","admin"], key="nr")
                with c4:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("추가", key="add_user"):
                        if nu and np:
                            if sdb.create_user(nu, np, nr): st.success(f"'{nu}' 추가!"); st.rerun()
                            else: st.error("추가 실패")
                        else: st.warning("입력하세요.")
            users = sdb.get_all_users()
            for u in users:
                c1,c2,c3,c4 = st.columns([2,2,2,1])
                with c1: st.markdown(f"**{u['username']}**")
                with c2: st.markdown(f"{'👑 관리자' if u.get('role')=='admin' else '👤 일반'}")
                with c3: st.markdown(f"{(u.get('created_at') or '')[:10]}")
                with c4:
                    if u["username"] != user["username"]:
                        if st.button("삭제", key=f"du_{u['id']}"):
                            sdb.delete_user(u["id"]); st.rerun()

    # 정보
    with tab_list[-1]:
        st.markdown("### ℹ️ 시스템 정보")
        st.markdown(f"""
| 항목 | 상태 |
|---|---|
| 네이버 API | {'✅' if NAVER_OK else '❌'} |
| 카카오 API | {'✅' if KAKAO_OK else '❌'} |
| 구글 RSS | {'✅' if GOOGLE_OK else '❌'} |
| Supabase DB | {'✅' if sdb.SUPABASE_OK else '❌'} |
| AI 요약 | {'✅' if ANTHROPIC_KEY else '❌'} |
| 누적 수집 | {stats['total']:,}건 |
""")

def main():
    if "user" not in st.session_state:
        login_page()
    else:
        main_dashboard()

if __name__ == "__main__":
    main()
