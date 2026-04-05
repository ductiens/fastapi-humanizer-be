from pydantic import BaseModel

class HumanizeTextRequest(BaseModel):
    text: str
    style: str # academic, creative, report, business
    intensity_level: str # light, medium, heavy
    language: str # vietnamese, english
    simulate_student: bool = False
