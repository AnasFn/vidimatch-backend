from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from models import VideoAnalysisRequest, VideoAnalysis
from youtube_client import get_youtube_client, get_video_details, get_video_comments
from openai_client import analyze_content

# Create a FastAPI application instance
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://iegaghldafpocoemdkcldpnchgignjgg"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze/", response_model=List[VideoAnalysis])
async def analyze_videos(request: VideoAnalysisRequest):
    """Endpoint to analyze multiple videos."""
    youtube = get_youtube_client()
    results = []
    
    for video_id in request.video_ids:
        video_details = get_video_details(youtube, video_id)
        comments = get_video_comments(youtube, video_id)
        
        analysis = analyze_content(
            request.search_term,
            video_details['title'],
            video_details['description'],
            comments
        )
        
        results.append(VideoAnalysis(
            video_id=video_id,
            match_rate=analysis['match_rate'],
            comment_summaries=analysis['comment_summaries'],
            title=video_details['title'],
            description=video_details['description']
        ))
    
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)