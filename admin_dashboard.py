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
    ["📊 대시보드", "🕷️ 크롤링 관리", "📁 데이터 관리", "⚙️ 설정"]
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
elif menu == "📁 데이터 관리":
    render_data_management()
elif menu == "⚙️ 설정":
    render_settings()
