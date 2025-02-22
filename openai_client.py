import json
from fastapi import HTTPException
from typing import List
from config import openai_client as client
import tiktoken  # Import tiktoken


def count_tokens(text: str) -> int:
    """Count the number of tokens in the given text."""
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")  # Use the appropriate model
    return len(encoding.encode(text))


def analyze_content(
    search_term: str,
    title: str,
    description: str,
    transcript_sample: str,
    comments: List[str],
) -> dict:
    """Analyze video content using GPT-4o-mini."""
    transcript_sample = transcript_sample if transcript_sample else "Not available"
    description = (
        description[:3500] if description else ""
    )  # Limit description to 3500 characters

    content = f"""
    Title: {title}
    Description: {description}
    Transcript Sample: {transcript_sample}
    Comments: {' | '.join(comments)}
    Search Term: {search_term}
    
    1. Video Analysis - Match Rate (0-100%)

    Evaluate how well the video matches the search term based on:
    Title, description, and transcript (first minute only)
    How the introduction sets up the topic
    Whether the title/description promise relevant content

    Scoring Criteria:
    0% : Completely unrelated (e.g., cooking video for a programming search).
    1-30% : Brief keyword mention but mostly unrelated OR only a minor part of the topic.
    31-60% : Covers one/few key aspect well or is a broad foundational topic.
    61-90% : Covers most search terms directly and in the right context.
    91-100% : Near-perfect match, covers all, and 95%+ positive comments

    2. Three main points from comments negative/positive (3-4 words each)
    """

    # Count tokens in the content
    token_count = count_tokens(content)
    print(f"Token count for the request: {token_count}")

    # Print the content being sent to GPT
    print("\n=== Data Being Sent to GPT API ===")
    print("Search Term:", search_term)
    print("Title:", title)
    print("Description:", description)
    print("Transcript Sample:", transcript_sample)
    print("Comments:", comments)
    print("\nFull Prompt:")
    print(content)
    print("================================\n")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a video content analyzer - Use exact matching criteria provided - Provide analysis as JSON with keys 'match_rate' (number) and 'comment_summaries' (array of 3 strings).""",
                },
                {"role": "user", "content": content},
            ],
            temperature=0.3,
            max_tokens=150,
        )

        print("\n=== GPT API Response ===")
        print("Raw response:", response)

        raw_content = response.choices[0].message.content.strip()
        print("\nExtracted content:", raw_content)

        if raw_content.startswith("```json") and raw_content.endswith("```"):
            raw_content = raw_content[7:-3].strip()

        print("\nProcessed content:", raw_content)
        print("=======================\n")

        return json.loads(raw_content)
    except json.JSONDecodeError as e:
        print(f"JSON decode error for title '{title}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error in content analysis for title '{title}': JSON decode error",
        )
    except HTTPException as http_ex:
        print(f"HTTPException: {str(http_ex)}")
        raise
    except Exception as e:
        print(f"Error in content analysis for title '{title}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error in content analysis for title '{title}': {str(e)}",
        )

        ######
    # Matching criteria:
    # - 0%: Content is completely unrelated
    # - 20-30%: Either:
    #     * just Mentions few main parts/terms but focuses on completely unrelated content
    # - 31-90%: Either:
    #     * Covers one or some main part of the search well that is related(e.g.content= comprehensive React Native, search term= "react native with supabase auth tutorial. here main part is 2 'react native, supabase auth")

    # - 85-100%: Perfect match where:
    #     * Covers ALL search main parts/terms
    #     * Content type matches exactly what was requested (e.g., tutorial as asked)
    #     ###
