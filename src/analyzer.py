"""
analyzer.py - 수집 데이터 분석 및 Markdown 리포트 생성
구조: 어제 미 증시 요약 → 한국 시장 영향 → 오늘 투자 전략
"""

import os
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _arrow(val: float) -> str:
    return "▲" if val >= 0 else "▼"

def _sign(val: float) -> str:
    return f"+{val:.2f}" if val >= 0 else f"{val:.2f}"

def _emoji(val: float) -> str:
    if val >= 1.5:  return "🚀"
    if val >= 0.5:  return "📈"
    if val >= -0.5: return "➡️"
    if val >= -1.5: return "📉"
    return "🔴"

def _sentiment(sp500_pct: float, nasdaq_pct: float) -> tuple[str, str]:
    """미 증시 평균 등락률로 시장 심리 판단"""
    avg = (sp500_pct + nasdaq_pct) / 2
    if avg >= 1.0:
        return "강세 (Bullish)", "✅ 긍정적 외부 환경"
    elif avg >= 0.0:
        return "소폭 강세", "⚠️ 보합 수준의 외부 환경"
    elif avg >= -1.0:
        return "약세 (Bearish)", "⚠️ 다소 부정적 외부 환경"
    else:
        return "강한 약세 (Strong Bearish)", "🚨 부정적 외부 환경"

def _korea_impact(sp500_pct: float, usd_krw_chg_pct: float) -> str:
    """한국 시장 영향 텍스트 생성"""
    lines = []

    # 미국 증시 방향
    if sp500_pct >= 0.5:
        lines.append("- 미 증시 강세로 외국인 매수 유입 기대 → KOSPI **상승** 압력")
    elif sp500_pct <= -0.5:
        lines.append("- 미 증시 약세로 외국인 매도 가능성 → KOSPI **하락** 압력")
    else:
        lines.append("- 미 증시 보합으로 직접 영향 제한적")

    # 환율
    if usd_krw_chg_pct >= 0.5:
        lines.append("- 원화 약세(달러 강세) → 수출주 유리, 외국인 매도 압력 병존")
    elif usd_krw_chg_pct <= -0.5:
        lines.append("- 원화 강세(달러 약세) → 내수주 유리, 외국인 유입 가능성")
    else:
        lines.append("- 환율 안정적 → 환율 리스크 낮음")

    return "\n".join(lines)

