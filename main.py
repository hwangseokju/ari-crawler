"""
아리텍 영업·경쟁사 크롤러 — 메인 실행 파일

실행 방법:
    python main.py

결과:
    reports/ 폴더에 HTML 리포트가 생성되고 브라우저가 자동으로 열립니다.
"""

import sys
import webbrowser
from datetime import datetime

import config
import naver_api
import database
import report


def main():
    print("=" * 62)
    print(f" 아리텍 크롤링 시작 : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 62)

    # 1. DB 초기화
    database.init_db()
    print(" DB 준비 완료")

    # 2. 키워드별 검색 → DB 저장
    total_keywords = sum(len(v) for v in config.CORE_KEYWORDS.values())
    done = 0
    total_added = 0

    for category, keywords in config.CORE_KEYWORDS.items():
        print(f"\n [{category}] {len(keywords)}개 키워드 검색")
        for kw in keywords:
            done += 1
            items = naver_api.search_all_platforms(
                kw,
                display=config.DISPLAY_PER_KEYWORD,
                platforms=config.PLATFORMS,
                sort=config.SORT_ORDER,
            )
            added = database.save_items(items, query_category=category)
            total_added += added
            print(f"   [{done:>2}/{total_keywords}] '{kw}' : 수집 {len(items):>3}건 / 신규 {added:>3}건")

    print(f"\n 이번 실행 신규 저장 : {total_added}건")

    # 3. 리포트 생성
    print("\n 리포트 생성 중...")
    new_items = database.get_new_items(days=config.NEW_ITEM_DAYS)
    stats = database.get_stats()
    report_path = report.render_report(new_items, stats, days=config.NEW_ITEM_DAYS)

    print(f" 리포트 : {report_path}")
    print(f" 최근 {config.NEW_ITEM_DAYS}일 신규 : {len(new_items)}건 / DB 누적 : {stats['total']}건")

    # 4. 브라우저로 리포트 자동 열기
    try:
        webbrowser.open(report_path.as_uri())
        print(" 브라우저로 리포트 열기 완료")
    except Exception as e:
        print(f" 브라우저 자동 열기 실패 : {e}")
        print(f"   직접 열기 : {report_path}")

    print("\n" + "=" * 62)
    print(" 완료")
    print("=" * 62)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n 사용자 중단")
        sys.exit(1)
    except RuntimeError as e:
        # .env 누락 등 설정 오류
        print(f"\n {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n 예기치 못한 오류 : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
