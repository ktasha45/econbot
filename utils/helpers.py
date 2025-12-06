import asyncio
import aiohttp
from config import HEADERS
import json
from datetime import datetime, timezone, timedelta
import os

async def fetch_html(session, url, encoding=None):
    """
    비동기로 URL의 HTML 텍스트를 가져옵니다.
    """
    try:
        async with session.get(url, headers=HEADERS, timeout=10) as response:
            if response.status == 200:
                if encoding:
                    return await response.text(encoding=encoding, errors='replace')
                else:
                    # 인코딩 자동 감지 시도 (utf-8 우선)
                    return await response.text(errors='replace')
    except Exception:
        pass
    return None

def load_sent_articles(file_path):
    if not os.path.exists(file_path):
        return set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        now_utc = datetime.now(timezone.utc)
        valid_links = set()
        
        for link, timestamp_str in data.items():
            timestamp_dt = datetime.fromisoformat(timestamp_str).astimezone(timezone.utc)
            if now_utc - timestamp_dt < timedelta(hours=24):
                valid_links.add(link)
        
        return valid_links
    except (json.JSONDecodeError, FileNotFoundError):
        return set()

def save_sent_articles(file_path, sent_links_with_time):
    # 24시간이 지난 데이터는 제거
    now_utc = datetime.now(timezone.utc)
    updated_data = {
        link: ts for link, ts in sent_links_with_time.items()
        if now_utc - datetime.fromisoformat(ts).astimezone(timezone.utc) < timedelta(hours=24)
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=4)
