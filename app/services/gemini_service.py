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
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
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

    if last_error:
        raise Exception(f"All models failed. Last error: {str(last_error)}")
    raise Exception("Model fallback chain failed without a specific error.")

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
    """
    Statistical post-processor — works on ANY text, ANY language.
    
    GPTZero detects AI primarily by measuring:
    1. Burstiness: variance in sentence lengths (AI = low variance = uniform)
    2. Perplexity: predictability of word sequences
    
    This function attacks #1 by analyzing sentence length distribution
    and forcibly breaking uniformity when detected.
    """
    import random
    import re
    
    # Split into sentences using regex (handles ., !, ?, and Vietnamese punctuation)
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(raw_sentences) < 3:
        return text  # Too short to meaningfully process
    
    lengths = [len(s) for s in raw_sentences]
    avg_len = sum(lengths) / len(lengths)
    
    # Calculate coefficient of variation (CV) — measure of uniformity
    # Human text typically has CV > 0.5; AI text often has CV < 0.3
    if avg_len > 0:
        variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
        std_dev = variance ** 0.5
        cv = std_dev / avg_len
    else:
        cv = 1.0  # skip processing
    
    # If CV is already high (varied), text looks human — skip heavy processing
    if cv > 0.5:
        return text
    
    # --- STRATEGY: Break uniformity ---
    result_sentences = list(raw_sentences)
    
    # Pass 1: Merge pairs of short consecutive sentences (creates long ones)
    i = 0
    merged_count = 0
    max_merges = max(1, len(result_sentences) // 4)  # merge at most 25%
    while i < len(result_sentences) - 1 and merged_count < max_merges:
        s1_len = len(result_sentences[i])
        s2_len = len(result_sentences[i + 1])
        # If both are short-to-medium, merge them
        if s1_len < avg_len * 1.2 and s2_len < avg_len * 1.2:
            connector = random.choice([" — ", "; ", ", và ", ", "])
            # Remove trailing period of first sentence before merging
            s1 = result_sentences[i].rstrip('.')
            s2_lower = result_sentences[i + 1][0].lower() + result_sentences[i + 1][1:]
            result_sentences[i] = s1 + connector + s2_lower
            result_sentences.pop(i + 1)
            merged_count += 1
            i += 2  # skip next to avoid chain merging
        else:
            i += 1
    
    # Pass 2: Split one long sentence into two shorter ones (creates short ones)
    split_done = False
    for i in range(len(result_sentences)):
        s = result_sentences[i]
        if len(s) > avg_len * 1.8 and not split_done:
            # Find a natural split point: comma followed by a conjunction or mid-point comma
            comma_positions = [m.start() for m in re.finditer(r',\s', s)]
            if comma_positions:
                # Pick a comma near the middle
                mid = len(s) // 2
                best_comma = min(comma_positions, key=lambda p: abs(p - mid))
                part1 = s[:best_comma].rstrip(',') + '.'
                part2 = s[best_comma + 1:].strip()
                if part2:
                    part2 = part2[0].upper() + part2[1:]
                result_sentences[i] = part1
                result_sentences.insert(i + 1, part2)
                split_done = True
    
    return ' '.join(result_sentences)

async def humanize_full_text(text: str, style: str, intensity: str, language: str, simulate_student: bool = False) -> str:
    # Larger chunks = fewer total requests
    chunks = chunk_text(text, max_chunk_size=4000)
    results = []
    for i, c in enumerate(chunks):
        res = await humanize_text_chunk(c, style, intensity, language, simulate_student)
        # Always run post-processing to scrub AI fingerprints
        res = apply_multipass_imperfections(res)
        results.append(res)
        # 5s gap between chunks — stays well under 15 RPM
        if i < len(chunks) - 1:
            await asyncio.sleep(5)
    return "\n\n".join(results)
