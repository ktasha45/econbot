import asyncio
import aiohttp
import feedparser
import trafilatura
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
import logging
import time
import sys
import os
import requests
from google import genai
from datetime import datetime
from google.genai import types



# =========================================================
# [설정] 글로벌 변수
# =========================================================
# 수집할 시간 범위 (시간 단위)
TIME_LIMIT_HOURS = 0.5

# 한국 시간(KST) 정의
KST = timezone(timedelta(hours=9))

# Trafilatura 로깅 끄기 (콘솔 지저분함 방지)
logging.getLogger('trafilatura').setLevel(logging.CRITICAL)

# 브라우저 위장용 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.google.com/"
}

# RSS 주소 목록
RSS_FEEDS = [
    {"name": "한경-증권", "url": "https://www.hankyung.com/feed/finance"},
    {"name": "한경-경제", "url": "https://www.hankyung.com/feed/economy"},
    {"name": "한경-부동산", "url": "https://www.hankyung.com/feed/realestate"},
    {"name": "한경-국제", "url": "https://www.hankyung.com/feed/international"},
    {"name": "한경-오피니언", "url": "https://www.hankyung.com/feed/opinion"},
    {"name": "매경-경제", "url": "https://www.mk.co.kr/rss/30100041/"},
    {"name": "매경-국제", "url": "https://www.mk.co.kr/rss/30300018/"},
    {"name": "매경-기업경영", "url": "https://www.mk.co.kr/rss/50100032/"},
    {"name": "매경-증권", "url": "https://www.mk.co.kr/rss/50200011/"},
    {"name": "매경-부동산", "url": "https://www.mk.co.kr/rss/50300009/"},
]

# =========================================================
# [공통] 비동기 HTTP 요청 헬퍼
# =========================================================

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

# =========================================================
# 1. RSS 처리 로직
# =========================================================

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
        
        # 최신글부터 확인하기 위해 정렬 시도 (보통 RSS는 최신순임)
        entries = feed.entries
        
        for entry in entries:
            if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                continue
                
            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            
            # 시간 필터링
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

# =========================================================
# 2. 매경 오피니언 처리 로직
# =========================================================

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
                
                # 상세 페이지 접속
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

# =========================================================
# 3. 더벨(The Bell) 처리 로직 (고속 비동기 버전)
# =========================================================

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
        # 1. 날짜 확인 (목록에서)
        date_tag = item.select_one('.userBox .date')
        if not date_tag: return None
        
        date_str = date_tag.text.strip()
        article_dt = parse_thebell_date(date_str)
        if not article_dt: return None
        
        # 시간 필터링
        if article_dt <= check_start_time_kst: return None
        
        # 2. 정보 추출
        a_tag = item.select_one('dl > a')
        if not a_tag: return None
        
        relative_link = a_tag['href']
        link = urljoin(base_url, relative_link)
        title = a_tag.select_one('dt').text.strip()
        summary = a_tag.select_one('dd').text.strip()

        # 3. 상세 페이지 비동기 접속
        full_html = await fetch_html(session, link, encoding='utf-8')
        full_content = ""
        
        if full_html:
            full_content = trafilatura.extract(full_html) or ""
            # Fallback
            if len(full_content) < 50:
                try:
                    art_soup = BeautifulSoup(full_html, 'html.parser')
                    content_div = art_soup.select_one('.viewSection')
                    if content_div: full_content = content_div.text.strip()
                except: pass
        
        final_content = full_content if len(full_content) > 50 else summary
        
        # 불필요 문구 제거
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
        
        # 각 기사를 비동기 Task로 생성하여 병렬 처리
        tasks = [process_thebell_article(session, item, base_url, check_start_time_kst) for item in items]
        
        # 모든 Task 동시 실행
        results = await asyncio.gather(*tasks)
        
        # None 제외 (날짜 지난 것들)
        valid_results = [r for r in results if r is not None]
        return valid_results
        
    except Exception as e:
        print(f"The Bell Error: {e}")
        return []

# =========================================================
# 4. 메인 실행 함수 (통합)
# =========================================================

async def main():
    start_time = time.time()
    
    now_utc = datetime.now(timezone.utc)
    now_kst = datetime.now(KST)
    
    # 체크 기준 시간 설정
    check_time_utc = now_utc - timedelta(hours=TIME_LIMIT_HOURS)
    check_time_kst = now_kst - timedelta(hours=TIME_LIMIT_HOURS)

    print(f"🚀 [{now_kst.strftime('%Y-%m-%d %H:%M:%S')}] 전체 뉴스 수집 시작 (최근 {TIME_LIMIT_HOURS}시간)\n")

    async with aiohttp.ClientSession() as session:
        tasks = []
        
        # 1. RSS 피드 태스크 추가
        for feed in RSS_FEEDS:
            tasks.append(process_rss_feed(session, feed, check_time_utc))
            
        # 2. 매경 오피니언 태스크 추가
        tasks.append(process_mk_opinion(session, check_time_kst))
        
        # 3. 더벨 태스크 추가 (비동기 함수로 변경됨!)
        tasks.append(get_thebell_news_async(session, check_time_kst))

        # 모든 태스크 병렬 실행 및 대기
        all_results_grouped = await asyncio.gather(*tasks)

    # 결과 리스트 평탄화
    flat_news_list = [news for group in all_results_grouped for news in group]
    
    # 최신순 정렬
    flat_news_list.sort(key=lambda x: x['published_at'], reverse=True)

    end_time = time.time()
    
    print(f"\n✅ [Complete] 모든 수집 완료")
    print(f"📊 총 {len(flat_news_list)}개의 뉴스를 수집했습니다. (소요시간: {end_time - start_time:.2f}초)")
    print(f"{'='*60}\n")

    return flat_news_list

    # 결과 출력
    # for news in flat_news_list:
    #     pub_str = news['published_at'].strftime('%H:%M')
    #     content_len = len(news.get('full_content', ''))
        
    #     print(f"[{news['source']} | {pub_str}] {news['title']}")
    #     print(f"🔗 링크: {news['link']}")
    #     print(f"📝 본문 길이: {content_len:,}자")  # 글자수만 출력
    #     print(news.get('full_content', '')[:500])
    #     print("-" * 40)

    # if len(flat_news_list) == 0:
    #     print(">>> 지정된 시간 내에 업데이트된 뉴스가 없습니다.")

    # print(flat_news_list)

