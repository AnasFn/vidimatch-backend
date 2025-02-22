import googleapiclient.discovery
from fastapi import HTTPException
from config import YOUTUBE_API_KEY

def get_youtube_client():
    """Initialize and return a YouTube API client."""
    return googleapiclient.discovery.build(
        "youtube", "v3", 
        developerKey=YOUTUBE_API_KEY
    )

def get_video_details(youtube, video_id: str):
    """Fetch video metadata from YouTube API."""
    try:
        request = youtube.videos().list(part="snippet", id=video_id)
        response = request.execute()
        
        if not response['items']:
            raise HTTPException(status_code=404, detail=f"Video with ID {video_id} not found")
            
        return response['items'][0]['snippet']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching video details for ID {video_id}: {str(e)}")

def get_video_comments(youtube, video_id: str):
    """Fetch both top-rated (8) and recent (4) comments from YouTube API."""
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=12,
            order="relevance"
        )
        response = request.execute()
        
        return [item['snippet']['topLevelComment']['snippet']['textDisplay'] for item in response['items']]
    except Exception as e:
        print(f"Error fetching comments for video ID {video_id}: {str(e)}")
        return [] 