#!/usr/bin/env python3
"""
main.py - 글로벌 투자 데일리 리포트 자동화 통합 실행
사용법: python main.py [--no-telegram]
"""

import sys
import os
import logging
import argparse
from datetime import datetime
import pytz

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from src.fetcher  import fetch_all
from src.analyzer import analyze, save_report
from src.notifier import send_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "logs", "report.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


def run(send_telegram: bool = True) -> str:
    """
    전체 파이프라인 실행:
      1. 데이터 수집 (fetcher)
      2. 분석 + 리포트 생성 (analyzer)
      3. 텔레그램 전송 (notifier)  ← --no-telegram 시 생략
    리포트 파일 경로를 반환합니다.
    """
    kst = pytz.timezone("Asia/Seoul")
    logger.info(f"=== 리포트 생성 시작: {datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S KST')} ===")

    # Step 1: 데이터 수집
    logger.info("[1/3] 시장 데이터 및 뉴스 수집 중...")
    data = fetch_all()

    # Step 2: 분석 및 리포트 저장
    logger.info("[2/3] 리포트 분석 및 생성 중...")
    report_content = analyze(data)
    report_path    = save_report(report_content)
    logger.info(f"      → 저장 완료: {report_path}")

    # Step 3: 텔레그램 전송
    if send_telegram:
        logger.info("[3/3] 텔레그램 전송 중...")
        try:
            send_report(report_path)
            logger.info("      → 전송 완료")
        except ValueError as e:
            logger.warning(f"      → 텔레그램 설정 미완료, 건너뜀: {e}")
        except Exception as e:
            logger.error(f"      → 전송 실패: {e}")
    else:
        logger.info("[3/3] 텔레그램 전송 건너뜀 (--no-telegram)")

    logger.info(f"=== 완료 ===")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="글로벌 투자 데일리 리포트 생성기")
    parser.add_argument(
        "--no-telegram", action="store_true",
        help="텔레그램 전송 없이 리포트만 생성"
    )
    args = parser.parse_args()

    # logs 디렉토리 보장
    os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)

    path = run(send_telegram=not args.no_telegram)

    print(f"\n✅ 리포트 생성 완료: {path}")
    if args.no_telegram:
        print("   (텔레그램 전송 생략됨 — 설정 후 --no-telegram 없이 실행하세요)")


if __name__ == "__main__":
    main()