def _semi_market_section(semi: dict) -> list[str]:
    """반도체 시세 섹션 생성"""
    lines = []
    lines.append("## 4️⃣ 전일 국제 반도체 시세")
    lines.append("")

    if not semi:
        lines.append("*데이터 수집 실패*")
        lines.append("")
        return lines

    # SOX 지수 별도 강조
    sox = semi.get("필라델피아반도체(SOX)")
    if sox:
        lines.append(
            f"**📡 필라델피아 반도체 지수 (SOX): "
            f"{sox['price']:,.2f}  {_emoji(sox['change_pct'])} {_sign(sox['change_pct'])}%**"
        )
        lines.append("")

    # 미국 종목
    lines.append("**🇺🇸 글로벌 반도체 주요 종목**")
    lines.append("")
    lines.append("| 종목 | 종가 | 등락 | 등락률 |")
    lines.append("|------|------|------|--------|")

    us_names = ["NVIDIA", "AMD", "인텔(Intel)", "TSMC", "퀄컴(Qualcomm)",
                "브로드컴(Broadcom)", "마이크론(Micron)", "ASML", "어플라이드머티리얼즈"]
    for name in us_names:
        d = semi.get(name)
        if d:
            lines.append(
                f"| {name} | ${d['price']:,.2f} | "
                f"{_arrow(d['change'])} {abs(d['change']):.2f} | "
                f"{_emoji(d['change_pct'])} {_sign(d['change_pct'])}% |"
            )

    lines.append("")
    lines.append("**🇰🇷 국내 반도체 종목**")
    lines.append("")
    lines.append("| 종목 | 종가 | 등락 | 등락률 |")
    lines.append("|------|------|------|--------|")

    kr_names = ["삼성전자", "SK하이닉스"]
    for name in kr_names:
        d = semi.get(name)
        if d:
            lines.append(
                f"| {name} | ₩{d['price']:,.0f} | "
                f"{_arrow(d['change'])} {abs(d['change']):.0f} | "
                f"{_emoji(d['change_pct'])} {_sign(d['change_pct'])}% |"
            )

    # 종합 시황 코멘트
    lines.append("")
    lines.append("**💬 반도체 시황 종합**")
    lines.append("")
    nvda = semi.get("NVIDIA", {})
    mu   = semi.get("마이크론(Micron)", {})
    hynix = semi.get("SK하이닉스", {})

    if nvda:
        if nvda["change_pct"] >= 2.0:
            lines.append(f"- NVIDIA {_sign(nvda['change_pct'])}% 강세 → AI 인프라 투자 확대 신호, HBM 수혜 기대 (SK하이닉스·삼성)")
        elif nvda["change_pct"] <= -2.0:
            lines.append(f"- NVIDIA {_sign(nvda['change_pct'])}% 약세 → AI 수요 우려 확산, 국내 HBM 공급사 단기 부정적")
        else:
            lines.append(f"- NVIDIA {_sign(nvda['change_pct'])}% 보합 → AI 칩 수요 현상 유지")

    if mu and mu.get("change_pct"):
        if mu["change_pct"] >= 2.0:
            lines.append(f"- 마이크론 {_sign(mu['change_pct'])}% 강세 → DRAM/NAND 업황 개선 신호, SK하이닉스·삼성전자 동반 수혜 가능")
        elif mu["change_pct"] <= -2.0:
            lines.append(f"- 마이크론 {_sign(mu['change_pct'])}% 약세 → 메모리 가격 하락 우려, 국내 반도체 주의 필요")

    lines.append("")
    return lines


def _semi_influencer_section(semi_news: list[dict]) -> list[str]:
    """반도체 영향력자 발언 및 영향 분석 섹션"""
    lines = []
    lines.append("## 5️⃣ 반도체 영향력자 발언 & 시장 영향 분석")
    lines.append("")

    if not semi_news:
        lines.append("*수집된 반도체 관련 뉴스가 없습니다.*")
        lines.append("")
        return lines

    # 영향력자 발언이 포함된 뉴스 우선 분류
    influencer_news = [n for n in semi_news if n.get("influencers")]
    general_news    = [n for n in semi_news if not n.get("influencers")]

    # ── 영향력자 발언 분석 ──
    if influencer_news:
        lines.append("### 🎙️ 주요 인사 발언 및 영향 분석")
        lines.append("")
        for item in influencer_news[:6]:
            lines.append(f"**[{item['source']}]** {item['title']}")
            for inf in item["influencers"][:2]:
                lines.append(f"> 👤 {inf}")

            # 자동 영향 분석
            impact = _analyze_semi_impact(item["title"] + " " + item["summary"])
            lines.append(f"> **📊 영향 분석:** {impact}")
            if item.get("link"):
                lines.append(f"> 🔗 [{item['link'][:60]}...]({item['link']})")
            lines.append("")

    # ── 반도체 일반 동향 뉴스 ──
    if general_news:
        lines.append("### 📡 반도체 산업 주요 동향")
        lines.append("")
        for item in general_news[:5]:
            lines.append(f"- **[{item['source']}]** [{item['title']}]({item['link']})")
        lines.append("")

    # ── 한국 반도체 영향 종합 의견 ──
    lines.append("### 🇰🇷 한국 반도체 산업 종합 의견")
    lines.append("")
    lines.append(_korea_semi_opinion(semi_news))
    lines.append("")

    return lines


