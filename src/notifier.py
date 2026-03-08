"""
notifier.py - 텔레그램 봇으로 리포트 전송 (requests 직접 호출)
- 요약본: 텍스트 메시지로 전송
- 전체본: .md 파일을 Document로 첨부
"""

import os
import re
import logging
from datetime import datetime

import requests
import pytz
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
MAX_TEXT_LEN = 4000
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _tg_post(endpoint: str, **kwargs) -> dict:
    """Telegram Bot API POST 요청 (requests 사용)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{endpoint}"
    resp = requests.post(url, timeout=30, **kwargs)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API 오류: {data}")
    return data


def _build_summary(content: str) -> str:
    """Markdown 리포트에서 핵심 섹션만 추출"""
    lines = content.splitlines()
    summary_lines = []
    capture = False
    section_count = 0

    for line in lines:
        if line.startswith("## "):
            section_count += 1
            capture = True
            if section_count > 4:   # 미증시, 한국영향, 반도체시세, 전략 4섹션
                break
        if capture:
            if line.startswith("|") and "---|" in line:
                continue
            summary_lines.append(line)

    summary = "\n".join(summary_lines).strip()
    if len(summary) > MAX_TEXT_LEN:
        summary = summary[:MAX_TEXT_LEN] + "\n\n...(전체 리포트 파일 첨부)"
    return summary


def _md_to_html(text: str) -> str:
    """Markdown → Telegram HTML 변환"""
    result = []
    for line in text.splitlines():
        if line.startswith("## "):
            line = f"<b>{line[3:]}</b>"
        elif line.startswith("# "):
            line = f"<b>{line[2:]}</b>"
        elif line.startswith("### "):
            line = f"<b>{line[4:]}</b>"
        else:
            line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
            line = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)  # 링크 텍스트만
            line = line.replace("|", "│")
        result.append(line)
    return "\n".join(result)


def send_report(report_path: str) -> None:
    """리포트 파일을 텔레그램으로 전송"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        raise ValueError("TELEGRAM_BOT_TOKEN 미설정")
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "your_chat_id_here":
        raise ValueError("TELEGRAM_CHAT_ID 미설정")

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    kst = pytz.timezone("Asia/Seoul")
    now_str = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M")
    header = f"<b>📊 글로벌 투자 데일리 리포트</b>\n<i>{now_str} KST</i>\n\n"

    # 1) 요약 텍스트 전송
    summary_html = _md_to_html(_build_summary(content))
    _tg_post("sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": header + summary_html,
        "parse_mode": "HTML",
    })
    logger.info("요약 메시지 전송 완료")

    # 2) 전체 .md 파일 Document 첨부
    filename = os.path.basename(report_path)
    with open(report_path, "rb") as doc_file:
        _tg_post("sendDocument", data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": "📎 전체 리포트 (Markdown)",
        }, files={"document": (filename, doc_file, "text/markdown")})
    logger.info("전체 리포트 파일 전송 완료")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
    if not os.path.isdir(reports_dir) or not os.listdir(reports_dir):
        print("reports/ 에 리포트 파일이 없습니다.")
        sys.exit(1)
    latest = sorted(os.listdir(reports_dir))[-1]
    path = os.path.join(reports_dir, latest)
    print(f"전송 대상: {path}")
    send_report(path)
    print("전송 완료!")
