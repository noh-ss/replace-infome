#!/usr/bin/env python
"""
관리자 대시보드
크롤링 관리, 통계, 모니터링
"""

import sys
from pathlib import Path
import sqlite3
from datetime import datetime
import subprocess
import json

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import streamlit.components.v1
import pandas as pd

from config.settings import settings
from src.crawler.url_manager import URLManager


# 페이지 설정
st.set_page_config(
    page_title="GNU RAG 관리자 대시보드",
    page_icon="🎛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 사이드바
st.sidebar.title("🎛️ 관리자 대시보드")
st.sidebar.markdown("---")

# 메뉴 선택
menu = st.sidebar.radio(
    "메뉴",
    ["📊 대시보드", "🕷️ 크롤링 관리", "🔗 URL 추출", "📁 데이터 관리", "⚙️ 설정"]
)

st.sidebar.markdown("---")
st.sidebar.info(f"**프로젝트**: GNU RAG Bot\n**버전**: 1.0.0")


def get_crawl_stats():
    """크롤링 통계 가져오기"""
    url_manager = URLManager()
    stats = url_manager.get_stats()

    # 추가 통계
    db_path = settings.metadata_dir / "crawl_metadata.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 최근 크롤링 시간
    cursor.execute("SELECT MAX(crawl_date) FROM urls WHERE status = 'visited'")
    last_crawl = cursor.fetchone()[0]

    conn.close()

    return {
        **stats,
        "last_crawl": last_crawl
    }


def get_file_stats():
    """파일 통계 가져오기"""
    raw_pages = list(settings.raw_data_dir.glob("pages/*.html"))
    raw_bulletins = list(settings.raw_data_dir.glob("bulletins/*.html"))

    # 파일 크기 계산
    total_size = sum(f.stat().st_size for f in raw_pages + raw_bulletins)

    return {
        "pages_count": len(raw_pages),
        "bulletins_count": len(raw_bulletins),
        "total_files": len(raw_pages) + len(raw_bulletins),
        "total_size_mb": total_size / (1024 * 1024)
    }


def render_dashboard():
    """대시보드 렌더링"""
    st.title("📊 관리자 대시보드")
    st.markdown("GNU RAG Bot 크롤링 및 데이터 현황")
    st.markdown("---")

    # 통계 가져오기
    crawl_stats = get_crawl_stats()
    file_stats = get_file_stats()

    # 주요 지표 (4열)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="✅ 크롤링 완료",
            value=f"{crawl_stats['visited']:,}",
            delta=None
        )

    with col2:
        st.metric(
            label="⏳ 대기 중",
            value=f"{crawl_stats['pending']:,}",
            delta=None
        )

    with col3:
        st.metric(
            label="❌ 실패",
            value=f"{crawl_stats['failed']:,}",
            delta=None
        )

    with col4:
        st.metric(
            label="📁 총 파일",
            value=f"{file_stats['total_files']:,}",
            delta=None
        )

    st.markdown("---")

    # 상세 정보 (2열)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 크롤링 통계")

        stats_data = {
            "항목": ["총 URL", "크롤링 완료", "대기 중", "실패"],
            "개수": [
                crawl_stats['total'],
                crawl_stats['visited'],
                crawl_stats['pending'],
                crawl_stats['failed']
            ]
        }
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True)

        # 진행률
        if crawl_stats['total'] > 0:
            progress = crawl_stats['visited'] / crawl_stats['total']
            st.progress(progress)
            st.caption(f"진행률: {progress*100:.1f}%")

    with col2:
        st.subheader("💾 데이터 현황")

        data_stats = {
            "항목": ["일반 페이지", "게시판", "총 파일", "총 용량"],
            "값": [
                f"{file_stats['pages_count']:,}개",
                f"{file_stats['bulletins_count']:,}개",
                f"{file_stats['total_files']:,}개",
                f"{file_stats['total_size_mb']:.2f} MB"
            ]
        }
        st.dataframe(pd.DataFrame(data_stats), use_container_width=True)

        # 최근 크롤링 시간
        if crawl_stats['last_crawl']:
            st.info(f"🕒 최근 크롤링: {crawl_stats['last_crawl']}")
        else:
            st.warning("아직 크롤링이 진행되지 않았습니다.")

    st.markdown("---")

    # 최근 URL 목록
    st.subheader("🔗 최근 크롤링한 URL")

    db_path = settings.metadata_dir / "crawl_metadata.db"
    conn = sqlite3.connect(db_path)

    query = """
        SELECT url, status, depth, crawl_date, error_message
        FROM urls
        WHERE status IN ('visited', 'failed')
        ORDER BY crawl_date DESC
        LIMIT 20
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("크롤링된 URL이 없습니다.")


def render_crawler_management():
    """크롤링 관리 페이지"""
    st.title("🕷️ 크롤링 관리")
    st.markdown("크롤러 실행 및 관리")
    st.markdown("---")

    # 크롤링 설정
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⚙️ 크롤링 설정")

        max_pages = st.number_input(
            "최대 페이지 수",
            min_value=1,
            max_value=10000,
            value=50,
            step=10
        )

        start_urls = st.text_area(
            "시작 URL (한 줄에 하나씩)",
            value="\n".join(settings.get_crawl_start_urls()),
            height=100
        )

    with col2:
        st.subheader("📊 현재 상태")
        stats = get_crawl_stats()

        st.metric("대기 중인 URL", f"{stats['pending']:,}")
        st.metric("크롤링 완료", f"{stats['visited']:,}")
        st.metric("실패", f"{stats['failed']:,}")

    st.markdown("---")

    # 크롤링 실행
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("▶️ 크롤링 시작", type="primary", use_container_width=True):
            with st.spinner("크롤링 중..."):
                try:
                    # 크롤링 실행
                    result = subprocess.run(
                        [
                            sys.executable,
                            "scripts/run_crawler.py",
                            "--max-pages", str(max_pages)
                        ],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )

                    if result.returncode == 0:
                        st.success("✅ 크롤링 완료!")
                        st.code(result.stdout[-1000:])  # 마지막 1000자
                    else:
                        st.error("❌ 크롤링 실패")
                        st.code(result.stderr[-1000:])

                except subprocess.TimeoutExpired:
                    st.warning("⏰ 크롤링 시간 초과 (5분)")
                except Exception as e:
                    st.error(f"오류 발생: {str(e)}")

    with col2:
        if st.button("🔄 URL 큐 리셋", use_container_width=True):
            if st.session_state.get('confirm_reset'):
                # URL 큐 초기화
                db_path = settings.metadata_dir / "crawl_metadata.db"
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE urls SET status = 'pending' WHERE status = 'visited'")
                conn.commit()
                conn.close()

                st.success("✅ URL 큐가 리셋되었습니다.")
                st.session_state['confirm_reset'] = False
            else:
                st.session_state['confirm_reset'] = True
                st.warning("⚠️ 다시 클릭하면 리셋됩니다.")

    with col3:
        if st.button("🗑️ 모든 데이터 삭제", use_container_width=True):
            if st.session_state.get('confirm_delete'):
                # 데이터 삭제
                import shutil

                # HTML 파일 삭제
                if settings.raw_data_dir.exists():
                    shutil.rmtree(settings.raw_data_dir)
                    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)

                # DB 초기화
                db_path = settings.metadata_dir / "crawl_metadata.db"
                if db_path.exists():
                    db_path.unlink()

                st.success("✅ 모든 데이터가 삭제되었습니다.")
                st.session_state['confirm_delete'] = False
            else:
                st.session_state['confirm_delete'] = True
                st.warning("⚠️ 다시 클릭하면 모든 데이터가 삭제됩니다!")


def render_data_management():
    """데이터 관리 페이지"""
    st.title("📁 데이터 관리")
    st.markdown("크롤링된 데이터 확인 및 관리")
    st.markdown("---")

    # 데이터 디렉토리 정보
    st.subheader("📂 데이터 디렉토리")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info(f"**원본 데이터**\n`{settings.raw_data_dir}`")

    with col2:
        st.info(f"**처리된 데이터**\n`{settings.processed_data_dir}`")

    with col3:
        st.info(f"**벡터 스토어**\n`{settings.vector_store_dir}`")

    st.markdown("---")

    # URL 검색
    st.subheader("🔍 URL 검색")

    search_query = st.text_input("URL 또는 키워드로 검색")

    if search_query:
        db_path = settings.metadata_dir / "crawl_metadata.db"
        conn = sqlite3.connect(db_path)

        query = f"""
            SELECT url, status, depth, crawl_date
            FROM urls
            WHERE url LIKE '%{search_query}%'
            ORDER BY crawl_date DESC
            LIMIT 50
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("검색 결과가 없습니다.")

    st.markdown("---")

    # 파일 목록
    st.subheader("📄 크롤링된 파일 목록")

    html_files = sorted(
        settings.raw_data_dir.glob("pages/*.html"),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )[:20]

    if html_files:
        file_data = []
        for f in html_files:
            file_data.append({
                "파일명": f.name,
                "크기": f"{f.stat().st_size / 1024:.1f} KB",
                "수정 시간": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

        st.dataframe(pd.DataFrame(file_data), use_container_width=True)
    else:
        st.info("크롤링된 파일이 없습니다.")


def extract_links_subprocess(target_url):
    """subprocess로 링크 추출 (Playwright 충돌 방지)"""
    import sys
    result = subprocess.run(
        [
            sys.executable, "-c", f'''
import json
from src.crawler.page_scraper import PageScraper

with PageScraper(headless=True) as scraper:
    result = scraper.fetch_page("{target_url}")
    if result:
        print(json.dumps({{"success": True, "links": result["links"], "title": result["title"]}}))
    else:
        print(json.dumps({{"success": False, "links": [], "title": ""}}))
'''
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60
    )
    return result


def render_url_extractor():
    """URL 관리 페이지 - 게시판 스타일"""
    st.title("🔗 URL 관리")

    # 세션 상태 초기화
    if 'selected_url' not in st.session_state:
        st.session_state['selected_url'] = None
    if 'view_mode' not in st.session_state:
        st.session_state['view_mode'] = 'list'  # list, detail, add, extract
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 0

    db_path = settings.metadata_dir / "crawl_metadata.db"

    # ===== 상단 통계 =====
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        stats_df = pd.read_sql_query("SELECT status, COUNT(*) as cnt FROM urls GROUP BY status", conn)
        total_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM urls", conn).iloc[0]['cnt']
        conn.close()

        col1, col2, col3, col4 = st.columns(4)
        pending = stats_df[stats_df['status'] == 'pending']['cnt'].sum() if 'pending' in stats_df['status'].values else 0
        visited = stats_df[stats_df['status'] == 'visited']['cnt'].sum() if 'visited' in stats_df['status'].values else 0
        failed = stats_df[stats_df['status'] == 'failed']['cnt'].sum() if 'failed' in stats_df['status'].values else 0

        col1.metric("⏳ 대기", pending)
        col2.metric("✅ 완료", visited)
        col3.metric("❌ 실패", failed)
        col4.metric("📊 전체", total_count)
    else:
        st.info("데이터베이스가 없습니다.")
        total_count = 0

    st.markdown("---")

    # ===== 상단 버튼 =====
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("📋 목록", use_container_width=True, type="primary" if st.session_state['view_mode'] == 'list' else "secondary"):
            st.session_state['view_mode'] = 'list'
            st.session_state['selected_url'] = None
            st.rerun()
    with col2:
        if st.button("➕ URL 추가", use_container_width=True, type="primary" if st.session_state['view_mode'] == 'add' else "secondary"):
            st.session_state['view_mode'] = 'add'
            st.rerun()
    with col3:
        if st.button("🔍 URL 추출", use_container_width=True, type="primary" if st.session_state['view_mode'] == 'extract' else "secondary"):
            st.session_state['view_mode'] = 'extract'
            st.rerun()
    with col4:
        if st.button("🔄 새로고침", use_container_width=True):
            st.rerun()
    with col5:
        if st.button("🗑️ 일괄삭제", use_container_width=True):
            st.session_state['view_mode'] = 'bulk_delete'
            st.rerun()

    st.markdown("---")

    # ===== 목록 보기 =====
    if st.session_state['view_mode'] == 'list':
        # 검색 및 필터
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            search_keyword = st.text_input("🔍 URL 검색", key="search_url", placeholder="검색어 입력...")
        with col2:
            status_filter = st.selectbox("상태", ["전체", "pending", "visited", "failed"], key="status_filter")
        with col3:
            per_page = st.selectbox("페이지당", [10, 20, 50, 100], index=1, key="per_page")

        if db_path.exists():
            conn = sqlite3.connect(db_path)

            # WHERE 조건 구성
            where_clauses = []
            if status_filter != "전체":
                where_clauses.append(f"status = '{status_filter}'")
            if search_keyword:
                where_clauses.append(f"url LIKE '%{search_keyword}%'")
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # 전체 개수 조회
            count_query = f"SELECT COUNT(*) as cnt FROM urls WHERE {where_sql}"
            filtered_count = pd.read_sql_query(count_query, conn).iloc[0]['cnt']

            # 페이지네이션 계산
            total_pages = max(1, (filtered_count + per_page - 1) // per_page)
            current_page = min(st.session_state['current_page'], total_pages - 1)
            offset = current_page * per_page

            # 데이터 조회
            query = f"""
                SELECT url, status, depth, crawl_date, error_message
                FROM urls
                WHERE {where_sql}
                ORDER BY
                    CASE status WHEN 'pending' THEN 1 WHEN 'failed' THEN 2 ELSE 3 END,
                    crawl_date DESC
                LIMIT {per_page} OFFSET {offset}
            """
            df = pd.read_sql_query(query, conn)
            conn.close()

            # 페이지네이션 컨트롤
            st.caption(f"총 {filtered_count}개 중 {offset+1}-{min(offset+per_page, filtered_count)}개 표시")

            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
            with col1:
                if st.button("⏮️ 처음", disabled=current_page == 0):
                    st.session_state['current_page'] = 0
                    st.rerun()
            with col2:
                if st.button("◀️ 이전", disabled=current_page == 0):
                    st.session_state['current_page'] = current_page - 1
                    st.rerun()
            with col3:
                st.markdown(f"<center>페이지 {current_page + 1} / {total_pages}</center>", unsafe_allow_html=True)
            with col4:
                if st.button("다음 ▶️", disabled=current_page >= total_pages - 1):
                    st.session_state['current_page'] = current_page + 1
                    st.rerun()
            with col5:
                if st.button("마지막 ⏭️", disabled=current_page >= total_pages - 1):
                    st.session_state['current_page'] = total_pages - 1
                    st.rerun()

            st.markdown("---")

            # URL 목록 테이블
            if not df.empty:
                for idx, row in df.iterrows():
                    status_icon = {"pending": "⏳", "visited": "✅", "failed": "❌"}.get(row['status'], "❓")

                    col1, col2, col3, col4 = st.columns([4, 1, 1, 2])
                    with col1:
                        # URL 클릭 시 상세보기
                        url_display = row['url'][:70] + "..." if len(row['url']) > 70 else row['url']
                        if st.button(f"{status_icon} {url_display}", key=f"url_{idx}", use_container_width=True):
                            st.session_state['selected_url'] = row['url']
                            st.session_state['view_mode'] = 'detail'
                            st.rerun()
                    with col2:
                        st.caption(f"깊이: {row['depth']}")
                    with col3:
                        st.caption(row['status'])
                    with col4:
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("🔄", key=f"retry_{idx}", help="재시도"):
                                conn = sqlite3.connect(db_path)
                                conn.execute("UPDATE urls SET status = 'pending', error_message = NULL WHERE url = ?", (row['url'],))
                                conn.commit()
                                conn.close()
                                st.rerun()
                        with c2:
                            if st.button("🗑️", key=f"del_{idx}", help="삭제"):
                                conn = sqlite3.connect(db_path)
                                conn.execute("DELETE FROM urls WHERE url = ?", (row['url'],))
                                conn.commit()
                                conn.close()
                                st.rerun()
            else:
                st.info("조건에 맞는 URL이 없습니다.")

    # ===== 상세 보기 =====
    elif st.session_state['view_mode'] == 'detail' and st.session_state['selected_url']:
        url = st.session_state['selected_url']

        st.subheader("📄 URL 상세정보")

        if db_path.exists():
            conn = sqlite3.connect(db_path)
            row = pd.read_sql_query(f"SELECT * FROM urls WHERE url = ?", conn, params=(url,))
            conn.close()

            if not row.empty:
                row = row.iloc[0]

                st.markdown(f"### 🔗 URL")
                st.code(url)
                st.link_button("🌐 새 창에서 열기", url)

                col1, col2, col3 = st.columns(3)
                col1.metric("상태", row['status'])
                col2.metric("깊이", row['depth'])
                col3.metric("크롤링 날짜", row['crawl_date'] or "N/A")

                if row['error_message']:
                    st.error(f"**오류 메시지:** {row['error_message']}")

                st.markdown("---")

                # 액션 버튼
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button("🔄 재시도 (pending)", type="primary", use_container_width=True):
                        conn = sqlite3.connect(db_path)
                        conn.execute("UPDATE urls SET status = 'pending', error_message = NULL WHERE url = ?", (url,))
                        conn.commit()
                        conn.close()
                        st.success("상태가 pending으로 변경됨!")
                        st.rerun()
                with col2:
                    if st.button("✅ 완료 처리", use_container_width=True):
                        conn = sqlite3.connect(db_path)
                        conn.execute("UPDATE urls SET status = 'visited' WHERE url = ?", (url,))
                        conn.commit()
                        conn.close()
                        st.success("상태가 visited로 변경됨!")
                        st.rerun()
                with col3:
                    if st.button("🗑️ 삭제", use_container_width=True):
                        conn = sqlite3.connect(db_path)
                        conn.execute("DELETE FROM urls WHERE url = ?", (url,))
                        conn.commit()
                        conn.close()
                        st.session_state['view_mode'] = 'list'
                        st.session_state['selected_url'] = None
                        st.success("삭제됨!")
                        st.rerun()
                with col4:
                    if st.button("📋 목록으로", use_container_width=True):
                        st.session_state['view_mode'] = 'list'
                        st.session_state['selected_url'] = None
                        st.rerun()

                # 페이지 미리보기
                st.markdown("---")
                st.subheader("🔍 페이지 미리보기")
                if st.button("링크 추출하기"):
                    with st.spinner("페이지 로딩 중..."):
                        try:
                            result = extract_links_subprocess(url)
                            if result.returncode == 0:
                                for line in reversed(result.stdout.strip().split('\n')):
                                    if line.startswith('{'):
                                        data = json.loads(line)
                                        if data['success']:
                                            st.success(f"✅ {len(data['links'])}개 링크 발견!")
                                            for i, link in enumerate(data['links'][:20], 1):
                                                st.markdown(f"{i}. [{link[:60]}...]({link})" if len(link) > 60 else f"{i}. [{link}]({link})")
                                            if len(data['links']) > 20:
                                                st.caption(f"... 외 {len(data['links']) - 20}개")
                                        else:
                                            st.error("페이지를 가져올 수 없습니다.")
                                        break
                        except Exception as e:
                            st.error(f"오류: {str(e)}")

    # ===== URL 추가 =====
    elif st.session_state['view_mode'] == 'add':
        st.subheader("➕ URL 추가")

        # 단일 추가
        new_url = st.text_input("URL 입력", placeholder="https://www.gnu.ac.kr/...")
        new_depth = st.number_input("크롤링 깊이", min_value=0, max_value=10, value=1)

        if st.button("➕ 추가", type="primary") and new_url:
            url_manager = URLManager()
            if url_manager.add_url(new_url, depth=new_depth):
                st.success(f"✅ 추가됨: {new_url}")
            else:
                st.warning("⚠️ 추가 불가 (이미 존재하거나 필터에 걸림)")

        st.markdown("---")

        # 일괄 추가
        st.subheader("📥 여러 URL 일괄 추가")
        bulk_urls = st.text_area("URL 목록 (한 줄에 하나씩)", height=200)

        if st.button("📥 일괄 추가") and bulk_urls:
            url_manager = URLManager()
            urls = [u.strip() for u in bulk_urls.strip().split('\n') if u.strip()]
            added = sum(1 for u in urls if url_manager.add_url(u, depth=new_depth))
            st.success(f"✅ {added}/{len(urls)}개 추가됨!")

    # ===== URL 추출 =====
    elif st.session_state['view_mode'] == 'extract':
        st.subheader("🔍 페이지에서 URL 추출")

        target_url = st.text_input("추출할 페이지 URL", value="https://www.gnu.ac.kr/main/main.do")

        if st.button("🔍 링크 추출", type="primary") and target_url:
            with st.spinner("페이지에서 링크를 추출하는 중..."):
                try:
                    result = extract_links_subprocess(target_url)
                    if result.returncode == 0:
                        for line in reversed(result.stdout.strip().split('\n')):
                            if line.startswith('{'):
                                data = json.loads(line)
                                if data['success']:
                                    st.session_state['extracted_links'] = data['links']
                                    st.session_state['extract_source_url'] = target_url
                                    st.success(f"✅ {len(data['links'])}개 링크 추출됨!")
                                else:
                                    st.error("❌ 페이지를 가져올 수 없습니다.")
                                break
                    else:
                        st.error(f"오류: {result.stderr[-200:]}")
                except Exception as e:
                    st.error(f"오류: {str(e)}")

        # 추출된 링크 표시
        if st.session_state.get('extracted_links'):
            st.markdown("---")

            col1, col2 = st.columns(2)
            with col1:
                filter_domain = st.checkbox("gnu.ac.kr만", value=True)
            with col2:
                filter_dup = st.checkbox("중복제거", value=True)

            links = st.session_state['extracted_links']
            original_count = len(links)
            if filter_domain:
                links = [l for l in links if 'gnu.ac.kr' in l]
            if filter_dup:
                links = list(dict.fromkeys(links))

            st.info(f"총 {len(links)}개 (원본: {original_count}개)")

            # 링크 목록
            for i, link in enumerate(links[:30], 1):
                st.markdown(f"`{i}.` [{link[:70]}...]({link})" if len(link) > 70 else f"`{i}.` [{link}]({link})")

            if len(links) > 30:
                st.caption(f"... 외 {len(links) - 30}개")

            st.markdown("---")
            add_depth = st.number_input("크롤링 깊이", min_value=0, max_value=10, value=1, key="extract_depth")
            if st.button("📥 전체 큐에 추가 & 저장", type="primary"):
                url_manager = URLManager()
                added = sum(1 for l in links if url_manager.add_url(l, depth=add_depth))

                # 추출 내역 DB에 저장
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO extraction_history (source_url, extracted_at, total_links, filtered_links, added_to_queue)
                    VALUES (?, datetime('now', 'localtime'), ?, ?, ?)
                """, (st.session_state.get('extract_source_url', target_url), original_count, len(links), added))
                extraction_id = cursor.lastrowid

                # 추출된 링크 저장
                for link in links:
                    cursor.execute("""
                        INSERT INTO extracted_links (extraction_id, link_url, added_to_queue)
                        VALUES (?, ?, 1)
                    """, (extraction_id, link))

                conn.commit()
                conn.close()

                st.success(f"✅ {added}개 추가됨! (추출 내역 저장됨)")

        # 추출 내역 보기
        st.markdown("---")
        st.subheader("📜 추출 내역")

        if db_path.exists():
            conn = sqlite3.connect(db_path)
            # 테이블 존재 확인
            table_check = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_history'", conn)

            if not table_check.empty:
                history_df = pd.read_sql_query("""
                    SELECT id, source_url, extracted_at, total_links, filtered_links, added_to_queue
                    FROM extraction_history
                    ORDER BY extracted_at DESC
                    LIMIT 10
                """, conn)
                conn.close()

                if not history_df.empty:
                    for idx, row in history_df.iterrows():
                        with st.expander(f"📅 {row['extracted_at']} - {row['source_url'][:50]}..."):
                            st.markdown(f"**원본 URL:** [{row['source_url']}]({row['source_url']})")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("전체 링크", row['total_links'])
                            col2.metric("필터링 후", row['filtered_links'])
                            col3.metric("큐 추가", row['added_to_queue'])

                            # 해당 추출의 링크 보기
                            if st.button(f"링크 보기", key=f"view_links_{row['id']}"):
                                conn2 = sqlite3.connect(db_path)
                                links_df = pd.read_sql_query(f"SELECT link_url FROM extracted_links WHERE extraction_id = {row['id']} LIMIT 20", conn2)
                                conn2.close()
                                for i, link_row in links_df.iterrows():
                                    st.markdown(f"- [{link_row['link_url'][:60]}...]({link_row['link_url']})")

                            # 삭제 버튼
                            if st.button(f"🗑️ 삭제", key=f"del_history_{row['id']}"):
                                conn2 = sqlite3.connect(db_path)
                                conn2.execute(f"DELETE FROM extracted_links WHERE extraction_id = {row['id']}")
                                conn2.execute(f"DELETE FROM extraction_history WHERE id = {row['id']}")
                                conn2.commit()
                                conn2.close()
                                st.success("삭제됨!")
                                st.rerun()
                else:
                    st.info("추출 내역이 없습니다.")
            else:
                conn.close()
                st.info("추출 내역 테이블이 없습니다. URL을 추출하면 자동 생성됩니다.")

    # ===== 일괄 삭제 =====
    elif st.session_state['view_mode'] == 'bulk_delete':
        st.subheader("🗑️ 일괄 삭제")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 실패 URL → 재시도", use_container_width=True, type="primary"):
                conn = sqlite3.connect(db_path)
                conn.execute("UPDATE urls SET status = 'pending', error_message = NULL WHERE status = 'failed'")
                conn.commit()
                conn.close()
                st.success("모든 실패 URL이 pending으로 변경됨!")

        with col2:
            if st.button("🗑️ 실패 URL 삭제", use_container_width=True):
                conn = sqlite3.connect(db_path)
                cursor = conn.execute("DELETE FROM urls WHERE status = 'failed'")
                deleted = cursor.rowcount
                conn.commit()
                conn.close()
                st.success(f"{deleted}개 실패 URL 삭제됨!")

        with col3:
            if st.button("🗑️ 완료 URL 삭제", use_container_width=True):
                conn = sqlite3.connect(db_path)
                cursor = conn.execute("DELETE FROM urls WHERE status = 'visited'")
                deleted = cursor.rowcount
                conn.commit()
                conn.close()
                st.success(f"{deleted}개 완료 URL 삭제됨!")

        st.markdown("---")
        st.warning("⚠️ 아래 작업은 되돌릴 수 없습니다!")

        if st.button("🗑️ 전체 URL 삭제", type="secondary"):
            if st.session_state.get('confirm_delete_all'):
                conn = sqlite3.connect(db_path)
                conn.execute("DELETE FROM urls")
                conn.commit()
                conn.close()
                st.session_state['confirm_delete_all'] = False
                st.success("모든 URL 삭제됨!")
                st.rerun()
            else:
                st.session_state['confirm_delete_all'] = True
                st.error("⚠️ 정말 삭제하시겠습니까? 다시 클릭하세요!")


def render_settings():
    """설정 페이지"""
    st.title("⚙️ 설정")
    st.markdown("시스템 설정 및 환경 변수")
    st.markdown("---")

    # 크롤링 설정
    st.subheader("🕷️ 크롤링 설정")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("시작 URL", value=settings.crawl.start_url, disabled=True)
        st.number_input("최대 깊이", value=settings.crawl.max_crawl_depth, disabled=True)
        st.number_input("속도 제한 (초)", value=settings.crawl.crawl_rate_limit, disabled=True)

    with col2:
        st.text_input("User Agent", value=settings.crawl.user_agent, disabled=True)
        st.number_input("최대 페이지", value=settings.crawl.max_pages, disabled=True)

    st.markdown("---")

    # RAG 설정
    st.subheader("🤖 RAG 설정")

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("청크 크기", value=settings.rag.chunk_size, disabled=True)
        st.number_input("청크 오버랩", value=settings.rag.chunk_overlap, disabled=True)

    with col2:
        st.number_input("Top-K 검색", value=settings.rag.top_k_retrieval, disabled=True)
        st.number_input("유사도 임계값", value=settings.rag.similarity_threshold, disabled=True)

    st.markdown("---")

    # Ollama 설정
    st.subheader("🦙 Ollama 설정")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("Ollama URL", value=settings.ollama.base_url, disabled=True)
        st.text_input("LLM 모델", value=settings.ollama.llm_model, disabled=True)

    with col2:
        st.text_input("임베딩 모델", value=settings.ollama.embedding_model, disabled=True)

    st.info("💡 설정을 변경하려면 `.env` 파일을 수정하세요.")


# 메인 라우팅
if menu == "📊 대시보드":
    render_dashboard()
elif menu == "🕷️ 크롤링 관리":
    render_crawler_management()
elif menu == "🔗 URL 추출":
    render_url_extractor()
elif menu == "📁 데이터 관리":
    render_data_management()
elif menu == "⚙️ 설정":
    render_settings()
