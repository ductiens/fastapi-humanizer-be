import asyncio
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, PermissionDenied
from app.core.config import settings
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, RetryError
from app.prompts.base_template import BASE_PROMPT
import logging

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

# Free tier stable models (as of 2026). Ordered by preference.
# gemini-2.5-flash = preview, 403 on free/VN. gemini-1.5-* = deprecated 404.
MODEL_FALLBACK_CHAIN = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-8b",   # smallest/cheapest, highest RPM on free tier (1000 RPD, 15 RPM)
]

# Semaphore OUTSIDE retry — so retry releases the slot between attempts
_semaphore = asyncio.Semaphore(1)  # 1 request at a time, safest for free tier

def _get_model(model_name: str):
    return genai.GenerativeModel(model_name)

def chunk_text(text: str, max_chunk_size: int = 4000) -> list[str]:
    """Larger chunks = fewer API calls = less chance of hitting RPM/RPD limits."""
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
    wait=wait_exponential(multiplier=2, min=5, max=30),
    stop=stop_after_attempt(2),
    retry=retry_if_exception_type((ResourceExhausted, ServiceUnavailable)),
)
async def _call_model_once(model_name: str, prompt: str) -> str:
    """Single model call with retry. Semaphore is acquired OUTSIDE this function."""
    model = _get_model(model_name)
    response = await model.generate_content_async(prompt)
    return response.text

async def call_gemini_safe(prompt: str) -> str:
    """Acquire semaphore once, then try each model in fallback chain."""
    async with _semaphore:
        last_error = None
        for model_name in MODEL_FALLBACK_CHAIN:
            try:
                logger.info(f"Calling Gemini model: {model_name}")
                return await _call_model_once(model_name, prompt)
            except PermissionDenied as e:
                # 403: model not available for this key/region, skip immediately
                logger.warning(f"Model {model_name} → 403 Forbidden, skipping.")
                last_error = e
            except RetryError as e:
                logger.warning(f"Model {model_name} → rate limit exhausted after retries, trying next.")
                last_error = e
            except (ResourceExhausted, ServiceUnavailable) as e:
                logger.warning(f"Model {model_name} → {type(e).__name__}, trying next.")
                last_error = e
            except Exception as e:
                logger.error(f"Model {model_name} → unexpected error: {e}")
                last_error = e

    raise Exception(
        "Gemini API rate limit reached across all models. "
        "Please wait a few minutes and try again."
    )

async def humanize_text_chunk(chunk: str, style: str, intensity: str, language: str, simulate_student: bool = False) -> str:
    student_directive = ""
    if simulate_student:
        student_directive = (
            "GIA VỊ NGÔN NGỮ (STUDENT SIMULATION): Đừng tạo cảm giác 'đang giả dạng'. "
            "Hãy áp dụng lối hành văn tự do: thi thoảng lược bỏ chủ ngữ, gộp ý vội vàng, "
            "hoặc đảo trật tự từ để câu văn mang hơi thở đời thực, không quá nắn nót ngữ pháp."
        )
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
    # Larger chunks = fewer total requests
    chunks = chunk_text(text, max_chunk_size=4000)
    results = []
    for i, c in enumerate(chunks):
        res = await humanize_text_chunk(c, style, intensity, language, simulate_student)
        if simulate_student:
            res = apply_multipass_imperfections(res)
        results.append(res)
        # 5s gap between chunks — stays well under 15 RPM
        if i < len(chunks) - 1:
            await asyncio.sleep(5)
    return "\n\n".join(results)
