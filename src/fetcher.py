"""
fetcher.py - 글로벌 시장 데이터 및 뉴스 수집
"""

import yfinance as yf
import feedparser
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import logging

logger = logging.getLogger(__name__)

# 주요 지수 티커
TICKERS = {
    "S&P500":     "^GSPC",
    "나스닥":     "^IXIC",
    "다우존스":   "^DJI",
    "원달러환율": "KRW=X",
    "KOSPI":      "^KS11",
    "KOSDAQ":     "^KQ11",
    "VIX":        "^VIX",
    "금":         "GC=F",
    "WTI유가":    "CL=F",
}

# 국제 반도체 주요 종목 (글로벌 + 한국)
SEMICONDUCTOR_TICKERS = {
    # 미국
    "필라델피아반도체(SOX)": "^SOX",
    "NVIDIA":               "NVDA",
    "AMD":                  "AMD",
    "인텔(Intel)":           "INTC",
    "TSMC":                 "TSM",
    "퀄컴(Qualcomm)":        "QCOM",
    "브로드컴(Broadcom)":    "AVGO",
    "마이크론(Micron)":      "MU",
    "ASML":                 "ASML",
    "어플라이드머티리얼즈":  "AMAT",
    # 한국
    "삼성전자":              "005930.KS",
    "SK하이닉스":            "000660.KS",
}

# 반도체 산업 영향력자 키워드
SEMI_INFLUENCERS = {
    "Jensen Huang":    "NVIDIA CEO — AI GPU 수요 및 데이터센터 전략의 핵심 결정자",
    "Lisa Su":         "AMD CEO — GPU/CPU 시장 점유율 및 MI300 AI칩 경쟁력",
    "Pat Gelsinger":   "Intel CEO — IDM 2.0 파운드리 전략 및 선단공정 로드맵",
    "C.C. Wei":        "TSMC CEO — 선단 파운드리 가격·생산능력 결정자",
    "Mark Liu":        "TSMC 회장 — 지정학적 반도체 공급망 발언",
    "Gina Raimondo":   "미 상무장관 — 대중 반도체 수출규제 정책",
    "Jensen":          "Jensen Huang 약칭",
    "NVIDIA CEO":      "NVIDIA 최고경영자 발언",
    "TSMC":            "파운드리 공급망 핵심 플레이어",
    "HBM":             "고대역폭메모리 — SK하이닉스·삼성 핵심 제품군",
    "export control":  "미 반도체 수출규제 동향",
    "chip ban":        "대중 반도체 제재",
    "AI chip":         "AI 반도체 수요 동향",
}

# 글로벌 경제 뉴스 RSS 피드
RSS_FEEDS = [
    {"name": "Reuters Markets",  "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"name": "Bloomberg Markets","url": "https://feeds.bloomberg.com/markets/news.rss"},
    {"name": "Investing.com",    "url": "https://www.investing.com/rss/news_25.rss"},
    {"name": "Yahoo Finance",    "url": "https://finance.yahoo.com/news/rssindex"},
]

# 반도체 전문 RSS 피드
SEMI_RSS_FEEDS = [
    {"name": "Reuters Tech",   "url": "https://feeds.reuters.com/reuters/technologyNews"},
    {"name": "EE Times",       "url": "https://www.eetimes.com/feed/"},
    {"name": "Tom's Hardware", "url": "https://www.tomshardware.com/feeds/all"},
    {"name": "Yahoo Finance",  "url": "https://finance.yahoo.com/news/rssindex"},
    {"name": "Seeking Alpha",  "url": "https://seekingalpha.com/feed.xml"},
]

# 반도체 뉴스 필터 키워드
SEMI_KEYWORDS = [
    "semiconductor", "chip", "NVIDIA", "AMD", "Intel", "TSMC", "Samsung",
    "SK Hynix", "HBM", "AI chip", "GPU", "foundry", "wafer", "export control",
    "Jensen Huang", "Lisa Su", "C.C. Wei", "Micron", "ASML", "Qualcomm",
    "반도체", "엔비디아", "삼성전자", "하이닉스",
]


def _parse_feed_time(entry) -> datetime | None:
    """RSS entry의 published 시간을 UTC datetime으로 파싱"""
    import email.utils
    published = entry.get("published", "") or entry.get("updated", "")
    if not published:
        return None
    try:
        # RFC 2822 포맷 (RSS 표준)
        tt = email.utils.parsedate_tz(published)
        if tt:
            timestamp = email.utils.mktime_tz(tt)
            return datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.utc)
    except Exception:
        pass
    return None


