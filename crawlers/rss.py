
import asyncio
import feedparser
import trafilatura
from datetime import datetime, timezone
from utils.helpers import fetch_html
from config import KST

async def get_content_smartly(session, entry):
    """RSS 항목에서 본문을 추출합니다."""
    html = await fetch_html(session, entry.link)
    if html:
        try:
            extracted = trafilatura.extract(html)
            if extracted and len(extracted) > 50:
                return extracted
        except: pass
        
    if hasattr(entry, 'summary'):
        try:
            summary_extract = trafilatura.extract(entry.summary)
            return f"[요약] {summary_extract if summary_extract else entry.summary}"
        except:
            return f"[요약] {entry.summary}"
            
    return "본문 추출 실패"

async def process_rss_feed(session, feed_info, check_start_time):
    source_name = feed_info["name"]
    print(f"📡 [Start] RSS 검색 중: {source_name}") # 진행 상황 표시
    
    results = []
    try:
        xml_data = await fetch_html(session, feed_info["url"])
        if not xml_data: return []

        feed = feedparser.parse(xml_data)
        
        entries = feed.entries
        
        for entry in entries:
            if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                continue
                
            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            
            if pub_dt > check_start_time:
                content = await get_content_smartly(session, entry)
                results.append({
                    'source': source_name,
                    'title': entry.title,
                    'link': entry.link,
                    'published_at': pub_dt.astimezone(KST),
                    'full_content': content
                })
    except Exception as e:
        print(f"Error processing {source_name}: {e}")
        
    return results
