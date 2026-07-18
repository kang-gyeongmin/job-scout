"""Notion에 job-scout 공고 DB를 한 번 생성하는 스크립트.

사전 준비:
1. https://www.notion.so/my-integrations 에서 내부 통합(integration) 생성
   → 시크릿을 .env의 NOTION_TOKEN에 저장
2. DB를 둘 Notion 페이지를 하나 만들고, 페이지 우상단 ⋯ → 연결(Connections)에서
   방금 만든 통합을 초대
3. 그 페이지 URL 끝의 32자리 hex가 페이지 ID → .env의 NOTION_PARENT_PAGE_ID에 저장

실행:
    uv run python scripts/setup_notion.py

출력된 NOTION_DB_ID를 .env에 추가하면 다음 실행부터 자동으로 동기화된다.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.notion_sync import create_database


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    token = os.environ.get("NOTION_TOKEN", "").strip()
    parent = os.environ.get("NOTION_PARENT_PAGE_ID", "").strip()
    if not token or not parent:
        raise SystemExit(".env에 NOTION_TOKEN과 NOTION_PARENT_PAGE_ID를 먼저 "
                         "설정하세요 (파일 상단 독스트링 참고)")
    db_id = create_database(token, parent)
    print("데이터베이스 생성 완료. .env에 아래 줄을 추가하세요:")
    print(f"NOTION_DB_ID={db_id}")


if __name__ == "__main__":
    main()
