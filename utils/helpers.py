
import asyncio
import aiohttp
from config import HEADERS

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
