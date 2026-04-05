import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

router = APIRouter(prefix="/api/v1/analyze", tags=["analysis"])

class AnalyzeRequest(BaseModel):
    text: str

@router.post("/ai-score")
async def analyze_ai_score(request: AnalyzeRequest):
    # Sử dụng thuật toán Heuristic nội bộ thay vì gọi Gemini để tiết kiệm 100% API Quota
    text = request.text.lower()
    ai_phrases = [
        "cần lưu ý rằng", "tóm lại", "hơn nữa", "quan trọng là", "nhìn chung", 
        "vũ bão", "nòng cốt", "thách thức", "tối ưu hóa", "đóng vai trò quan trọng",
        "tapestry", "moreover", "in summary", "overall"
    ]
    phrase_count = sum(text.count(p) for p in ai_phrases)
    base_score = min(phrase_count * 20, 60)
    
    sentences = re.split(r'[.!?\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        score = 0
    else:
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
        if 15 <= avg_len <= 22:
            base_score += 15
        variance = sum((len(s.split()) - avg_len)**2 for s in sentences) / len(sentences)
        if variance < 15: 
            base_score += 20 # robotic variance
            
    score = min(max(base_score, 0), 98)
    return {"score": int(score)}

@router.post("/phrases")
async def analyze_phrases(request: AnalyzeRequest):
    text = request.text
    ai_phrases = [
        "It is worth noting", "Furthermore", "In conclusion", "Cần lưu ý rằng", 
        "Tóm lại", "Hơn nữa", "Quan trọng là", "Nhìn chung", "Overall", "delve into",
        "tapestry", "Moreover", "In summary"
    ]
    found = []
    lower_text = text.lower()
    for phrase in ai_phrases:
        idx = 0
        while True:
            idx = lower_text.find(phrase.lower(), idx)
            if idx == -1:
                break
            found.append({
                "phrase": text[idx:idx+len(phrase)],
                "start": idx,
                "end": idx + len(phrase)
            })
            idx += len(phrase)
    return {"phrases": found}