def _analyze_semi_impact(text: str) -> str:
    """뉴스 텍스트 기반으로 반도체 시장 영향을 분석합니다."""
    text_lower = text.lower()

    # 긍정 시그널
    bullish_signals = [
        ("record", "실적 사상 최고 → 반도체 업황 피크 사이클 진입 가능성"),
        ("beat", "실적 어닝 서프라이즈 → 섹터 전반 밸류에이션 리레이팅 기대"),
        ("demand", "수요 확대 언급 → 공급사(삼성·SK하이닉스) 수혜 가능"),
        ("ai", "AI 투자 확대 시그널 → HBM·고부가 메모리 수혜 직결"),
        ("hbm", "HBM 수요·공급 언급 → SK하이닉스 직접 수혜 종목"),
        ("expansion", "생산 확장 계획 → 장비주(한미반도체 등) 동반 수혜"),
        ("partnership", "전략적 파트너십 → 공급망 다변화, 수혜 업체 모니터링"),
        ("data center", "데이터센터 투자 확대 → 메모리·AI칩 수요 직결"),
        ("guidance", "가이던스 상향 → 실적 모멘텀 강화, 섹터 긍정"),
    ]

    # 부정 시그널
    bearish_signals = [
        ("ban", "수출 규제·금지 조치 → 공급망 리스크 확대, 한국 수출 영향 점검"),
        ("export control", "대중 수출통제 강화 → 삼성·SK하이닉스 중국 매출 리스크"),
        ("sanction", "제재 조치 → 글로벌 공급망 재편 가속, 단기 불확실성"),
        ("inventory", "재고 과잉 우려 → 메모리 가격 하락 압력"),
        ("miss", "실적 미스 → 섹터 전반 센티먼트 악화"),
        ("cut", "투자·생산 축소 → 업황 피크아웃 신호"),
        ("tariff", "관세 부과 → 수출 의존도 높은 한국 반도체 직격"),
        ("oversupply", "공급 과잉 → ASP(평균판매가격) 하락 압력"),
        ("competition", "경쟁 심화 → 마진 압박 가능성"),
    ]

    for kw, analysis in bullish_signals:
        if kw in text_lower:
            return f"🟢 **긍정적** — {analysis}"

    for kw, analysis in bearish_signals:
        if kw in text_lower:
            return f"🔴 **부정적** — {analysis}"

    return "🟡 **중립** — 직접적 가격 영향 제한적. 추가 맥락 모니터링 권고"


def _korea_semi_opinion(semi_news: list[dict]) -> str:
    """수집된 반도체 뉴스 전체를 바탕으로 한국 반도체 산업 종합 의견 생성"""
    all_text = " ".join(
        (n["title"] + " " + n.get("summary", "")).lower()
        for n in semi_news
    )

    bullish_count = sum(1 for kw in [
        "record", "beat", "ai", "hbm", "demand", "expansion", "data center", "guidance"
    ] if kw in all_text)

    bearish_count = sum(1 for kw in [
        "ban", "export control", "sanction", "inventory", "miss", "cut", "tariff", "oversupply"
    ] if kw in all_text)

    lines = []
    if bullish_count > bearish_count:
        lines.append("**전반적 판단: 🟢 긍정 우세**")
        lines.append("- AI·HBM 수요 확대 기조 유지 → 삼성전자·SK하이닉스 실적 모멘텀 긍정적")
        lines.append("- NVIDIA 생태계 확장이 국내 메모리 공급사의 직접 수혜로 연결되는 구조 강화")
        lines.append("- 단기 트레이딩: SK하이닉스 > 삼성전자 (HBM 점유율 우위)")
    elif bearish_count > bullish_count:
        lines.append("**전반적 판단: 🔴 부정 우세**")
        lines.append("- 수출규제·재고 우려 등 외생 변수 부각 → 반도체 섹터 단기 리스크 관리 필요")
        lines.append("- 중국 매출 비중이 높은 삼성전자 상대적 취약, SK하이닉스 HBM 비중 방어막")
        lines.append("- 포지션 축소 또는 헤지 전략 검토 권고")
    else:
        lines.append("**전반적 판단: 🟡 중립**")
        lines.append("- 긍정·부정 시그널 혼재 → 방향성 불확실, 분할매수·관망 병행")
        lines.append("- NVIDIA 실적 발표, TSMC 월간 매출 등 주요 이벤트 모니터링 필수")
        lines.append("- 핵심 모니터링: HBM4 양산 일정, 중국 수출통제 추가 조치 여부")

    return "\n".join(lines)


