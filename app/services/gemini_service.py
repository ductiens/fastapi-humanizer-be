import asyncio
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, PermissionDenied
from app.core.config import settings
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, RetryError
from app.prompts.base_template import BASE_PROMPT
import logging

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

# Only stable free-tier models. 2.5-flash = preview (403 on free/VN region). 1.5-flash = deprecated (404).
MODEL_FALLBACK_CHAIN = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

# Global semaphore: max 2 concurrent Gemini requests to avoid self-spamming 429
_semaphore = asyncio.Semaphore(2)

def _get_model(model_name: str):
    return genai.GenerativeModel(model_name)

def chunk_text(text: str, max_chunk_size: int = 2000) -> list[str]:
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
    wait=wait_exponential(multiplier=1, min=2, max=20),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((ResourceExhausted, ServiceUnavailable)),
)
async def _call_model(model_name: str, prompt: str) -> str:
    async with _semaphore:
        model = _get_model(model_name)
        response = await model.generate_content_async(prompt)
        return response.text

async def call_gemini_safe(prompt: str) -> str:
    last_error = None
    for model_name in MODEL_FALLBACK_CHAIN:
        try:
            logger.info(f"Calling Gemini model: {model_name}")
            return await _call_model(model_name, prompt)
        except PermissionDenied as e:
            logger.warning(f"Model {model_name} returned 403, trying next. Error: {e}")
            last_error = e
        except RetryError as e:
            logger.warning(f"Model {model_name} rate limit exhausted, trying next.")
            last_error = e
        except (ResourceExhausted, ServiceUnavailable) as e:
            logger.warning(f"Model {model_name} unavailable, trying next. Error: {e}")
            last_error = e
        except Exception as e:
            logger.error(f"Unexpected error with model {model_name}: {e}")
            last_error = e

    raise Exception(
        f"All Gemini models failed. Last error: {last_error}. "
        "Please wait a few minutes and try again."
    )

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
    return await call_gemini_safe(prompt)

def apply_multipass_imperfections(text: str) -> str:
    text = text.replace("Tuy nhiên,", "Mặc dù vậy,")
    text = text.replace("bởi vì", "do")
    return text

async def humanize_full_text(text: str, style: str, intensity: str, language: str, simulate_student: bool = False) -> str:
    chunks = chunk_text(text, max_chunk_size=2000)
    results = []
    for i, c in enumerate(chunks):
        res = await humanize_text_chunk(c, style, intensity, language, simulate_student)
        if simulate_student:
            res = apply_multipass_imperfections(res)
        results.append(res)
        if i < len(chunks) - 1:
            await asyncio.sleep(4)
    return "\n\n".join(results)
