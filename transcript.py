from youtube_transcript_api import YouTubeTranscriptApi
from fastapi import HTTPException

TRANSCRIPT_DURATION_LIMIT = 40  # Duration limit in seconds

def get_smart_transcript_sample(video_id: str) -> str:
    """Fetch and return the first 40 seconds of the video transcript."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        
        if not transcript_list:
            raise ValueError(f"No transcript available for video ID {video_id}")

        samples = []
        total_duration = 0
        for entry in transcript_list:
            samples.append(entry['text'])
            total_duration += entry['duration']
            if total_duration >= TRANSCRIPT_DURATION_LIMIT:
                break
        
        return " ".join(samples)[:500]
            
    except ValueError as ve:
        print(f"ValueError: {str(ve)}")
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        print(f"Error getting transcript for video ID {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting transcript for video ID {video_id}: {str(e)}") 