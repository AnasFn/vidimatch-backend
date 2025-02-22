from dotenv import load_dotenv
import os
from openai import OpenAI

# Load environment variables from a .env file
load_dotenv()

# Print all environment variables for debugging
print("Environment variables:", os.environ)

# Initialize API keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables")
if not YOUTUBE_API_KEY:
    raise ValueError("YOUTUBE_API_KEY not found in environment variables")

# Initialize the OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY) 