def fetch_market_data() -> dict:
    """
    주요 지표를 수집합니다. 시간봉(1h)으로 최신 가격 반영.
    반환값: {티커명: {price, change, change_pct, prev_close, ...}}
    """
    result = {}
    kst = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(kst)

    for name, ticker in TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            # 시간봉 5일치 → 최신 가격 + 전일 종가 비교
            hist = t.history(period="5d", interval="1h")

            if hist.empty or len(hist) < 2:
                # 시간봉 실패 시 일봉 fallback
                hist = t.history(period="5d")
                if hist.empty or len(hist) < 2:
                    logger.warning(f"{name}({ticker}) 데이터 없음")
                    continue

            latest = hist.iloc[-1]

            # 전일 종가: 오늘 날짜와 다른 마지막 봉
            latest_date = hist.index[-1].date()
            prev_bars = hist[hist.index.date < latest_date]
            if prev_bars.empty:
                prev_close = hist.iloc[-2]["Close"]
            else:
                prev_close = prev_bars.iloc[-1]["Close"]

            close      = latest["Close"]
            change     = close - prev_close
            change_pct = (change / prev_close) * 100

            result[name] = {
                "ticker":      ticker,
                "price":       round(close, 2),
                "prev_close":  round(prev_close, 2),
                "change":      round(change, 2),
                "change_pct":  round(change_pct, 2),
                "high":        round(latest["High"], 2),
                "low":         round(latest["Low"], 2),
                "volume":      int(latest["Volume"]),
                "date":        hist.index[-1].strftime("%Y-%m-%d %H:%M"),
            }
            logger.info(f"{name}: {close:.2f} ({change_pct:+.2f}%)")

        except Exception as e:
            logger.error(f"{name}({ticker}) 수집 실패: {e}")

    return result


def fetch_news(max_per_feed: int = 5, hours: int = 6) -> list[dict]:
    """
    RSS 피드에서 최신 글로벌 경제 뉴스를 수집합니다.
    hours: 최근 N시간 이내 뉴스만 포함 (시간 필터)
    """
    news_list = []
    cutoff = datetime.now(pytz.utc) - timedelta(hours=hours)

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            count = 0
            for entry in feed.entries:
                if count >= max_per_feed:
                    break
                pub_time = _parse_feed_time(entry)
                # 시간 파싱 실패 시 포함, 성공 시 cutoff 이후만 포함
                if pub_time and pub_time < cutoff:
                    continue
                news_list.append({
                    "source":    feed_info["name"],
                    "title":     entry.get("title", ""),
                    "link":      entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "pub_time":  pub_time,
                    "summary":   entry.get("summary", "")[:200],
                })
                count += 1
            logger.info(f"{feed_info['name']}: {count}개 뉴스 수집 (최근 {hours}h)")
        except Exception as e:
            logger.warning(f"{feed_info['name']} RSS 실패: {e}")

    # 중복 제거 + 최신순 정렬
    seen = set()
    unique_news = []
    for item in news_list:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique_news.append(item)

    unique_news.sort(
        key=lambda x: x["pub_time"] if x["pub_time"] else datetime.min.replace(tzinfo=pytz.utc),
        reverse=True
    )
    return unique_news


