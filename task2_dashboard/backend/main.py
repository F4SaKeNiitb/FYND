"""
FastAPI Backend for Yelp Feedback Dashboard
Handles review submission, AI response generation, and analytics
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import json
import os
import asyncio
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# Debug: Check API key
api_key = os.getenv("GOOGLE_API_KEY")
print(f"[DEBUG] API Key loaded: {'Yes' if api_key else 'No'}")
print(f"[DEBUG] API Key length: {len(api_key) if api_key else 0}")
print(f"[DEBUG] API Key prefix: {api_key[:10]}..." if api_key and len(api_key) > 10 else "[DEBUG] API Key too short or missing")

# Configure Gemini AI
if api_key:
    genai.configure(api_key=api_key)
    print("[DEBUG] Gemini configured successfully")
else:
    print("[ERROR] GOOGLE_API_KEY not found in environment variables!")

# Safety settings to avoid unnecessary blocking
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Use gemini-2.5-flash
model = genai.GenerativeModel(
    'gemini-2.5-flash',
    safety_settings=safety_settings
)
print("[DEBUG] Using model: gemini-2.5-flash")

# Initialize FastAPI app
app = FastAPI(
    title="Yelp Feedback API",
    description="Backend API for the AI-powered feedback dashboard",
    version="1.0.0"
)

# CORS middleware for frontend communication - allow all origins for deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Data storage path
DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "reviews.json"


# Pydantic models
class ReviewSubmission(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Star rating from 1 to 5")
    review: str = Field(..., min_length=1, description="Review text")
    timestamp: str = Field(..., description="ISO timestamp of submission")


class Review(BaseModel):
    id: str
    rating: int
    review: str
    timestamp: str
    aiResponse: str
    aiSummary: str
    recommendedActions: List[str]


class ReviewResponse(BaseModel):
    success: bool
    aiResponse: str
    reviewId: str


class ReviewsListResponse(BaseModel):
    reviews: List[Review]


# Helper functions for data persistence
def ensure_data_dir():
    """Ensure the data directory exists"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_reviews() -> List[dict]:
    """Read reviews from JSON file"""
    ensure_data_dir()
    
    if not DATA_FILE.exists():
        write_reviews([])
        return []
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            return data.get('reviews', [])
    except (json.JSONDecodeError, IOError):
        return []


def write_reviews(reviews: List[dict]):
    """Write reviews to JSON file"""
    ensure_data_dir()
    
    with open(DATA_FILE, 'w') as f:
        json.dump({'reviews': reviews}, f, indent=2)


# AI Generation functions
def get_response_text(response) -> str:
    """Safely extract text from Gemini response"""
    try:
        # Try direct text access first
        if response.text:
            return response.text
        
        # Check if response has candidates
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content.parts:
                return candidate.content.parts[0].text
        
        return ""
    except Exception as e:
        print(f"[DEBUG] Error in get_response_text: {e}")
        return ""


