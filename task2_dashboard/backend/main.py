"""
FastAPI Backend for Yelp Feedback Dashboard v2.0
Features: SQLite, Photo Upload, Rate Limiting, Caching, Export, Search, Filters,
          Reply to Reviews, Priority Flagging, Sentiment Trends, Word Cloud, Comparison Reports
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import Counter
import sqlite3
import json
import os
import asyncio
import io
import csv
import re
import time
import hashlib
from pathlib import Path
from functools import lru_cache
import google.generativeai as genai
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# Configure Gemini AI
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    print("[DEBUG] Gemini configured successfully")

# Safety settings
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel('gemini-2.5-flash', safety_settings=safety_settings)

# Initialize FastAPI app
app = FastAPI(
    title="Yelp Feedback API v2.0",
    description="Enhanced API with SQLite, Photo Upload, Analytics, and more",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

# Directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "reviews.db"

# Create directories
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files for uploaded images
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# ==================== RATE LIMITING ====================
class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Remove old requests outside the window
        self.requests[client_id] = [
            t for t in self.requests[client_id] 
            if now - t < self.window_seconds
        ]
        
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        self.requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        now = time.time()
        if client_id not in self.requests:
            return self.max_requests
        recent = [t for t in self.requests[client_id] if now - t < self.window_seconds]
        return max(0, self.max_requests - len(recent))

rate_limiter = RateLimiter(max_requests=20, window_seconds=60)

# ==================== CACHING ====================
class SimpleCache:
    def __init__(self, ttl_seconds: int = 60):
        self.cache: Dict[str, tuple] = {}  # key -> (value, timestamp)
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        self.cache[key] = (value, time.time())
    
    def invalidate(self, pattern: str = None):
        if pattern:
            keys_to_delete = [k for k in self.cache if pattern in k]
            for k in keys_to_delete:
                del self.cache[k]
        else:
            self.cache.clear()

analytics_cache = SimpleCache(ttl_seconds=30)

# ==================== DATABASE ====================
def get_db():
    """Get database connection"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Reviews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            rating INTEGER NOT NULL,
            review TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            ai_response TEXT,
            ai_summary TEXT,
            recommended_actions TEXT,
            sentiment TEXT,
            photo_url TEXT,
            is_flagged INTEGER DEFAULT 0,
            admin_reply TEXT,
            admin_reply_timestamp TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON reviews(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rating ON reviews(rating)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_flagged ON reviews(is_flagged)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment ON reviews(sentiment)')
    
    conn.commit()
    conn.close()
    print("[DEBUG] Database initialized")

# Initialize database on startup
init_db()

# ==================== PYDANTIC MODELS ====================
class ReviewSubmission(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: str = Field(..., min_length=1)
    timestamp: str

class ReviewResponse(BaseModel):
    success: bool
    aiResponse: str
    reviewId: str

class AdminReply(BaseModel):
    reply: str

class FlagUpdate(BaseModel):
    is_flagged: bool

class ReviewFilters(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    rating: Optional[int] = None
    sentiment: Optional[str] = None
    search: Optional[str] = None
    flagged_only: bool = False

# ==================== AI FUNCTIONS ====================
def get_response_text(response) -> str:
    """Safely extract text from Gemini response"""
    try:
        if response.text:
            return response.text
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content.parts:
                return candidate.content.parts[0].text
        return ""
    except:
        return ""

async def analyze_sentiment(review: str) -> str:
    """Analyze sentiment of review text"""
    prompt = f'''Analyze this review and respond with exactly one word - "positive", "negative", or "inappropriate":
Review: "{review[:300]}"
Rules:
- "inappropriate" = profanity, vulgar, offensive, spam
- "negative" = dissatisfaction, complaints (clean language)
- "positive" = satisfaction, praise, happiness
Respond with only one word.'''
    
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(
            temperature=0.1, max_output_tokens=1024
        ))
        text = get_response_text(response).strip().lower()
        if text in ["positive", "negative", "inappropriate"]:
            return text
    except Exception as e:
        print(f"[ERROR] Sentiment analysis: {e}")
    return "neutral"

async def generate_user_response(rating: int, review: str, sentiment: str) -> str:
    """Generate AI response for user"""
    if sentiment == "inappropriate":
        return "Thank you for your feedback. We encourage constructive comments that help us improve."
    
    prompt = f'''A customer left a {rating}-star review with {sentiment} sentiment.
Write a brief 2-sentence professional response acknowledging their experience.'''
    
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(
            temperature=0.7, max_output_tokens=2048
        ))
        text = get_response_text(response)
        if text:
            return text
    except Exception as e:
        print(f"[ERROR] User response: {e}")
    
    # Fallback
    if sentiment == "positive":
        return "Thank you for your wonderful feedback! We're thrilled you had a great experience."
    elif sentiment == "negative":
        return "We apologize for not meeting your expectations. Your feedback helps us improve."
    return "Thank you for sharing your feedback. We value your input."

async def generate_admin_summary(rating: int, review: str, sentiment: str) -> str:
    """Generate summary for admin"""
    if sentiment == "inappropriate":
        return f"[FLAGGED] {rating}-star review contains inappropriate content - requires moderation."
    
    prompt = f'''Summarize this {sentiment} {rating}-star review in one sentence:
"{review[:200]}"
Be factual and brief.'''
    
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(
            temperature=0.5, max_output_tokens=2048
        ))
        text = get_response_text(response)
        if text:
            return text
    except Exception as e:
        print(f"[ERROR] Admin summary: {e}")
    
    return f"{sentiment.capitalize()} {rating}-star review: {review[:80]}..."

