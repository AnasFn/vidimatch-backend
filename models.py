from pydantic import BaseModel
from typing import List

class VideoAnalysisRequest(BaseModel):
    video_ids: List[str]
    search_term: str

class VideoAnalysis(BaseModel):
    video_id: str
    match_rate: float
    comment_summaries: List[str]
    title: str
    description: str 