# =========================================================
# 5. 실행 환경 호환성 코드
# =========================================================
if __name__ == "__main__":
    # 윈도우 환경 asyncio 정책 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Jupyter/Colab 환경 대응
    if 'ipykernel' in sys.modules or 'google.colab' in sys.modules:
        try:
            import nest_asyncio
            nest_asyncio.apply()
            articles=asyncio.run(main())
        except ImportError:
            # nest_asyncio가 없으면 await로 실행 (Jupyter 구버전 등)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
    else:
        # 일반 파이썬 실행
        articles=asyncio.run(main())


# 1. API 키 및 설정 (환경변수에서 가져오도록 설정 - 보안 필수!)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    print("Error: API Key가 설정되지 않았습니다.")
    sys.exit(1)

# Gemini 클라이언트 설정
client = genai.Client(api_key=GEMINI_API_KEY)


model = "gemini-flash-latest"


ins="""
당신은 월스트리트의 유능한 펀드매니저입니다. 
​[지시문]
이 기사를 아래의 [작성 원칙]에 따라 요약해 주세요.
​[작성 원칙]
​형식: 서술형 줄글 대신, 핵심 내용 5~7개를 추려 개조식으로 나열하세요.
​구조: 각 문장 앞에 [주제 키워드]를 달아 내용을 직관적으로 분류하고, 번호를 매겨 나열하세요.
​간결성: 조사와 미사여구는 배제하고, '명사형' 또는 '개조식 어미'로 간결하게 끝맺으세요. 문장 호흡이 너무 길어지지 않게 끊어주세요.
​데이터 활용 (중요): 추상적인 표현(예: "대폭 상승") 대신 **구체적인 수치(%, 금액, 기간 등)**를 포함하여 근거를 제시하세요.
​용어 사용: 경제/정치/시사 분야의 **통용 약어(YoY, QoQ, BP, YTD 등)**와 **전문 용어(매파/비둘기파, 숏커버링, 펀더멘털 등)**를 그대로 사용하여 문장의 정보 밀도를 높이세요.
긴 서술보다는 건조한(Dry) 톤을 유지하시고, 함축적인 한자어(예: 상승하다→상회, 지켜보다→관망, 걱정하다→우려)를 적극 사용하여 문장 길이를 압축하세요.
상승/하락/보합 등의 방향성은 텍스트 대신 **특수기호(↑, ↓, -)**를 적극 활용하여 직관성을 높이세요.
Markdown 태그(**, ## 등)는 일절 사용하지 말고 텍스트로만 출력하세요.
"""

config=types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_budget=0),
    system_instruction=ins
)


# 2. 텔레그램 메시지 전송 함수
def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # parse_mode를 삭제하여 일반 텍스트로 보냅니다.
    # 이렇게 하면 AI가 어떤 특수문자를 뱉어도 에러가 나지 않습니다.
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
        # "parse_mode":"markdown",
    }
    
    try:
        response = requests.post(url, json=payload)
        
        # 만약 또 에러가 난다면, 텔레그램이 보내준 구체적인 이유를 출력합니다.
        if response.status_code != 200:
            print(f"전송 실패 원인: {response.text}")
            
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")
        return False

# ... (나머지 코드는 동일) ...


# 3. Gemini 요약 함수
def summarize_text(full_text):
    prompt = f"""
    [기사 본문]
    {full_text}
    """
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest", contents=prompt, config=config,
        )
        return response.text

    except Exception as e:
        print(f"Gemini 요약 실패: {e}")
        return "요약을 생성하지 못했습니다."


# ==========================================
# 4. 메인 로직 실행
# ==========================================

print(f"총 {len(articles)}개의 기사를 처리합니다.")

for article in articles:
    title = article.get('title', '제목 없음')
    link = article.get('link', '')
    content = article.get('full_content', '')
    
    if not content:
        continue # 본문이 없으면 건너뜀
    
    raw_date = article.get('published_at')
    date_str = ""
    
    if isinstance(raw_date, datetime):
        # 원하는 형식으로 변환 (예: 2025년 12월 06일 00:36)
        date_str = raw_date.strftime('%Y년 %m월 %d일 %H:%M')
    else:
        # 날짜 데이터가 없거나 형식이 다를 경우 대비
        date_str = str(raw_date) if raw_date else ""

    if not content:
        continue 
    
    # 1) Gemini에게 요약 요청
    print(f"'{title}' 요약 중...")
    summary = summarize_text(content)

    # 2) 텔레그램 메시지 포맷팅
    # [수정] 제목 아래에 날짜를 추가했습니다.
    message = f"[{article['source']}] {title}\n"
    if date_str:
        message += f"📅 {date_str}\n\n" # 날짜 출력
    else:
        message += "\n"
        
    message += f"{summary}\n\n"
    message += f"{link}"
    
    # 3) 텔레그램 전송
    send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)


print("모든 작업이 완료되었습니다.")
