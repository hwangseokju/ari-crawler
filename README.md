# 아리텍 영업·경쟁사 크롤러

네이버 검색 API(뉴스·블로그·카페글)로 경쟁사 동향과 업계 뉴스를 자동 수집합니다.

---

## 폴더 구조

```
ari_crawler/
├── main.py              ← 실행 진입점
├── config.py            ← 키워드 설정 (여기만 수정해도 됨)
├── naver_api.py         ← 네이버 API 호출
├── database.py          ← SQLite 저장·신규 판별
├── report.py            ← HTML 리포트 생성
├── requirements.txt     ← 필수 라이브러리
├── .env.example         ← API 키 입력 템플릿
├── data/
│   └── crawler.db       ← 실행 후 자동 생성 (수집 이력)
└── reports/
    └── report_*.html    ← 실행할 때마다 생성
```

---

## 1. 최초 1회 설정

### 1-1. Python 설치

**Windows 기준**

1. https://www.python.org/downloads/ 에서 Python 3.11 이상 다운로드
2. 설치 시 **"Add Python to PATH" 체크 필수**
3. 설치 확인 (명령 프롬프트):
   ```
   python --version
   ```

### 1-2. 네이버 API 키 발급

1. https://developers.naver.com → 로그인
2. **Application → 애플리케이션 등록**
3. 애플리케이션 이름: 자유 (예: `아리텍크롤러`)
4. **사용 API**: **검색** 체크
5. 비로그인 오픈 API 서비스 환경: **WEB 설정** / URL: `http://localhost`
6. 등록 후 **내 애플리케이션** 메뉴에서 **Client ID** / **Client Secret** 복사

### 1-3. 라이브러리 설치

프로젝트 폴더에서 명령 프롬프트 열고:

```
pip install -r requirements.txt
```

### 1-4. API 키 입력

1. `.env.example` 파일을 복사 → 이름을 `.env` 로 변경
2. 메모장으로 열어 발급받은 값 입력:
   ```
   NAVER_CLIENT_ID=abcd1234EFGH5678
   NAVER_CLIENT_SECRET=ZyxwVutSrq
   ```

---

## 2. 실행

프로젝트 폴더에서:

```
python main.py
```

**실행되는 작업**

1. 네이버 검색 API로 경쟁사·기술·업계 키워드 17개 검색 (뉴스·블로그·카페)
2. 결과를 `data/crawler.db` 에 누적 저장 (이미 있는 URL 은 스킵)
3. `reports/report_YYYYMMDD_HHMMSS.html` 생성
4. 브라우저 자동으로 리포트 열림

**소요 시간**: 약 30초 ~ 1분

---

## 3. 키워드 수정

`config.py` 파일을 메모장으로 열어서 리스트를 수정하세요.

```python
COMPETITOR_KEYWORDS = [
    "귀뚜라미 환경테크",
    "엔백",
    "휴렉",
    "하이에나",
    "추가할_경쟁사",    # ← 이렇게 추가
]
```

---

## 4. 문제 해결

| 증상 | 원인 / 해결 |
|---|---|
| `.env 파일에 ... 이 없습니다` | `.env.example` 을 `.env` 로 이름 변경 안 했거나 값 입력 안 함 |
| `HTTP 401` | Client ID/Secret 오타 또는 검색 API 사용 설정 안 함 |
| `HTTP 429` | 일일 호출 한도 25,000회 초과 → 다음 날 재실행 |
| 한글 깨짐 | Windows 터미널에서 `chcp 65001` 입력 후 재실행 |
| `pip` 명령어 못 찾음 | Python 설치 시 PATH 체크 안 됨 → 재설치 |

---

## 5. 다음 단계 (예정)

- [ ] 카카오(Daum) 검색 추가
- [ ] 구글 뉴스 RSS 추가
- [ ] 서울시 1,213개 사업장명 자동 매칭
- [ ] 다른 지자체 정비사업 데이터 연동
- [ ] 매일/매주 자동 실행 (Windows 작업 스케줄러)
