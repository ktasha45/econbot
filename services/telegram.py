
import requests

def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            print(f"전송 실패 원인: {response.text}")
            
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")
        return False