def _strategy(sp500_pct: float, nasdaq_pct: float, vix: dict | None,
               gold: dict | None, oil: dict | None) -> str:
    """오늘의 투자 전략 텍스트"""
    lines = []
    avg = (sp500_pct + nasdaq_pct) / 2

    # VIX 공포지수 해석
    if vix:
        vix_val = vix["price"]
        if vix_val >= 30:
            lines.append(f"- 🚨 **VIX {vix_val:.1f}** — 시장 공포 극대화. 방어주·채권 비중 확대 고려")
        elif vix_val >= 20:
            lines.append(f"- ⚠️ **VIX {vix_val:.1f}** — 변동성 확대 구간. 포지션 축소 / 손절선 점검")
        else:
            lines.append(f"- ✅ **VIX {vix_val:.1f}** — 변동성 안정. 적극적 매수 가능 구간")

    # 금·원유
    if gold and gold["change_pct"] >= 1.0:
        lines.append(f"- 금 {_sign(gold['change_pct'])}% 상승 → 안전자산 선호 심리 강화")
    if oil:
        if oil["change_pct"] >= 2.0:
            lines.append(f"- 유가 {_sign(oil['change_pct'])}% 급등 → 에너지·정유주 수혜 기대")
        elif oil["change_pct"] <= -2.0:
            lines.append(f"- 유가 {_sign(oil['change_pct'])}% 급락 → 항공·화학주 수혜 기대")

    # 전반적 전략
    if avg >= 1.0:
        lines.append("- 📈 성장주·기술주 중심 매수 기회 모색")
        lines.append("- KODEX 200, 반도체·2차전지 ETF 관심")
    elif avg >= 0.0:
        lines.append("- ➡️ 단기 관망 또는 분할매수 전략 유지")
        lines.append("- 실적 개선 종목 중심 선별 접근")
    elif avg >= -1.0:
        lines.append("- 📉 리스크 관리 우선. 현금 비중 유지")
        lines.append("- 낙폭 과대 종목 저점 탐색 (단, 물타기 주의)")
    else:
        lines.append("- 🔴 전면 방어 전략. 신규 매수 자제")
        lines.append("- 인버스 ETF 또는 현금화 비중 확대 검토")

    return "\n".join(lines)


# ── 메인 분석 함수 ──────────────────────────────────────────────────────────