async def generate_recommended_actions(rating: int, sentiment: str) -> List[str]:
    """Generate action items"""
    if sentiment == "inappropriate":
        return ["Flag for moderation", "Review content policy", "Document incident"]
    
    prompt = f'''For a {rating}-star {sentiment} review, list 2-3 action items under 10 words each.
Return only the items, one per line, no bullets or numbers.'''
    
    try:
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(
            temperature=0.7, max_output_tokens=2048
        ))
        content = get_response_text(response)
        if content:
            actions = []
            for line in content.split('\n'):
                line = line.strip().lstrip('-*•0123456789.) ').replace('**', '').strip()
                if 5 < len(line) < 100 and not any(s in line.lower() for s in ['here are', 'action']):
                    actions.append(line)
            if actions:
                return actions[:3]
    except Exception as e:
        print(f"[ERROR] Actions: {e}")
    
    # Fallback
    if sentiment == "positive":
        return ["Continue excellent service", "Share with team", "Request testimonial"]
    elif sentiment == "negative":
        return ["Follow up with customer", "Review processes", "Team training"]
    return ["Review feedback", "Monitor patterns", "Discuss improvements"]

# ==================== HELPER FUNCTIONS ====================
def get_client_ip(request: Request) -> str:
    """Get client IP for rate limiting"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def extract_words(text: str) -> List[str]:
    """Extract words for word cloud"""
    # Common stop words to exclude
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'his', 'her', 'its',
        'our', 'their', 'this', 'that', 'these', 'those', 'what', 'which', 'who', 'whom',
        'very', 'really', 'just', 'also', 'so', 'as', 'if', 'when', 'than', 'then',
        'not', 'no', 'yes', 'all', 'any', 'some', 'more', 'most', 'other', 'into'
    }
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return [w for w in words if w not in stop_words]

# ==================== API ROUTES ====================

@app.get("/")
async def root():
    """Health check"""
    return {"status": "healthy", "service": "Yelp Feedback API v2.0", "features": [
        "SQLite Database", "Photo Upload", "Rate Limiting", "Caching",
        "Export CSV/Excel", "Search & Filters", "Reply to Reviews",
        "Priority Flagging", "Sentiment Trends", "Word Cloud", "Comparison Reports"
    ]}

@app.post("/api/submit-review")
async def submit_review(
    request: Request,
    rating: int = Form(...),
    review: str = Form(...),
    timestamp: str = Form(...),
    photo: Optional[UploadFile] = File(None)
):
    """Submit a review with optional photo"""
    # Rate limiting
    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    
    try:
        # Handle photo upload
        photo_url = None
        if photo and photo.filename:
            # Generate unique filename
            ext = Path(photo.filename).suffix.lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                raise HTTPException(status_code=400, detail="Invalid image format")
            
            file_hash = hashlib.md5(f"{timestamp}{rating}".encode()).hexdigest()[:8]
            filename = f"{file_hash}{ext}"
            file_path = UPLOAD_DIR / filename
            
            # Save file
            content = await photo.read()
            if len(content) > 5 * 1024 * 1024:  # 5MB limit
                raise HTTPException(status_code=400, detail="Image too large (max 5MB)")
            
            with open(file_path, "wb") as f:
                f.write(content)
            photo_url = f"/uploads/{filename}"
        
        # Quick sentiment based on rating for fast response
        quick_sentiment = "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"
        
        # Generate user response
        user_response = await generate_user_response(rating, review, quick_sentiment)
        
        # Create review ID
        review_id = f"review_{int(datetime.now().timestamp() * 1000)}_{os.urandom(4).hex()}"
        
        # Quick summary for immediate display
        quick_summary = f"{quick_sentiment.capitalize()} {rating}-star review: {review[:80]}..."
        quick_actions = json.dumps(["Processing...", "AI analysis in progress"])
        
        # Save to database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reviews (id, rating, review, timestamp, ai_response, ai_summary, 
                                recommended_actions, sentiment, photo_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (review_id, rating, review, timestamp, user_response, quick_summary, 
              quick_actions, quick_sentiment, photo_url))
        conn.commit()
        conn.close()
        
        # Invalidate cache
        analytics_cache.invalidate()
        
        # Background processing for admin data
        asyncio.create_task(process_admin_data_bg(review_id, rating, review))
        
        return {
            "success": True,
            "aiResponse": user_response,
            "reviewId": review_id,
            "photoUrl": photo_url,
            "rateLimitRemaining": rate_limiter.get_remaining(client_ip)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Submit review: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to process review")

async def process_admin_data_bg(review_id: str, rating: int, review_text: str):
    """Background task to process admin data"""
    try:
        sentiment = await analyze_sentiment(review_text)
        summary, actions = await asyncio.gather(
            generate_admin_summary(rating, review_text, sentiment),
            generate_recommended_actions(rating, sentiment)
        )
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reviews SET ai_summary = ?, recommended_actions = ?, sentiment = ?
            WHERE id = ?
        ''', (summary, json.dumps(actions), sentiment, review_id))
        conn.commit()
        conn.close()
        
        analytics_cache.invalidate()
        print(f"[DEBUG] Background processing complete: {review_id}")
    except Exception as e:
        print(f"[ERROR] Background processing: {e}")

@app.get("/api/get-reviews")
async def get_reviews(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    rating: Optional[int] = None,
    sentiment: Optional[str] = None,
    search: Optional[str] = None,
    flagged_only: bool = False,
    limit: int = 100,
    offset: int = 0
):
    """Get reviews with filters"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM reviews WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)
    if rating:
        query += " AND rating = ?"
        params.append(rating)
    if sentiment:
        query += " AND sentiment = ?"
        params.append(sentiment)
    if search:
        query += " AND (review LIKE ? OR ai_summary LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if flagged_only:
        query += " AND is_flagged = 1"
    
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Get total count
    count_query = query.replace("SELECT *", "SELECT COUNT(*)").split("ORDER BY")[0]
    cursor.execute(count_query, params[:-2])
    total = cursor.fetchone()[0]
    
    conn.close()
    
    reviews = []
    for row in rows:
        reviews.append({
            "id": row["id"],
            "rating": row["rating"],
            "review": row["review"],
            "timestamp": row["timestamp"],
            "aiResponse": row["ai_response"],
            "aiSummary": row["ai_summary"],
            "recommendedActions": json.loads(row["recommended_actions"] or "[]"),
            "sentiment": row["sentiment"],
            "photoUrl": row["photo_url"],
            "isFlagged": bool(row["is_flagged"]),
            "adminReply": row["admin_reply"],
            "adminReplyTimestamp": row["admin_reply_timestamp"]
        })
    
    return {"reviews": reviews, "total": total, "limit": limit, "offset": offset}

