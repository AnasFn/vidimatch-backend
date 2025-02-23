from youtube_transcript_api import YouTubeTranscriptApi
from fastapi import HTTPException
import random
from youtube_transcript_api.formatters import JSONFormatter
from youtube_transcript_api._transcripts import TranscriptListFetcher
from youtube_transcript_api._settings import WATCH_URL

TRANSCRIPT_DURATION_LIMIT = 40  # Duration limit in seconds

# List of common User-Agents to rotate through
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

def get_smart_transcript_sample(video_id: str) -> str:
    """Fetch and return the first 40 seconds of the video transcript."""
    try:
        # Create a custom headers dictionary with a random User-Agent
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1"
        }

        # Create a transcript fetcher with custom headers
        fetcher = TranscriptListFetcher(http_client={'headers': headers})
        
        # Get transcript list using the fetcher
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