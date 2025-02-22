from fastapi import FastAPI
from typing import List
from models import VideoAnalysisRequest, VideoAnalysis
from youtube_client import get_youtube_client, get_video_details, get_video_comments
from transcript import get_smart_transcript_sample
from openai_client import analyze_content

# Create a FastAPI application instance
app = FastAPI()

@app.post("/analyze/", response_model=List[VideoAnalysis])
async def analyze_videos(request: VideoAnalysisRequest):
    """Endpoint to analyze multiple videos."""
    youtube = get_youtube_client()
    results = []
    
    for video_id in request.video_ids:
        video_details = get_video_details(youtube, video_id)
        comments = get_video_comments(youtube, video_id)
        transcript_sample = get_smart_transcript_sample(video_id)
        
        analysis = analyze_content(
            request.search_term,
            video_details['title'],
            video_details['description'],
            transcript_sample,
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