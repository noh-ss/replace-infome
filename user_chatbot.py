#!/usr/bin/env python
"""
사용자 챗봇 웹 UI
GNU RAG 챗봇 인터페이스
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from datetime import datetime

from config.settings import settings
from src.rag.rag_pipeline import RAGPipeline


# 페이지 설정
st.set_page_config(
    page_title="경상국립대학교 안내 챗봇",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 커스텀 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        color: #333;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #1f77b4;
        color: #1a1a1a;
    }
    .bot-message {
        background-color: #f5f5f5;
        border-left: 4px solid #4caf50;
        color: #1a1a1a;
    }
    .chat-message strong {
        color: #000;
        font-weight: 600;
    }
    .example-question {
        background-color: #fff3e0;
        padding: 0.5rem 1rem;
        border-radius: 0.3rem;
        margin: 0.3rem;
        display: inline-block;
        cursor: pointer;
        border: 1px solid #ff9800;
    }
</style>
""", unsafe_allow_html=True)

# 헤더
st.markdown('<div class="main-header">🎓 경상국립대학교 안내 챗봇</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">궁금한 것을 물어보세요!</div>', unsafe_allow_html=True)

# 세션 상태 초기화
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'chat_started' not in st.session_state:
    st.session_state.chat_started = False

# RAG 파이프라인 초기화 (캐시)
@st.cache_resource
def get_rag_pipeline():
    """RAG 파이프라인 초기화 (캐시됨)"""
    try:
        return RAGPipeline()
    except Exception as e:
        st.error(f"RAG 파이프라인 초기화 실패: {str(e)}")
        return None

rag_pipeline = get_rag_pipeline()


# 챗봇 응답 함수
def get_bot_response(user_input: str) -> tuple[str, list]:
    """
    챗봇 응답 생성 (RAG 파이프라인 사용)

    Returns:
        (답변 텍스트, 출처 목록) 튜플
    """
    if not rag_pipeline:
        return (
            "죄송합니다. 챗봇 시스템이 초기화되지 않았습니다. 페이지를 새로고침해주세요.",
            []
        )

    try:
        # RAG 파이프라인 실행
        response = rag_pipeline.query(user_input, top_k=5, temperature=0.7)

        return (response.answer, response.sources)

    except Exception as e:
        return (
            f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {str(e)}",
            []
        )


# 사이드바
with st.sidebar:
    st.title("💬 채팅 옵션")
    st.markdown("---")

    # 대화 초기화
    if st.button("🗑️ 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_started = False
        st.rerun()

    st.markdown("---")

    # 정보
    st.info("""
    **안내**

    이 챗봇은 경상국립대학교 웹사이트의 정보를 학습하여 질문에 답변합니다.

    - 입학 안내
    - 학사 일정
    - 학과 정보
    - 편의시설
    - 장학금
    - 기타 대학 생활
    """)

    st.markdown("---")

    st.caption(f"© 2026 GNU RAG Bot v1.0")


# 예제 질문
if not st.session_state.chat_started:
    st.markdown("### 💡 이런 질문을 해보세요")

    col1, col2, col3 = st.columns(3)

    example_questions = [
        "경상국립대학교에 대해 알려주세요",
        "등록금 납부 방법은 무엇인가요?",
        "기초학력진단평가는 언제 응시하나요?",
        "신입생 모집 안내를 알려주세요",
        "ICT 교육 프로그램은 무엇인가요?",
        "자람 제도에 대해 설명해주세요"
    ]

    for idx, question in enumerate(example_questions):
        col_idx = idx % 3
        col = [col1, col2, col3][col_idx]

        with col:
            if st.button(f"💭 {question}", key=f"example_{idx}", use_container_width=True):
                # 사용자 메시지 추가
                st.session_state.messages.append({
                    "role": "user",
                    "content": question,
                    "timestamp": datetime.now()
                })
                st.session_state.chat_started = True

                # 봇 응답 즉시 생성
                with st.spinner("답변 생성 중..."):
                    bot_response, sources = get_bot_response(question)

                # 봇 메시지 추가
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": bot_response,
                    "sources": sources,
                    "timestamp": datetime.now()
                })

                st.rerun()

    st.markdown("---")


# 채팅 메시지 표시
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f"""
        <div class="chat-message user-message">
            <strong>👤 사용자</strong><br>
            {message['content']}
        </div>
        """, unsafe_allow_html=True)
    else:
        # 봇 응답
        st.markdown(f"""
        <div class="chat-message bot-message">
            <strong>🤖 챗봇</strong><br>
            {message['content']}
        </div>
        """, unsafe_allow_html=True)

        # 출처 표시
        if 'sources' in message and message['sources']:
            with st.expander(f"📚 출처 ({len(message['sources'])}개)"):
                for i, source in enumerate(message['sources'], 1):
                    st.markdown(f"""
                    **{i}. {source['title']}**
                    - URL: {source['url']}
                    - 유사도: {source['score']}
                    """)
                    st.markdown("---")


# 채팅 입력
user_input = st.chat_input("궁금한 것을 입력하세요...")

if user_input:
    # 사용자 메시지 추가
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now()
    })
    st.session_state.chat_started = True

    # 봇 응답 생성
    with st.spinner("답변 생성 중..."):
        bot_response, sources = get_bot_response(user_input)

    # 봇 메시지 추가
    st.session_state.messages.append({
        "role": "assistant",
        "content": bot_response,
        "sources": sources,
        "timestamp": datetime.now()
    })

    # 화면 새로고침
    st.rerun()


# 하단 푸터
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown("""
    <div style="text-align: center; color: #999; font-size: 0.9rem;">
        <p>🎓 이 챗봇은 RAG 기술을 활용하여 경상국립대학교 정보를 제공합니다.</p>
        <p>✅ Phase 1-4 완료 | 💾 163개 문서 학습 완료</p>
        <p>정확한 정보는 공식 홈페이지를 참고해주세요.</p>
    </div>
    """, unsafe_allow_html=True)
