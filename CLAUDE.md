# 글로벌 투자 데일리 리포트 자동화

한국 시장 대응형 일간 투자 리포트를 자동 생성하고 텔레그램으로 전송하는 파이프라인.

## 프로젝트 구조

```
investment-report/
├── main.py              # 통합 실행 진입점
├── requirements.txt     # Python 의존성
├── .env                 # 환경변수 (토큰 등) — .gitignore에 포함
├── .env.example         # 환경변수 템플릿
├── src/
│   ├── fetcher.py       # 시장 데이터 + 뉴스 수집 (yfinance, RSS)
│   ├── analyzer.py      # 데이터 분석 + Markdown 리포트 생성
│   └── notifier.py      # 텔레그램 봇 전송
├── reports/             # 생성된 리포트 저장 (YYYYMMDD_report.md)
└── logs/                # 실행 로그
```

## 빠른 시작

### 1. 텔레그램 봇 설정 (최초 1회)

1. 텔레그램에서 `@BotFather` 검색 → `/newbot` → 토큰 복사
2. `@userinfobot` 에 메시지 전송 → Chat ID 확인
3. `.env` 파일 편집:
   ```
   TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
   TELEGRAM_CHAT_ID=123456789
   ```

### 2. 리포트 생성 (Claude Code에서)

```
/generate-report
```

또는 터미널에서 직접:

```bash
cd /Users/sangchullee/Documents/investment-report
.venv/bin/python main.py
```

텔레그램 전송 없이 리포트만 생성:

```bash
.venv/bin/python main.py --no-telegram
```

## 리포트 구성

| 섹션 | 내용 |
|------|------|
| 1️⃣ 어제 미 증시 요약 | S&P500, 나스닥, 다우존스 + VIX, 금, 유가 |
| 2️⃣ 한국 시장 영향 | 원달러 환율, KOSPI/KOSDAQ + 전망 분석 |
| 3️⃣ 오늘 투자 전략 | VIX 기반 리스크 판단 + 섹터 전략 |
| 📰 글로벌 뉴스 | RSS 수집 경제 뉴스 (최대 10개) |

## 수집 지표

- **미국 증시**: S&P500 (`^GSPC`), 나스닥 (`^IXIC`), 다우존스 (`^DJI`)
- **한국 증시**: KOSPI (`^KS11`), KOSDAQ (`^KQ11`)
- **환율**: 원달러 (`KRW=X`)
- **리스크**: VIX (`^VIX`), 금 (`GC=F`), WTI 유가 (`CL=F`)

## 개별 모듈 테스트

```bash
# 데이터 수집 테스트
.venv/bin/python src/fetcher.py

# 리포트 생성 테스트 (텔레그램 없이)
.venv/bin/python src/analyzer.py

# 텔레그램 전송 테스트 (최신 리포트 기준)
.venv/bin/python src/notifier.py
```

## 자동화 (cron 예시)

매일 오전 7시 실행:

```cron
0 7 * * * cd /Users/sangchullee/Documents/investment-report && .venv/bin/python main.py >> logs/cron.log 2>&1
```
