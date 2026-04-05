from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.schemas.request import HumanizeTextRequest
from app.schemas.response import HumanizeResponse, HistoryRecordResponse
from app.services.gemini_service import humanize_full_text, chunk_text, humanize_text_chunk
from app.services.file_service import extract_text_from_pdf, extract_text_from_docx, create_docx_from_text
from app.db.repository import save_history_record, get_history_records, get_history_by_id
from app.services.auth_service import get_current_user, get_current_user_optional
from fastapi import Request
from datetime import datetime, timezone
import json
import asyncio
from typing import List

router = APIRouter(prefix="/api/v1", tags=["humanize"])

@router.post("/humanize", response_model=HumanizeResponse)
async def humanize_text_endpoint(request: HumanizeTextRequest):
    try:
        humanized = await humanize_full_text(
            text=request.text,
            style=request.style,
            intensity=request.intensity_level,
            language=request.language,
            simulate_student=request.simulate_student
        )
        
        record = {
            "original_text": request.text,
            "humanized_text": humanized,
            "style": request.style,
            "intensity_level": request.intensity_level,
            "language": request.language,
            "created_at": datetime.now(timezone.utc)
        }
        history_id = await save_history_record(record)
        
        return HumanizeResponse(
            success=True,
            original_text=request.text,
            humanized_text=humanized,
            history_id=history_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/humanize/stream")
async def humanize_stream_endpoint(request: HumanizeTextRequest, req: Request):
    username = get_current_user_optional(req)
    async def event_generator():
        try:
            chunks = chunk_text(request.text, max_chunk_size=6000)
            humanized_chunks = []
            for i, c in enumerate(chunks):
                # Send progress update
                progress = int((i / len(chunks)) * 100)
                yield f"data: {json.dumps({'type': 'progress', 'progress': progress})}\n\n"
                
                res = await humanize_text_chunk(c, request.style, request.intensity_level, request.language, request.simulate_student)
                humanized_chunks.append(res)
                
                # Yield partial string to UI if wanted, or just progress
                yield f"data: {json.dumps({'type': 'chunk', 'text': res})}\n\n"
                await asyncio.sleep(2)
                
            full_humanized = "\n\n".join(humanized_chunks)
            record = {
                "username": username,
                "original_text": request.text,
                "humanized_text": full_humanized,
                "style": request.style,
                "intensity_level": request.intensity_level,
                "language": request.language,
                "created_at": datetime.now(timezone.utc)
            }
            history_id = await save_history_record(record)
            
            # Send final response
            yield f"data: {json.dumps({'type': 'complete', 'humanized_text': full_humanized, 'history_id': history_id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
            
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
@router.post("/parse-file")
async def parse_file_endpoint(file: UploadFile = File(...)):
    try:
        content = await file.read()
        if file.filename.endswith(".pdf"):
            text = await extract_text_from_pdf(content)
        elif file.filename.endswith(".docx"):
            text = await extract_text_from_docx(content)
        else:
            raise HTTPException(status_code=400, detail="Mime type not supported. Use .pdf or .docx")
            
        return {"text": text, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/download")
async def download_docx(text: str = Form(...)):
    docx_stream = await create_docx_from_text(text)
    return StreamingResponse(
        docx_stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=humanized_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"}
    )

@router.get("/history", response_model=List[HistoryRecordResponse])
async def get_history_endpoint(user=Depends(get_current_user)):
    records = await get_history_records(user)
    return records

@router.get("/history/{history_id}/export")
async def export_history_docx(history_id: str):
    record = await get_history_by_id(history_id)
    if not record:
        raise HTTPException(status_code=404, detail="History record not found")
        
    docx_stream = await create_docx_from_text(record["humanized_text"])
    return StreamingResponse(
        docx_stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=humanized_{history_id}.docx"}
    )
