import os
import sys
from datetime import timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# 수집할 시간 범위 (시간 단위)
TIME_LIMIT_HOURS = 2

# 한국 시간(KST) 정의
KST = timezone(timedelta(hours=9))

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
    # {"name": "매경-경제", "url": "https://www.mk.co.kr/rss/30100041/"},
    # {"name": "매경-국제", "url": "https://www.mk.co.kr/rss/30300018/"},
    # {"name": "매경-기업경영", "url": "https://www.mk.co.kr/rss/50100032/"},
    # {"name": "매경-증권", "url": "https://www.mk.co.kr/rss/50200011/"},
    # {"name": "매경-부동산", "url": "https://www.mk.co.kr/rss/50300009/"},
]

# API 키 및 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    print("Error: API Key가 설정되지 않았습니다.")
    sys.exit(1)


# Gemini 모델 설정
GEMINI_MODEL = "gemini-flash-latest"

