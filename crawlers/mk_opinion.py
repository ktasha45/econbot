
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import trafilatura
from utils.helpers import fetch_html
from config import KST

def parse_mk_date_str(date_text):
    try:
        return datetime.strptime(date_text.strip().replace('.', '-'), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
    except:
        return None

async def process_mk_opinion(session, check_start_time_kst):
    print(f"📡 [Start] 매경 오피니언 검색 중...") # 진행 상황 표시
    results = []
    base_url = "https://www.mk.co.kr/opinion/"
    
    try:
        html = await fetch_html(session, base_url)
        if not html: return []

        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('a.news_item')

        for item in items:
            try:
                link = urljoin("https://www.mk.co.kr", item['href'])
                title_tag = item.select_one('.news_ttl')
                title = title_tag.text.strip() if title_tag else "제목 없음"
                
                sub_html = await fetch_html(session, link)
                if not sub_html: continue
                sub_soup = BeautifulSoup(sub_html, 'html.parser')
                
                date_area = sub_soup.select_one('.registration dd') or sub_soup.select_one('.news_input_time')
                if not date_area: continue
                
                article_dt = parse_mk_date_str(date_area.text)
                if not article_dt or article_dt <= check_start_time_kst: continue

                content = trafilatura.extract(sub_html)
                if not content:
                    body = sub_soup.select_one('.news_cnt_detail_wrap')
                    content = body.text.strip() if body else "본문 실패"

                results.append({
                    'source': '매경-오피니언',
                    'title': title,
                    'link': link,
                    'published_at': article_dt,
                    'full_content': content
                })
            except: continue
    except Exception as e:
        print(f"MK Opinion Error: {e}")
        
    return results