@app.delete("/api/reviews/{review_id}")
async def delete_review(review_id: str):
    """Delete a review"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Review not found")
    conn.commit()
    conn.close()
    analytics_cache.invalidate()
    return {"success": True, "message": "Review deleted"}

@app.patch("/api/reviews/{review_id}/flag")
async def toggle_flag(review_id: str, flag_update: FlagUpdate):
    """Toggle priority flag on a review"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE reviews SET is_flagged = ? WHERE id = ?", 
                   (1 if flag_update.is_flagged else 0, review_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Review not found")
    conn.commit()
    conn.close()
    return {"success": True, "isFlagged": flag_update.is_flagged}

@app.post("/api/reviews/{review_id}/reply")
async def reply_to_review(review_id: str, reply: AdminReply):
    """Add admin reply to a review"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE reviews SET admin_reply = ?, admin_reply_timestamp = ?
        WHERE id = ?
    ''', (reply.reply, datetime.now().isoformat(), review_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Review not found")
    conn.commit()
    conn.close()
    return {"success": True, "message": "Reply added"}

@app.get("/api/analytics")
async def get_analytics():
    """Get analytics with caching"""
    cached = analytics_cache.get("analytics")
    if cached:
        return cached
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Basic stats
    cursor.execute("SELECT COUNT(*) FROM reviews")
    total = cursor.fetchone()[0]
    
    if total == 0:
        return {
            "totalReviews": 0, "averageRating": 0,
            "ratingDistribution": {str(i): 0 for i in range(1, 6)},
            "sentimentBreakdown": {"positive": 0, "neutral": 0, "negative": 0},
            "flaggedCount": 0, "repliedCount": 0
        }
    
    cursor.execute("SELECT AVG(rating) FROM reviews")
    avg_rating = round(cursor.fetchone()[0] or 0, 1)
    
    # Rating distribution
    rating_dist = {str(i): 0 for i in range(1, 6)}
    cursor.execute("SELECT rating, COUNT(*) FROM reviews GROUP BY rating")
    for row in cursor.fetchall():
        rating_dist[str(row[0])] = row[1]
    
    # Sentiment breakdown
    sentiment = {"positive": 0, "neutral": 0, "negative": 0, "inappropriate": 0}
    cursor.execute("SELECT sentiment, COUNT(*) FROM reviews GROUP BY sentiment")
    for row in cursor.fetchall():
        if row[0] in sentiment:
            sentiment[row[0]] = row[1]
    
    # Flagged and replied counts
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE is_flagged = 1")
    flagged = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reviews WHERE admin_reply IS NOT NULL")
    replied = cursor.fetchone()[0]
    
    conn.close()
    
    result = {
        "totalReviews": total,
        "averageRating": avg_rating,
        "ratingDistribution": rating_dist,
        "sentimentBreakdown": sentiment,
        "flaggedCount": flagged,
        "repliedCount": replied
    }
    
    analytics_cache.set("analytics", result)
    return result

@app.get("/api/export")
async def export_reviews(format: str = "csv"):
    """Export reviews as CSV or JSON"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    if format == "json":
        reviews = []
        for row in rows:
            reviews.append({
                "id": row["id"],
                "rating": row["rating"],
                "review": row["review"],
                "timestamp": row["timestamp"],
                "sentiment": row["sentiment"],
                "aiSummary": row["ai_summary"],
                "isFlagged": bool(row["is_flagged"]),
                "adminReply": row["admin_reply"]
            })
        return {"reviews": reviews}
    
    # CSV export
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Rating", "Review", "Timestamp", "Sentiment", 
                     "AI Summary", "Flagged", "Admin Reply"])
    
    for row in rows:
        writer.writerow([
            row["id"], row["rating"], row["review"], row["timestamp"],
            row["sentiment"], row["ai_summary"], 
            "Yes" if row["is_flagged"] else "No", row["admin_reply"] or ""
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reviews_export.csv"}
    )

@app.get("/api/word-cloud")
async def get_word_cloud():
    """Get word frequency for word cloud"""
    cached = analytics_cache.get("wordcloud")
    if cached:
        return cached
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT review FROM reviews")
    rows = cursor.fetchall()
    conn.close()
    
    all_words = []
    for row in rows:
        all_words.extend(extract_words(row["review"]))
    
    # Count word frequencies
    word_counts = Counter(all_words)
    
    # Get top 50 words
    top_words = [{"word": word, "count": count} for word, count in word_counts.most_common(50)]
    
    result = {"words": top_words}
    analytics_cache.set("wordcloud", result)
    return result

@app.get("/api/sentiment-trends")
async def get_sentiment_trends(period: str = "daily"):
    """Get sentiment trends over time"""
    cached = analytics_cache.get(f"trends_{period}")
    if cached:
        return cached
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Group by date
    if period == "weekly":
        date_format = "%Y-W%W"
    elif period == "monthly":
        date_format = "%Y-%m"
    else:  # daily
        date_format = "%Y-%m-%d"
    
    cursor.execute(f'''
        SELECT strftime('{date_format}', timestamp) as period,
               sentiment, COUNT(*) as count,
               AVG(rating) as avg_rating
        FROM reviews
        GROUP BY period, sentiment
        ORDER BY period
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    # Organize by period
    trends = {}
    for row in rows:
        period_key = row["period"]
        if period_key not in trends:
            trends[period_key] = {
                "period": period_key,
                "positive": 0, "neutral": 0, "negative": 0, "inappropriate": 0,
                "total": 0, "avgRating": 0
            }
        trends[period_key][row["sentiment"]] = row["count"]
        trends[period_key]["total"] += row["count"]
    
    # Calculate averages
    cursor = get_db().cursor()
    for period_key in trends:
        cursor.execute(f'''
            SELECT AVG(rating) FROM reviews 
            WHERE strftime('{date_format}', timestamp) = ?
        ''', (period_key,))
        avg = cursor.fetchone()[0]
        trends[period_key]["avgRating"] = round(avg, 1) if avg else 0
    
    result = {"trends": list(trends.values())}
    analytics_cache.set(f"trends_{period}", result)
    return result

@app.get("/api/comparison")
async def get_comparison():
    """Compare this week vs last week"""
    cached = analytics_cache.get("comparison")
    if cached:
        return cached
    
    now = datetime.now()
    this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start
    
    conn = get_db()
    cursor = conn.cursor()
    
    def get_week_stats(start: datetime, end: datetime):
        cursor.execute('''
            SELECT COUNT(*) as count, AVG(rating) as avg_rating,
                   SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive,
                   SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative
            FROM reviews WHERE timestamp >= ? AND timestamp < ?
        ''', (start.isoformat(), end.isoformat()))
        row = cursor.fetchone()
        return {
            "count": row["count"] or 0,
            "avgRating": round(row["avg_rating"] or 0, 1),
            "positive": row["positive"] or 0,
            "negative": row["negative"] or 0
        }
    
    this_week = get_week_stats(this_week_start, now)
    last_week = get_week_stats(last_week_start, last_week_end)
    
    conn.close()
    
    # Calculate changes
    def calc_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round((current - previous) / previous * 100, 1)
    
    result = {
        "thisWeek": this_week,
        "lastWeek": last_week,
        "changes": {
            "count": calc_change(this_week["count"], last_week["count"]),
            "avgRating": round(this_week["avgRating"] - last_week["avgRating"], 1),
            "positive": calc_change(this_week["positive"], last_week["positive"]),
            "negative": calc_change(this_week["negative"], last_week["negative"])
        }
    }
    
    analytics_cache.set("comparison", result)
    return result

@app.get("/api/debug")
async def debug():
    """Debug endpoint"""
    return {
        "api_key_exists": bool(api_key),
        "db_exists": DB_PATH.exists(),
        "upload_dir_exists": UPLOAD_DIR.exists(),
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