async def analyze_sentiment(review: str) -> str:
    """Analyze the actual sentiment of the review text"""
    prompt = f"""Analyze this review and respond with exactly one word - either "positive", "negative", or "inappropriate":

Review: "{review[:300]}"

Rules:
- "inappropriate" = contains profanity, vulgar language, offensive content, or spam
- "negative" = expresses dissatisfaction, complaints, or criticism (clean language)
- "positive" = expresses satisfaction, praise, or happiness

Respond with only one word."""

    try:
        print(f"[DEBUG] Calling Gemini for sentiment analysis...")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=10,
            )
        )
        print(f"[DEBUG] Gemini response received for sentiment")
        text = get_response_text(response).strip().lower()
        print(f"[DEBUG] Sentiment result: {text}")
        if text in ["positive", "negative", "inappropriate"]:
            return text
    except Exception as e:
        print(f"[ERROR] Sentiment analysis failed: {e}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
    return "unknown"


async def generate_user_response(rating: int, review: str, sentiment: str) -> str:
    """Generate AI response for the user based on their review"""
    
    # Handle inappropriate content
    if sentiment == "inappropriate":
        return "Thank you for your feedback. We appreciate all reviews but encourage constructive comments that help us improve our service."
    
    # Use actual sentiment, not just rating
    prompt = f"""A customer left a {rating}-star review. The actual tone of their review is {sentiment}.

Write a brief 2-sentence response that:
- Acknowledges their actual experience (not just the star rating)
- Is professional and empathetic
- If sentiment doesn't match rating, focus on the sentiment"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=150,
            )
        )
        
        text = get_response_text(response)
        if text:
            return text
    except Exception as e:
        print(f"Error generating user response: {e}")
    
    # Fallback responses based on actual sentiment
    if sentiment == "positive":
        return "Thank you so much for your wonderful feedback! We're thrilled that you had a great experience with us."
    elif sentiment == "negative":
        return "We sincerely apologize that your experience didn't meet your expectations. Your feedback is valuable, and we're committed to doing better."
    else:
        return "Thank you for taking the time to share your feedback. We value your input and are always working to improve."


async def generate_admin_summary(rating: int, review: str, sentiment: str) -> str:
    """Generate a concise summary for admin dashboard"""
    
    # Handle inappropriate content
    if sentiment == "inappropriate":
        return f"[FLAGGED] {rating}-star review contains inappropriate content - requires moderation."
    
    review_snippet = review[:200] if len(review) > 200 else review
    
    # Alert if rating and sentiment mismatch
    mismatch_note = ""
    if (rating >= 4 and sentiment == "negative") or (rating <= 2 and sentiment == "positive"):
        mismatch_note = f" [MISMATCH: {rating}-star rating but {sentiment} content]"
    
    prompt = f"""Summarize this customer review in one sentence. The review sentiment is {sentiment}.

Review: "{review_snippet}"

Be factual and note the key points."""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.5,
                max_output_tokens=100,
            )
        )
        
        text = get_response_text(response)
        if text:
            return text + mismatch_note
    except Exception as e:
        print(f"Error generating summary: {e}")
    
    # Fallback summary
    sentiment_label = sentiment.capitalize() if sentiment != "unknown" else "Mixed"
    return f"{sentiment_label} {rating}-star review: {review[:80]}...{mismatch_note}"


async def generate_recommended_actions(rating: int, review: str, sentiment: str) -> List[str]:
    """Generate actionable recommendations based on the review"""
    
    # Handle inappropriate content
    if sentiment == "inappropriate":
        return [
            "Flag review for moderation",
            "Consider removing inappropriate content",
            "Document incident for records"
        ]
    
    review_snippet = review[:200] if len(review) > 200 else review
    
    # Focus on actual sentiment, not just rating
    prompt = f"""A customer left a {rating}-star review with {sentiment} sentiment.

List 2-3 specific action items for the business team based on the actual sentiment (not just the rating).
Keep each item under 10 words."""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=150,
            )
        )
        
        content = get_response_text(response)
        
        if content:
            actions = [
                line.lstrip('-*0123456789.) ').strip()
                for line in content.split('\n')
                if line.strip()
            ]
            actions = [a for a in actions if a and len(a) > 3][:3]
            
            if actions:
                return actions
    except Exception as e:
        print(f"Error generating actions: {e}")
    
    # Fallback actions based on actual sentiment (not rating)
    if sentiment == "positive":
        return [
            "Continue delivering excellent service",
            "Share positive feedback with team",
            "Request customer testimonial if appropriate"
        ]
    elif sentiment == "negative":
        return [
            "Follow up with customer to address concerns",
            "Review processes to prevent similar issues",
            "Schedule team training if needed"
        ]
    else:
        return [
            "Review feedback for actionable insights",
            "Monitor for similar patterns",
            "Discuss with team how to improve"
        ]


# API Routes
@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Yelp Feedback API"}


@app.get("/api/debug")
async def debug_gemini():
    """Debug endpoint to test Gemini API"""
    api_key = os.getenv("GOOGLE_API_KEY")
    result = {
        "api_key_exists": bool(api_key),
        "api_key_length": len(api_key) if api_key else 0,
        "api_key_prefix": api_key[:10] + "..." if api_key and len(api_key) > 10 else "N/A",
        "model_name": "gemini-1.5-flash",
        "gemini_test": None,
        "raw_response": None,
        "candidates": None,
        "finish_reason": None,
        "safety_ratings": None,
        "error": None
    }
    
    try:
        print("[DEBUG] Testing Gemini API...")
        response = model.generate_content(
            "Say hello",
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=20,
            )
        )
        
        # Capture raw response details
        result["raw_response"] = str(response)
        
        if response.candidates:
            candidate = response.candidates[0]
            result["candidates"] = len(response.candidates)
            result["finish_reason"] = str(candidate.finish_reason) if hasattr(candidate, 'finish_reason') else None
            
            # Get safety ratings
            if hasattr(candidate, 'safety_ratings'):
                result["safety_ratings"] = [
                    {"category": str(r.category), "probability": str(r.probability)} 
                    for r in candidate.safety_ratings
                ]
            
            # Try to get content
            if hasattr(candidate, 'content') and candidate.content.parts:
                result["gemini_test"] = candidate.content.parts[0].text
        else:
            result["candidates"] = 0
            
        # Also try direct text access
        try:
            result["direct_text"] = response.text
        except Exception as te:
            result["direct_text_error"] = str(te)
            
        print(f"[DEBUG] Gemini test result: {result}")
    except Exception as e:
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        print(f"[ERROR] Gemini test failed: {e}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
    
    return result


@app.post("/api/submit-review", response_model=ReviewResponse)
async def submit_review(submission: ReviewSubmission):
    """
    Submit a new review and generate AI responses
    """
    try:
        # First, analyze the actual sentiment of the review text
        sentiment = await analyze_sentiment(submission.review)
        
        # Generate AI responses in parallel, passing the actual sentiment
        user_response, admin_summary, recommended_actions = await asyncio.gather(
            generate_user_response(submission.rating, submission.review, sentiment),
            generate_admin_summary(submission.rating, submission.review, sentiment),
            generate_recommended_actions(submission.rating, submission.review, sentiment)
        )
        
        # Create review object
        review_id = f"review_{int(datetime.now().timestamp() * 1000)}_{os.urandom(4).hex()}"
        new_review = {
            "id": review_id,
            "rating": submission.rating,
            "review": submission.review,
            "timestamp": submission.timestamp,
            "aiResponse": user_response,
            "aiSummary": admin_summary,
            "recommendedActions": recommended_actions,
        }
        
        # Save to file
        reviews = read_reviews()
        reviews.append(new_review)
        write_reviews(reviews)
        
        return ReviewResponse(
            success=True,
            aiResponse=user_response,
            reviewId=review_id
        )
        
    except Exception as e:
        print(f"Error processing review: {e}")
        raise HTTPException(status_code=500, detail="Failed to process review")


@app.get("/api/get-reviews", response_model=ReviewsListResponse)
async def get_reviews():
    """
    Get all reviews for the admin dashboard
    """
    reviews = read_reviews()
    return ReviewsListResponse(reviews=reviews)


@app.delete("/api/reviews/{review_id}")
async def delete_review(review_id: str):
    """
    Delete a specific review by ID
    """
    reviews = read_reviews()
    original_count = len(reviews)
    reviews = [r for r in reviews if r.get('id') != review_id]
    
    if len(reviews) == original_count:
        raise HTTPException(status_code=404, detail="Review not found")
    
    write_reviews(reviews)
    return {"success": True, "message": "Review deleted"}


@app.get("/api/analytics")
async def get_analytics():
    """
    Get analytics data for the dashboard
    """
    reviews = read_reviews()
    
    if not reviews:
        return {
            "totalReviews": 0,
            "averageRating": 0,
            "ratingDistribution": {str(i): 0 for i in range(1, 6)},
            "sentimentBreakdown": {"positive": 0, "neutral": 0, "negative": 0},
            "recentTrend": []
        }
    
    total = len(reviews)
    avg_rating = sum(r['rating'] for r in reviews) / total
    
    rating_dist = {str(i): 0 for i in range(1, 6)}
    for r in reviews:
        rating_dist[str(r['rating'])] += 1
    
    sentiment = {
        "positive": len([r for r in reviews if r['rating'] >= 4]),
        "neutral": len([r for r in reviews if r['rating'] == 3]),
        "negative": len([r for r in reviews if r['rating'] <= 2])
    }
    
    # Recent trend (last 10 reviews)
    recent = reviews[-10:]
    trend = [{"index": i + 1, "rating": r['rating']} for i, r in enumerate(recent)]
    
    return {
        "totalReviews": total,
        "averageRating": round(avg_rating, 1),
        "ratingDistribution": rating_dist,
        "sentimentBreakdown": sentiment,
        "recentTrend": trend
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
