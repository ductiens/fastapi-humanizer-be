import asyncio
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from app.core.config import settings
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from app.prompts.base_template import BASE_PROMPT
import logging

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)
# Vừa phát hiện 'gemini-flash-latest' trỏ sang bản beta 'gemini-3-flash' có giới hạn siêu gắt 20 request / ngày. Xuống lại 2.5 flash.
model = genai.GenerativeModel('gemini-2.5-flash')

def chunk_text(text: str, max_chunk_size: int = 1500) -> list[str]:
    # Basic text chunking logic to avoid breaking sentences.
    # We split by double newlines (paragraphs) first
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    for p in paragraphs:
        if len(current_chunk) + len(p) < max_chunk_size:
            current_chunk += p + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = p + "\n\n"
    if current_chunk:
         chunks.append(current_chunk.strip())
    if not chunks:
        chunks = [text]
    return chunks

@retry(
    wait=wait_exponential(multiplier=1, min=5, max=30),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_type(ResourceExhausted)
)
async def call_gemini_with_retry(prompt: str) -> str:
    response = await model.generate_content_async(prompt)
    return response.text

async def call_gemini_safe(prompt: str) -> str:
    """Wrapper that converts RetryError/ResourceExhausted into clean exceptions."""
    from tenacity import RetryError
    try:
        return await call_gemini_with_retry(prompt)
    except RetryError as e:
        logger.error(f"Gemini rate limit exhausted after retries: {e}")
        raise Exception("Gemini API rate limit reached. Please wait a few minutes and try again.")
    except ResourceExhausted as e:
        logger.error(f"Gemini ResourceExhausted: {e}")
        raise Exception("Gemini API quota exceeded. Please try again later.")
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        raise e

async def humanize_text_chunk(chunk: str, style: str, intensity: str, language: str, simulate_student: bool = False) -> str:
    student_directive = ""
    if simulate_student:
        student_directive = "GIA VỊ NGÔN NGỮ (STUDENT SIMULATION): Đừng tạo cảm giác 'đang giả dạng'. Hãy áp dụng lối hành văn tự do: thi thoảng lược bỏ chủ ngữ, gộp ý vội vàng, hoặc đảo trật tự từ để câu văn mang hơi thở đời thực, không quá nắn nót ngữ pháp."
        
    prompt = BASE_PROMPT.format(
        style=style,
        intensity_level=intensity,
        language=language,
        student_directive=student_directive,
        text=chunk
    )
    result = await call_gemini_safe(prompt)
    return result

def apply_multipass_imperfections(text: str) -> str:
    # 2nd Pass: Regex based small tweaks to disrupt AI syntax predictability natively
    text = text.replace("Tuy nhiên,", "Mặc dù vậy,")
    text = text.replace("bởi vì", "do")
    return text

async def humanize_full_text(text: str, style: str, intensity: str, language: str, simulate_student: bool = False) -> str:
    # Khoảng 1500 token tương đương với ~6000 ký tự. Ta nới rộng chunk để gọi ít request hơn
    chunks = chunk_text(text, max_chunk_size=6000)
    results = []
    for c in chunks:
        # Gọi tuần tự để tránh lỗi ResourceExhausted do gọi song song chạm ngưỡng Limit free tier
        res = await humanize_text_chunk(c, style, intensity, language, simulate_student)
        
        # Áp dụng xử lý đa tầng (Multi-pass Engine 2)
        if simulate_student:
             res = apply_multipass_imperfections(res)
             
        results.append(res)
        # Chờ 2 giây trước khi gọi chunk tiếp theo
        await asyncio.sleep(2)
        
    return "\n\n".join(results)
