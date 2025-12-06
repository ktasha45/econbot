
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import trafilatura
from utils.helpers import fetch_html
from config import KST

def parse_thebell_date(date_str):
    """더벨 날짜 문자열 파싱"""
    try:
        parts = date_str.strip().split()
        if len(parts) != 3: return None
        date_part, ampm, time_part = parts
        hour, minute, second = map(int, time_part.split(':'))
        if ampm == "오후" and hour != 12: hour += 12
        elif ampm == "오전" and hour == 12: hour = 0
        dt_str = f"{date_part} {hour:02d}:{minute:02d}:{second:02d}"
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
    except Exception:
        return None

async def process_thebell_article(session, item, base_url, check_start_time_kst):
    """개별 더벨 기사를 처리하는 작업 단위"""
    try:
        date_tag = item.select_one('.userBox .date')
        if not date_tag: return None
        
        date_str = date_tag.text.strip()
        article_dt = parse_thebell_date(date_str)
        if not article_dt: return None
        
        if article_dt <= check_start_time_kst: return None
        
        a_tag = item.select_one('dl > a')
        if not a_tag: return None
        
        relative_link = a_tag['href']
        link = urljoin(base_url, relative_link)
        title = a_tag.select_one('dt').text.strip()
        summary = a_tag.select_one('dd').text.strip()

        full_html = await fetch_html(session, link, encoding='utf-8')
        full_content = ""
        
        if full_html:
            full_content = trafilatura.extract(full_html) or ""
            if len(full_content) < 50:
                try:
                    art_soup = BeautifulSoup(full_html, 'html.parser')
                    content_div = art_soup.select_one('.viewSection')
                    if content_div: full_content = content_div.text.strip()
                except: pass
        
        final_content = full_content if len(full_content) > 50 else summary
        
        cleanup_marker = "저작권자 ⓒ 자본시장 미디어 'thebell'"
        if cleanup_marker in final_content:
            final_content = final_content.split(cleanup_marker)[0].strip()
            
        return {
            'source': '더벨(The Bell)',
            'title': title,
            'link': link,
            'full_content': final_content,
            'published_at': article_dt
        }
    except:
        return None

async def get_thebell_news_async(session, check_start_time_kst):
    print(f"📡 [Start] 더벨(The Bell) 검색 중...") # 진행 상황 표시
    base_url = "https://www.thebell.co.kr/free/content/article.asp?svccode=00"
    
    try:
        html = await fetch_html(session, base_url, encoding='utf-8')
        if not html: return []
        
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.listBox > ul > li')
        
        tasks = [process_thebell_article(session, item, base_url, check_start_time_kst) for item in items]
        
        results = await asyncio.gather(*tasks)
        
        valid_results = [r for r in results if r is not None]
        return valid_results
        
    except Exception as e:
        print(f"The Bell Error: {e}")
        return []
