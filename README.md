# GNU RAG 챗봇 ✅

경상국립대학교(gnu.ac.kr) 웹사이트의 정보를 학습하여 질의응답이 가능한 RAG(Retrieval-Augmented Generation) 챗봇 시스템

## 🎉 구현 완료 상태

- ✅ **Phase 1**: 웹 크롤링 시스템 (완료)
- ✅ **Phase 2**: 텍스트 처리 파이프라인 (완료)
- ✅ **Phase 3**: 벡터 스토어 구축 (완료 - 163개 문서)
- ✅ **Phase 4**: RAG 파이프라인 (완료)
- ✅ **Phase 5**: 웹 UI 통합 (완료)

## 기술 스택

- **프레임워크**: Python + LangChain
- **벡터 DB**: ChromaDB (로컬)
- **LLM**: Ollama (llama3.1)
- **임베딩**: Ollama (nomic-embed-text)
- **웹 크롤링**: Playwright

## 설치 방법

### 1. Python 환경 설정

Python 3.10 이상이 필요합니다.

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (macOS/Linux)
source venv/bin/activate

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. Playwright 브라우저 설치

```bash
playwright install chromium
```

### 3. Ollama 설치 및 모델 다운로드

```bash
# macOS
brew install ollama

# Ollama 서비스 시작
ollama serve

# 다른 터미널에서 모델 다운로드
ollama pull llama3.1
ollama pull nomic-embed-text
```

### 4. 환경 변수 설정

```bash
# .env.example을 .env로 복사
cp .env.example .env

# 필요한 경우 .env 파일을 편집하여 설정 조정
```

### 5. 디렉토리 구조 생성

```bash
mkdir -p data/raw/pages
mkdir -p data/raw/bulletins
mkdir -p data/processed
mkdir -p data/vector_store
mkdir -p data/metadata
mkdir -p logs
```

## 사용 방법

### 1. 웹 크롤링

```bash
python scripts/run_crawler.py --max-pages 100
```

### 2. 관리자 대시보드 실행

```bash
streamlit run admin_dashboard.py
```

관리자 대시보드 기능:
- 📊 크롤링 통계 및 현황 모니터링
- 🕷️ 크롤링 시작/중지/관리
- 📁 데이터 관리 및 검색
- ⚙️ 시스템 설정 확인

### 3. 데이터 처리

```bash
python scripts/process_data.py --max-files 100
```

HTML 파일을 정제된 텍스트 청크로 변환합니다.

### 4. 벡터 스토어 구축

```bash
python scripts/build_vectorstore.py
```

처리된 청크를 임베딩하여 ChromaDB에 저장합니다.

### 5. 사용자 챗봇 실행 (RAG 통합 완료!)

```bash
streamlit run user_chatbot.py --server.port 8502
```

사용자 챗봇 기능:
- 💬 대학 정보 질의응답 (RAG 기반)
- 🎓 입학, 학사, 생활 안내
- 📚 163개 문서에서 검색된 정보 기반 답변
- 🔗 출처 정보 표시

접속: http://localhost:8502

### 6. 지식베이스 업데이트 (예정)

```bash
python scripts/update_knowledge.py
```

## 프로젝트 구조

```
replace-infome/
├── config/                  # 설정 파일
├── data/                    # 데이터 저장소 (gitignored)
├── logs/                    # 로그 파일
├── src/                     # 소스 코드
│   ├── crawler/            # 웹 크롤링 모듈
│   ├── processor/          # 텍스트 처리 모듈
│   ├── vectorstore/        # 벡터 DB 모듈
│   ├── rag/                # RAG 파이프라인
│   ├── chatbot/            # 챗봇 인터페이스
│   └── utils/              # 유틸리티
├── scripts/                 # 실행 스크립트
├── tests/                   # 테스트 코드
└── requirements.txt        # Python 의존성
```

## 개발 상태

- [x] **Phase 1**: 기반 구축 및 기본 크롤러 ✅
  - URL 관리 시스템 (SQLite)
  - Playwright 기반 페이지 스크래퍼
  - 콘텐츠 추출기
  - 10페이지 테스트 크롤링 완료

- [x] **Phase 2**: 텍스트 처리 시스템 ✅
  - TextCleaner (텍스트 정제)
  - TextChunker (LangChain 기반 청킹)
  - MetadataManager (메타데이터 관리)
  - 163개 청크 생성 완료

- [x] **Phase 3**: 벡터 스토어 구축 ✅
  - Ollama 임베딩 서비스
  - ChromaDB 관리자
  - 163개 문서 임베딩 완료

- [x] **Phase 4**: RAG 파이프라인 ✅
  - 문서 검색기 (Retriever)
  - LLM 인터페이스 (Ollama llama3.1)
  - RAG 파이프라인 통합

- [x] **Phase 5**: 웹 UI ✅
  - 관리자 대시보드 (포트 8501)
  - 사용자 챗봇 (포트 8502)
  - RAG 통합 완료

- [ ] **Phase 6**: 전체 크롤링 및 최적화 (예정)
  - 비동기 크롤링
  - 게시판 페이지네이션
  - 전체 사이트 크롤링

- [ ] **Phase 7**: 업데이트 메커니즘 (예정)
  - 증분 크롤링
  - 자동 업데이트 스케줄러

- [ ] **Phase 8**: 테스트 및 개선 (예정)
  - 단위 테스트
  - 성능 최적화

## 라이선스

MIT

## 기여

기여는 언제나 환영합니다! Issue나 Pull Request를 열어주세요.