def fetch_semiconductor_data() -> dict:
    """국제 반도체 주요 종목 시세를 수집합니다. (시간봉 사용)"""
    result = {}
    for name, ticker in SEMICONDUCTOR_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", interval="1h")
            if hist.empty or len(hist) < 2:
                hist = t.history(period="5d")
                if hist.empty or len(hist) < 2:
                    logger.warning(f"반도체 {name}({ticker}) 데이터 없음")
                    continue

            latest = hist.iloc[-1]
            latest_date = hist.index[-1].date()
            prev_bars = hist[hist.index.date < latest_date]
            prev_close = prev_bars.iloc[-1]["Close"] if not prev_bars.empty else hist.iloc[-2]["Close"]

            close      = latest["Close"]
            change     = close - prev_close
            change_pct = (change / prev_close) * 100

            result[name] = {
                "ticker":     ticker,
                "price":      round(close, 2),
                "prev_close": round(prev_close, 2),
                "change":     round(change, 2),
                "change_pct": round(change_pct, 2),
                "high":       round(latest["High"], 2),
                "low":        round(latest["Low"], 2),
                "date":       hist.index[-1].strftime("%Y-%m-%d %H:%M"),
            }
            logger.info(f"  반도체 {name}: {close:.2f} ({change_pct:+.2f}%)")
        except Exception as e:
            logger.error(f"반도체 {name}({ticker}) 수집 실패: {e}")
    return result


def fetch_semiconductor_news(max_per_feed: int = 8, hours: int = 8) -> list[dict]:
    """
    반도체 전문 RSS 뉴스 수집. hours 이내 뉴스만 포함.
    """
    raw_items = []
    cutoff = datetime.now(pytz.utc) - timedelta(hours=hours)

    for feed_info in SEMI_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            count = 0
            for entry in feed.entries:
                if count >= max_per_feed * 3:
                    break
                pub_time = _parse_feed_time(entry)
                if pub_time and pub_time < cutoff:
                    continue
                raw_items.append({
                    "source":    feed_info["name"],
                    "title":     entry.get("title", ""),
                    "link":      entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "pub_time":  pub_time,
                    "summary":   entry.get("summary", "")[:300],
                })
                count += 1
            logger.info(f"반도체뉴스 {feed_info['name']}: {count}개 원시 수집")
        except Exception as e:
            logger.warning(f"반도체뉴스 {feed_info['name']} RSS 실패: {e}")

    # 반도체 관련 키워드 필터링 + 최신순 정렬
    filtered = []
    seen = set()
    for item in raw_items:
        combined = (item["title"] + " " + item["summary"]).lower()
        if any(kw.lower() in combined for kw in SEMI_KEYWORDS):
            if item["title"] not in seen:
                seen.add(item["title"])
                matched_influencers = [
                    f"{name} ({desc})"
                    for name, desc in SEMI_INFLUENCERS.items()
                    if name.lower() in combined
                ]
                item["influencers"] = matched_influencers
                filtered.append(item)

    filtered.sort(
        key=lambda x: x["pub_time"] if x["pub_time"] else datetime.min.replace(tzinfo=pytz.utc),
        reverse=True
    )
    logger.info(f"반도체 뉴스 필터링 완료: {len(filtered)}개 (최근 {hours}h)")
    return filtered[:20]


def fetch_all() -> dict:
    """fetcher 통합 진입점"""
    logger.info("=== 시장 데이터 수집 시작 ===")
    market    = fetch_market_data()
    news      = fetch_news()
    semi      = fetch_semiconductor_data()
    semi_news = fetch_semiconductor_news()
    logger.info(f"수집 완료: 지표 {len(market)}개, 반도체종목 {len(semi)}개, 뉴스 {len(news)}개, 반도체뉴스 {len(semi_news)}개")
    return {"market": market, "news": news, "semiconductor": semi, "semiconductor_news": semi_news}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_all()
    print("\n[시장 데이터]")
    for name, v in data["market"].items():
        print(f"  {name:10s}: {v['price']:>10.2f}  ({v['change_pct']:+.2f}%)  [{v['date']}]")
    print(f"\n[반도체 종목] {len(data['semiconductor'])}개")
    for name, v in data["semiconductor"].items():
        print(f"  {name:15s}: {v['price']:>10.2f}  ({v['change_pct']:+.2f}%)")
    print(f"\n[반도체 뉴스] {len(data['semiconductor_news'])}개")
    for n in data["semiconductor_news"][:3]:
        print(f"  [{n['source']}] {n['title'][:70]}")