def analyze(data: dict) -> str:
    """
    fetcher.fetch_all() 결과를 받아 Markdown 리포트 문자열을 반환합니다.
    """
    market     = data.get("market", {})
    news       = data.get("news", [])
    semi       = data.get("semiconductor", {})
    semi_news  = data.get("semiconductor_news", [])

    kst  = pytz.timezone("Asia/Seoul")
    now  = datetime.now(kst)
    date_str = now.strftime("%Y년 %m월 %d일")
    file_date = now.strftime("%Y%m%d")

    sp500  = market.get("S&P500", {})
    nasdaq = market.get("나스닥", {})
    dow    = market.get("다우존스", {})
    usd_krw = market.get("원달러환율", {})
    kospi  = market.get("KOSPI", {})
    kosdaq = market.get("KOSDAQ", {})
    vix    = market.get("VIX", {})
    gold   = market.get("금", {})
    oil    = market.get("WTI유가", {})

    sp500_pct  = sp500.get("change_pct", 0.0)
    nasdaq_pct = nasdaq.get("change_pct", 0.0)
    usd_pct    = usd_krw.get("change_pct", 0.0)

    sentiment_label, sentiment_summary = _sentiment(sp500_pct, nasdaq_pct)

    # ── 리포트 본문 ────────────────────────────────────────────────────────────
    lines = []
    lines.append(f"# 📊 글로벌 투자 데일리 리포트")
    lines.append(f"**{date_str} (KST)** | 자동 생성")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. 미 증시 요약
    lines.append("## 1️⃣ 어제 미 증시 요약")
    lines.append("")
    lines.append(f"**시장 심리: {sentiment_label}**")
    lines.append("")
    lines.append("| 지수 | 종가 | 전일 대비 | 등락률 |")
    lines.append("|------|------|-----------|--------|")

    for label, d in [("S&P 500", sp500), ("나스닥", nasdaq), ("다우존스", dow)]:
        if d:
            lines.append(
                f"| {label} | {d['price']:,.2f} | "
                f"{_arrow(d['change'])} {abs(d['change']):.2f} | "
                f"{_emoji(d['change_pct'])} {_sign(d['change_pct'])}% |"
            )

    lines.append("")
    lines.append("**📌 주요 지표**")
    lines.append("")
    lines.append("| 지표 | 현재가 | 등락률 |")
    lines.append("|------|--------|--------|")

    for label, d in [("VIX (공포지수)", vix), ("금 (GC=F)", gold), ("WTI 유가", oil)]:
        if d:
            lines.append(
                f"| {label} | {d['price']:,.2f} | "
                f"{_emoji(d['change_pct'])} {_sign(d['change_pct'])}% |"
            )

    lines.append("")

    # 2. 한국 시장 영향
    lines.append("## 2️⃣ 한국 시장에 미치는 영향")
    lines.append("")
    lines.append("**환율 (원/달러)**")
    if usd_krw:
        lines.append(
            f"- 현재 **{usd_krw['price']:,.2f}원** "
            f"({_arrow(usd_krw['change'])} {abs(usd_krw['change']):.2f}원, "
            f"{_sign(usd_pct)}%)"
        )
    lines.append("")

    lines.append("**국내 지수 전일 종가**")
    lines.append("")
    lines.append("| 지수 | 종가 | 등락률 |")
    lines.append("|------|------|--------|")
    for label, d in [("KOSPI", kospi), ("KOSDAQ", kosdaq)]:
        if d:
            lines.append(
                f"| {label} | {d['price']:,.2f} | "
                f"{_emoji(d['change_pct'])} {_sign(d['change_pct'])}% |"
            )

    lines.append("")
    lines.append("**오늘 한국 시장 전망**")
    lines.append("")
    lines.append(sentiment_summary)
    lines.append("")
    lines.append(_korea_impact(sp500_pct, usd_pct))
    lines.append("")

    # 4. 반도체 시세
    lines.extend(_semi_market_section(semi))

    # 5. 반도체 영향력자 발언 분석
    lines.extend(_semi_influencer_section(semi_news))

    # 3. 오늘 투자 전략
    lines.append("## 3️⃣ 오늘의 투자 전략")
    lines.append("")
    lines.append(_strategy(sp500_pct, nasdaq_pct, vix, gold, oil))
    lines.append("")
    lines.append("> ⚠️ 본 리포트는 자동 생성된 참고 자료입니다. 투자 결정은 본인 책임 하에 이루어져야 합니다.")
    lines.append("")

    # 4. 글로벌 뉴스
    if news:
        lines.append("## 📰 글로벌 경제 뉴스")
        lines.append("")
        for item in news[:10]:
            lines.append(f"- **[{item['source']}]** [{item['title']}]({item['link']})")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated at {now.strftime('%Y-%m-%d %H:%M:%S')} KST*")

    return "\n".join(lines)


def save_report(content: str) -> str:
    """리포트를 reports/YYYYMMDD_report.md 로 저장하고 경로를 반환합니다."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    kst = pytz.timezone("Asia/Seoul")
    file_date = datetime.now(kst).strftime("%Y%m%d")
    path = os.path.join(REPORTS_DIR, f"{file_date}_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"리포트 저장 완료: {path}")
    return path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    logging.basicConfig(level=logging.INFO)
    from src.fetcher import fetch_all
    data = fetch_all()
    report = analyze(data)
    path  = save_report(report)
    print(f"\n리포트 저장: {path}")
    print("\n" + "="*60)
    print(report[:1000] + "...")
