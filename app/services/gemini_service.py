import asyncio
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, PermissionDenied
from app.core.config import settings
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, RetryError
from app.prompts.base_template import BASE_PROMPT
import logging
import random
import re

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

# Maximum temperature = maximum randomness in word selection = high perplexity
# This is the single most important setting for defeating AI detectors
GENERATION_CONFIG = genai.types.GenerationConfig(
    temperature=2.0,   # Max value — forces unpredictable word choices
    top_p=0.99,        # Near-full sampling — allows rare words
    top_k=80,          # Wide candidate pool
)

# Free tier stable models (as of 2026). Ordered by preference.
MODEL_FALLBACK_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
]

# Semaphore OUTSIDE retry — so retry releases the slot between attempts
_semaphore = asyncio.Semaphore(1)  # 1 request at a time, safest for free tier

def _get_model(model_name: str):
    return genai.GenerativeModel(model_name, generation_config=GENERATION_CONFIG)

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
    
    # Single pass — "retell from memory" approach
    prompt = BASE_PROMPT.format(
        style=style,
        intensity_level=intensity,
        language=language,
        student_directive=student_directive,
        text=chunk
    )
    return await call_gemini_safe(prompt)


# ===================================================================
# POST-PROCESSOR: Pure Python algorithms, NO AI, NO hardcoded phrases
# Works on ANY text in ANY language.
# ===================================================================

def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, preserving the delimiter."""
    # Match sentence-ending punctuation followed by whitespace
    parts = re.split(r'(?<=[.!?;])\s+', text.strip())
    return [p for p in parts if p.strip()]

def _measure_burstiness(sentences: list[str]) -> float:
    """Calculate coefficient of variation of sentence lengths.
    Human text: CV > 0.5 (varied lengths)
    AI text: CV < 0.35 (uniform lengths)
    """
    if len(sentences) < 2:
        return 1.0
    lengths = [len(s) for s in sentences]
    avg = sum(lengths) / len(lengths)
    if avg == 0:
        return 1.0
    variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
    return (variance ** 0.5) / avg

def _randomly_merge_sentences(sentences: list[str], count: int = 1) -> list[str]:
    """Merge {count} pairs of adjacent sentences to create longer ones."""
    result = list(sentences)
    merged = 0
    i = 0
    while i < len(result) - 1 and merged < count:
        # Pick candidates: both sentences should be below median length
        median_len = sorted([len(s) for s in result])[len(result) // 2]
        if len(result[i]) <= median_len and len(result[i+1]) <= median_len:
            connector = random.choice([" — ", "; ", ", "])
            s1 = result[i].rstrip('.!?;')
            s2 = result[i+1]
            # Lowercase first char of second sentence
            if s2 and s2[0].isupper():
                s2 = s2[0].lower() + s2[1:]
            result[i] = s1 + connector + s2
            result.pop(i + 1)
            merged += 1
            i += 2
        else:
            i += 1
    return result

def _randomly_split_sentence(sentences: list[str], count: int = 1) -> list[str]:
    """Split {count} long sentences at a natural comma point."""
    result = list(sentences)
    splits = 0
    avg_len = sum(len(s) for s in result) / max(len(result), 1)
    
    for i in range(len(result)):
        if splits >= count:
            break
        s = result[i]
        if len(s) > avg_len * 1.5:
            # Find commas
            comma_positions = [m.start() for m in re.finditer(r',\s', s)]
            if comma_positions:
                mid = len(s) // 2
                best = min(comma_positions, key=lambda p: abs(p - mid))
                part1 = s[:best].rstrip(',') + '.'
                part2 = s[best+1:].strip()
                if part2:
                    part2 = part2[0].upper() + part2[1:]
                    result[i] = part1
                    result.insert(i + 1, part2)
                    splits += 1
    return result

def _inject_punctuation_noise(text: str) -> str:
    """Randomly add/modify punctuation to break token-level patterns.
    - Swap some commas with em-dashes or semicolons
    - Add occasional ellipsis
    """
    chars = list(text)
    comma_indices = [i for i, c in enumerate(chars) if c == ',']
    
    if comma_indices:
        # Swap 1-2 random commas with different punctuation
        swap_count = min(2, len(comma_indices))
        chosen = random.sample(comma_indices, swap_count)
        for idx in chosen:
            replacement = random.choice([' —', ';'])
            chars[idx] = replacement
    
    return ''.join(chars)

def _vary_paragraph_breaks(text: str) -> str:
    """If text is one big block, split into 2-3 paragraphs at natural points.
    If text already has paragraphs, occasionally merge two short ones.
    """
    paragraphs = text.split('\n\n')
    
    if len(paragraphs) == 1:
        # Single block — split it
        sentences = _split_sentences(text)
        if len(sentences) >= 4:
            # Split at a random point in the middle third
            split_range = range(len(sentences) // 3, 2 * len(sentences) // 3)
            if split_range:
                split_at = random.choice(list(split_range))
                p1 = ' '.join(sentences[:split_at])
                p2 = ' '.join(sentences[split_at:])
                return p1 + '\n\n' + p2
    
    return text

def apply_multipass_imperfections(text: str) -> str:
    """
    Statistical post-processor — works on ANY text, ANY language.
    No hardcoded phrases. Pure algorithmic text manipulation.
    
    Strategy:
    1. Measure burstiness (sentence length variance)
    2. If too uniform → merge short sentences + split long ones
    3. Add punctuation noise (swap commas with dashes/semicolons)
    4. Vary paragraph structure
    """
    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return text
    
    cv = _measure_burstiness(sentences)
    
    # Determine how aggressively to intervene based on uniformity score
    if cv < 0.3:
        # Very uniform (strong AI signal) — heavy intervention
        merge_count = max(1, len(sentences) // 3)
        split_count = 1
    elif cv < 0.5:
        # Moderately uniform — light intervention
        merge_count = max(1, len(sentences) // 5)
        split_count = 1
    else:
        # Already varied — minimal intervention
        merge_count = 0
        split_count = 0
    
    if merge_count > 0:
        sentences = _randomly_merge_sentences(sentences, merge_count)
    if split_count > 0:
        sentences = _randomly_split_sentence(sentences, split_count)
    
    text = ' '.join(sentences)
    
    # Punctuation noise — always apply lightly
    text = _inject_punctuation_noise(text)
    
    # Paragraph structure variation
    text = _vary_paragraph_breaks(text)
    
    return text


async def humanize_full_text(text: str, style: str, intensity: str, language: str, simulate_student: bool = False) -> str:
    # Larger chunks = fewer total requests
    chunks = chunk_text(text, max_chunk_size=4000)
    results = []
    for i, c in enumerate(chunks):
        res = await humanize_text_chunk(c, style, intensity, language, simulate_student)
        # Always run post-processing to break AI patterns
        res = apply_multipass_imperfections(res)
        results.append(res)
        # 5s gap between chunks — stays well under 15 RPM
        if i < len(chunks) - 1:
            await asyncio.sleep(5)
    return "\n\n".join(results)
