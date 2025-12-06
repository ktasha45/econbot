import asyncio
import aiohttp
import time
import sys
from datetime import datetime, timedelta, timezone
import logging
import json

# 설정 및 크롤러, 서비스 모듈 임포트
import config
from crawlers.rss import process_rss_feed
from crawlers.mk_opinion import process_mk_opinion
from crawlers.thebell import get_thebell_news_async
from services.gemini import summarize_text
from services.telegram import send_telegram_message
from utils.helpers import load_sent_articles, save_sent_articles

# Trafilatura 로깅 끄기
logging.getLogger('trafilatura').setLevel(logging.CRITICAL)

async def main():
    start_time = time.time()
    
    now_utc = datetime.now(timezone.utc)
    now_kst = datetime.now(config.KST)
    
    check_time_utc = now_utc - timedelta(hours=config.TIME_LIMIT_HOURS)
    check_time_kst = now_kst - timedelta(hours=config.TIME_LIMIT_HOURS)

    print(f"🚀 [{now_kst.strftime('%Y-%m-%d %H:%M:%S')}] 전체 뉴스 수집 시작 (최근 {config.TIME_LIMIT_HOURS}시간)\n")

    async with aiohttp.ClientSession() as session:
        tasks = []
        
        # RSS 피드 태스크 추가
        for feed in config.RSS_FEEDS:
            tasks.append(process_rss_feed(session, feed, check_time_utc))
            
        # 매경 오피니언 태스크 추가
        tasks.append(process_mk_opinion(session, check_time_kst))
        
        # 더벨 태스크 추가
        tasks.append(get_thebell_news_async(session, check_time_kst))

        all_results_grouped = await asyncio.gather(*tasks)

    flat_news_list = [news for group in all_results_grouped for news in group]

    # 수집된 기사 목록 내에서 링크를 기준으로 중복 제거
    print(f"\n- 중복 제거 전 기사 수: {len(flat_news_list)}")
    unique_articles = {}
    for article in flat_news_list:
        link = article.get('link')
        if link and link not in unique_articles:
            unique_articles[link] = article
    flat_news_list = list(unique_articles.values())
    print(f"- 중복 제거 후 기사 수: {len(flat_news_list)}")
    
    flat_news_list.sort(key=lambda x: x['published_at'], reverse=True)

    end_time = time.time()
    
    print(f"\n✅ [Complete] 모든 수집 완료")
    print(f"📊 총 {len(flat_news_list)}개의 뉴스를 수집했습니다. (소요시간: {end_time - start_time:.2f}초)")
    print(f"{'='*60}\n")

    return flat_news_list

if __name__ == "__main__":
    # 윈도우 환경 asyncio 정책 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Jupyter/Colab 환경 대응
    if 'ipykernel' in sys.modules or 'google.colab' in sys.modules:
        try:
            import nest_asyncio
            nest_asyncio.apply()
            articles = asyncio.run(main())
        except ImportError:
            loop = asyncio.get_event_loop()
            articles = loop.run_until_complete(main())
    else:
        articles = asyncio.run(main())

    # 전송된 기사 목록 로드 (링크만 포함된 set)
    sent_articles_file = "sent_articles.json"
    sent_links = load_sent_articles(sent_articles_file)

    # 새로운 기사만 필터링
    new_articles = [article for article in articles if article.get('link') not in sent_links]

    print(f"총 {len(articles)}개의 기사 중 {len(new_articles)}개의 새로운 기사를 처리합니다.")

    if not new_articles:
        print("새로운 기사가 없습니다.")
    else:
        # 전송된 기사 정보를 담을 딕셔너리 (기존 데이터 로드)
        try:
            with open(sent_articles_file, 'r', encoding='utf-8') as f:
                sent_articles_with_time = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            sent_articles_with_time = {}

        for article in new_articles:
            title = article.get('title', '제목 없음')
            link = article.get('link', '')
            content = article.get('full_content', '')
            
            if not content:
                continue
            
            raw_date = article.get('published_at')
            date_str = ""
            
            if isinstance(raw_date, datetime):
                date_str = raw_date.strftime('%Y년 %m월 %d일 %H:%M')
            else:
                date_str = str(raw_date) if raw_date else ""

            print(f"'{title}' 요약 중...")
            summary = summarize_text(content)

            message = f"[{article['source']}] {title}\n"
            if date_str:
                message += f"📅 {date_str}\n\n"
            else:
                message += "\n"
                
            message += f"{summary}\n\n"
            message += f"{link}"
            
            send_telegram_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, message)
            
            # 전송된 링크와 시간 추가
            sent_articles_with_time[link] = datetime.now(timezone.utc).isoformat()

        # 전송된 기사 목록 저장
        save_sent_articles(sent_articles_file, sent_articles_with_time)

    print("모든 작업이 완료되었습니다.")
