
import os
from google import genai
from google.genai import types

# Gemini 클라이언트 초기화
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY 환경 변수를 설정해주세요.")

client = genai.Client(api_key=api_key)

# Gemini 모델 설정
GEMINI_MODEL = "gemini-flash-latest"

GEMINI_INSTRUCTION = """
당신은 월스트리트의 유능한 펀드매니저입니다. 
​[지시문]
이 기사를 아래의 [작성 원칙]에 따라 요약해 주세요.
​[작성 원칙]
​형식: 서술형 줄글 대신, 핵심 내용 5~7개를 추려 개조식으로 나열하세요.
​구조: 각 문장 앞에 [주제 키워드]를 달아 내용을 직관적으로 분류하고, 번호를 매겨 나열하세요. (1. [xxx] xxx... 이런 식으로.)
​간결성: 조사와 미사여구는 배제하고, '명사형' 또는 '개조식 어미'로 간결하게 끝맺으세요. 문장 호흡이 너무 길어지지 않게 끊어주세요.
​데이터 활용 (중요): 추상적인 표현(예: "대폭 상승") 대신 **구체적인 수치(%, 금액, 기간 등)**를 포함하여 근거를 제시하세요.
​용어 사용: 경제/정치/시사 분야의 **통용 약어(YoY, QoQ, BP, YTD 등)**와 **전문 용어(매파/비둘기파, 숏커버링, 펀더멘털 등)**를 그대로 사용하여 문장의 정보 밀도를 높이세요.
긴 서술보다는 건조한(Dry) 톤을 유지하시고, 함축적인 한자어(예: 상승하다→상회, 지켜보다→관망, 걱정하다→우려)를 적극 사용하여 문장 길이를 압축하세요.
상승/하락/보합 등의 방향성은 텍스트 대신 **특수기호(↑, ↓, -)**를 적극 활용하여 직관성을 높이세요.
Markdown 태그(**, ## 등)는 일절 사용하지 말고 텍스트로만 출력하세요. ($\downarrow$ 같은 특이한 문법도 사용하지 마세요.)
"""

GEMINI_CONFIG = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_budget=0),
    system_instruction=GEMINI_INSTRUCTION
)

def summarize_text(full_text):
    prompt = f"""
    [기사 본문]
    {full_text}
    """
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL, contents=prompt, config=GEMINI_CONFIG,
        )
        return response.text

    except Exception as e:
        print(f"Gemini 요약 실패: {e}")
        return "요약을 생성하지 못했습니다."
