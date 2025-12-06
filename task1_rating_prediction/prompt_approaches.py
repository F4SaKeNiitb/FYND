"""
Three Different Prompting Approaches for Yelp Review Rating Prediction
Using Google Gemini 2.5 Flash with Concurrent Processing
"""

import os
import json
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, Tuple, List, Callable
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from functools import partial
import threading

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Thread-local storage for model instances (each thread gets its own)
thread_local = threading.local()

def get_model():
    """Get or create a thread-local model instance"""
    if not hasattr(thread_local, 'model'):
        thread_local.model = genai.GenerativeModel('gemini-3-pro-preview')
    return thread_local.model

# Default number of workers (can be overridden)
# Using lower workers for gemini-3-pro due to rate limits (25 req/min)
DEFAULT_MAX_WORKERS = min(4, (multiprocessing.cpu_count() or 1))
RATE_LIMIT_DELAY = 3.0  # Higher delay for gemini-3-pro rate limits (25 req/min)

def parse_json_response(text: str) -> Dict:
    """Extract JSON from model response"""
    try:
        # Try direct JSON parsing
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Try to find JSON object in text
        json_match = re.search(r'\{[^{}]*"predicted_stars"[^{}]*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        
        # Fallback: try to extract rating from text
        rating_match = re.search(r'(\d)\s*(?:star|stars)', text.lower())
        if rating_match:
            return {
                "predicted_stars": int(rating_match.group(1)),
                "explanation": text[:200]
            }
        
        return {"predicted_stars": 3, "explanation": "Could not parse response"}

# ============================================================================
# APPROACH 1: Expectation-Reality Gap Analysis (V2 Best - MAE 1.14)
# ============================================================================
# Strategy: Psychologically-grounded approach measuring gap between expectations
# and actual experience. Best overall performer across all versions.
# ============================================================================

def approach_1_direct_sentiment(review_text: str) -> Dict:
    """
    Approach 1: Expectation-Reality Gap Analysis
    
    Best performer from V2 with MAE 1.14, 19% exact accuracy.
    """
    
    prompt = f"""You are analyzing a Yelp review to predict its star rating using EXPECTATION-REALITY GAP analysis.

THEORY: Customer ratings reflect how reality compared to expectations:
- Reality >> Expectations = 5 stars (delighted)
- Reality > Expectations = 4 stars (pleased)  
- Reality = Expectations = 3 stars (satisfied)
- Reality < Expectations = 2 stars (disappointed)
- Reality << Expectations = 1 star (angry)

ANALYZE THIS REVIEW:
"{review_text}"

STEP 1: IDENTIFY EXPECTATION SIGNALS
What did the customer expect? Look for:
- Price expectations (expensive = high expectations, cheap = low)
- Reputation mentions ("heard great things", "famous for", "highly rated")
- Past experience ("usually love this place", "first time")
- Specific hopes ("came for the pizza", "wanted to celebrate")
List the expectation level: [Very High / High / Medium / Low / Very Low]

STEP 2: IDENTIFY REALITY SIGNALS  
What actually happened? Look for:
- Quality descriptors ("delicious", "bland", "perfect", "terrible")
- Service experience ("friendly", "rude", "attentive", "ignored")
- Value assessment ("worth it", "overpriced", "great deal", "rip-off")
- Outcome ("will return", "never again", "might try again")
List the reality assessment: [Exceptional / Good / Average / Poor / Terrible]

STEP 3: CALCULATE GAP
- Exceptional reality + any expectation = 5 stars (exceeded all expectations)
- Good reality + Low/Medium expectation = 5 stars | + High expectation = 4 stars
- Good reality + Very High expectation = 3-4 stars (met but didn't exceed)
- Average reality + Low expectation = 3-4 stars | + High expectation = 2-3 stars
- Poor reality + any expectation = 2 stars (disappointed regardless)
- Terrible reality + any expectation = 1 star (failed completely)

Respond with ONLY this JSON (no other text):
{{"predicted_stars": <integer 1-5>, "explanation": "<expectation level> expectations, <reality assessment> reality = <rating reasoning>"}}"""

    try:
        model = get_model()
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=512,
            )
        )
        
        result = parse_json_response(response.text)
        return result
    except Exception as e:
        return {"predicted_stars": 3, "explanation": f"Error: {str(e)}"}


# ============================================================================
# APPROACH 2: Chain-of-Thought Sentiment Analysis (V2 - MAE 1.16)
# ============================================================================
# Strategy: Multi-step reasoning process that forces systematic analysis
# Third best overall performer.
# ============================================================================

def approach_2_aspect_based(review_text: str) -> Dict:
    """
    Approach 2: Chain-of-Thought Sentiment Analysis
    
    From V2 with MAE 1.16, 18% exact accuracy.
    """
    
    prompt = f"""You are an expert at predicting Yelp star ratings from review text.

REVIEW TO ANALYZE:
"{review_text}"

ANALYSIS FRAMEWORK - Think through each step:

STEP 1: EMOTIONAL TONE
What is the overall emotional tone? (angry, disappointed, neutral, satisfied, delighted)
Key emotional words/phrases:

STEP 2: SPECIFIC COMPLAINTS OR PRAISE
List specific things mentioned:
- Positive points:
- Negative points:

STEP 3: INTENSITY SIGNALS
Look for intensity markers:
- Strong negative: "worst", "terrible", "never again", "awful", "disgusting"
- Mild negative: "disappointing", "not great", "could be better"
- Neutral: "okay", "average", "decent", "fine"
- Mild positive: "good", "nice", "enjoyed", "pleasant"
- Strong positive: "amazing", "best ever", "perfect", "outstanding", "love"

STEP 4: RETURN INTENT
Would they come back? (definitely not / probably not / maybe / probably yes / definitely yes)

STEP 5: RATING DECISION
Based on your analysis:
- 1 star: Angry, multiple severe complaints, warning others, never returning
- 2 stars: Disappointed, significant issues, unlikely to return
- 3 stars: Mixed feelings, some good some bad, might return
- 4 stars: Generally positive, minor issues, would return
- 5 stars: Enthusiastic, no complaints, highly recommending

Respond with ONLY this JSON (no other text):
{{"predicted_stars": <integer 1-5>, "explanation": "<brief reasoning>"}}"""

    try:
        model = get_model()
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=512,
            )
        )
        
        result = parse_json_response(response.text)
        return result
    except Exception as e:
        return {"predicted_stars": 3, "explanation": f"Error: {str(e)}"}


# ============================================================================
# APPROACH 3: Direct Sentiment Classification (V1 - MAE 1.175)
# ============================================================================
# Strategy: Simple, direct sentiment analysis mapping emotional tone to ratings
# Second best overall - sometimes simpler is better.
# ============================================================================

def approach_3_few_shot(review_text: str) -> Dict:
    """
    Approach 3: Direct Sentiment Classification
    
    From V1 with MAE 1.175, 17.5% exact accuracy.
    Simple but effective approach.
    """
    
    prompt = f"""Analyze the following Yelp review and predict the star rating (1-5 stars).

Review: "{review_text}"

Based on the sentiment and content of this review, predict the star rating where:
- 1 star = Very negative experience
- 2 stars = Negative experience  
- 3 stars = Mixed or neutral experience
- 4 stars = Positive experience
- 5 stars = Excellent experience

Return your response in JSON format ONLY, no other text:
{{
    "predicted_stars": <number 1-5>,
    "explanation": "Brief reasoning for the assigned rating."
}}"""

    try:
        model = get_model()
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=256,
            )
        )
        
        result = parse_json_response(response.text)
        return result
    except Exception as e:
        return {"predicted_stars": 3, "explanation": f"Error: {str(e)}"}


# ============================================================================
# Concurrent Processing Utilities
# ============================================================================

def process_single_review(args: Tuple[int, str, int, Callable]) -> Tuple[int, Dict]:
    """Process a single review with the given approach function.
    
    Args:
        args: Tuple of (index, review_text, actual_stars, approach_func)
    
    Returns:
        Tuple of (index, result_dict)
    """
    idx, review_text, actual_stars, approach_func = args
    
    try:
        result = approach_func(review_text)
        time.sleep(RATE_LIMIT_DELAY)  # Small delay to avoid rate limiting
        return (idx, result)
    except Exception as e:
        return (idx, {"predicted_stars": 3, "explanation": f"Error: {str(e)}"})


def process_reviews_batch(
    reviews: List[Tuple[int, str, int]], 
    approach_func: Callable,
    max_workers: int = None
) -> Dict[int, Dict]:
    """Process multiple reviews concurrently using thread pool.
    
    Args:
        reviews: List of tuples (index, review_text, actual_stars)
        approach_func: The approach function to use
        max_workers: Number of concurrent workers (default: auto-calculated)
    
    Returns:
        Dictionary mapping index to result
    """
    if max_workers is None:
        max_workers = DEFAULT_MAX_WORKERS
    
    results = {}
    
    # Prepare arguments for each review
    args_list = [(idx, text, stars, approach_func) for idx, text, stars in reviews]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_idx = {
            executor.submit(process_single_review, args): args[0] 
            for args in args_list
        }
        
        # Collect results as they complete
        completed = 0
        total = len(args_list)
        
        for future in as_completed(future_to_idx):
            idx, result = future.result()
            results[idx] = result
            completed += 1
            print(f"Processing: {completed}/{total} ({completed*100//total}%)", end='\r')
    
    print()  # New line after progress
    return results


# ============================================================================
# Evaluation Function (with Concurrent Processing)
# ============================================================================

def evaluate_approach(
    df: pd.DataFrame, 
    approach_func: Callable, 
    approach_name: str, 
    max_samples: int = 200,
    max_workers: int = None,
    use_concurrency: bool = True
) -> Tuple[pd.DataFrame, Dict]:
    """
    Evaluate a prompting approach on the dataset with concurrent processing
    
    Args:
        df: DataFrame with 'text' and 'stars' columns
        approach_func: Function to use for prediction
        approach_name: Name for logging
        max_samples: Maximum number of samples to evaluate
        max_workers: Number of concurrent workers (default: auto-calculated)
        use_concurrency: Whether to use concurrent processing
    
    Returns:
        - DataFrame with predictions
        - Dictionary with evaluation metrics
    """
    if max_workers is None:
        max_workers = DEFAULT_MAX_WORKERS
    
    print(f"\n{'='*60}")
    print(f"Evaluating: {approach_name}")
    print(f"{'='*60}")
    print(f"Samples: {min(max_samples, len(df))}, Workers: {max_workers}, Concurrent: {use_concurrency}\n")
    
    # Sample if needed
    eval_df = df.head(max_samples).copy()
    
    predictions = [None] * len(eval_df)
    explanations = [None] * len(eval_df)
    json_valid_count = 0
    
    start_time = time.time()
    
    if use_concurrency:
        # Prepare review data for concurrent processing
        reviews = [
            (i, row['text'], row['stars']) 
            for i, (_, row) in enumerate(eval_df.iterrows())
        ]
        
        # Process concurrently
        results = process_reviews_batch(reviews, approach_func, max_workers)
        
        # Collect results
        for idx, result in results.items():
            if 'predicted_stars' in result and 'explanation' in result:
                json_valid_count += 1
                predictions[idx] = result['predicted_stars']
                explanations[idx] = result['explanation']
            else:
                predictions[idx] = 3
                explanations[idx] = "Invalid JSON response"
    else:
        # Sequential processing (original method)
        for idx, (_, row) in enumerate(eval_df.iterrows()):
            review_text = row['text']
            
            print(f"Processing {idx + 1}/{len(eval_df)}...", end='\r')
            
            result = approach_func(review_text)
            
            if 'predicted_stars' in result and 'explanation' in result:
                json_valid_count += 1
                predictions[idx] = result['predicted_stars']
                explanations[idx] = result['explanation']
            else:
                predictions[idx] = 3
                explanations[idx] = "Invalid JSON response"
            
            time.sleep(RATE_LIMIT_DELAY)
        
        print()
    
    elapsed_time = time.time() - start_time
    
    # Add predictions to dataframe
    eval_df['predicted_stars'] = predictions
    eval_df['explanation'] = explanations
    eval_df['error'] = abs(eval_df['stars'] - eval_df['predicted_stars'])
    
    # Calculate metrics
    mae = eval_df['error'].mean()
    rmse = (eval_df['error'] ** 2).mean() ** 0.5
    exact_accuracy = (eval_df['error'] == 0).mean()
    within_1_accuracy = (eval_df['error'] <= 1).mean()
    json_validity = json_valid_count / len(eval_df)
    
    metrics = {
        'approach': approach_name,
        'mean_absolute_error': round(mae, 3),
        'rmse': round(rmse, 3),
        'exact_accuracy': round(exact_accuracy, 3),
        'within_1_star_accuracy': round(within_1_accuracy, 3),
        'json_validity_rate': round(json_validity, 3),
        'processing_time_seconds': round(elapsed_time, 2),
        'reviews_per_second': round(len(eval_df) / elapsed_time, 2)
    }
    
    print(f"\n{approach_name} Results:")
    print(f"  MAE: {metrics['mean_absolute_error']}")
    print(f"  RMSE: {metrics['rmse']}")
    print(f"  Exact Accuracy: {metrics['exact_accuracy']:.1%}")
    print(f"  Within 1 Star: {metrics['within_1_star_accuracy']:.1%}")
    print(f"  JSON Validity: {metrics['json_validity_rate']:.1%}")
    print(f"  Time: {metrics['processing_time_seconds']}s ({metrics['reviews_per_second']} reviews/sec)")
    
    return eval_df, metrics


def evaluate_all_approaches_concurrent(
    df: pd.DataFrame,
    max_samples: int = 200,
    max_workers: int = None
) -> Tuple[List[pd.DataFrame], List[Dict]]:
    """
    Evaluate all three approaches concurrently for maximum speed.
    
    This runs all three approaches in parallel using process pool.
    """
    from concurrent.futures import ProcessPoolExecutor
    
    if max_workers is None:
        max_workers = DEFAULT_MAX_WORKERS
    
    approaches = [
        (approach_1_direct_sentiment, "Approach 1: Direct Sentiment"),
        (approach_2_aspect_based, "Approach 2: Aspect-Based Analysis"),
        (approach_3_few_shot, "Approach 3: Few-Shot Learning"),
    ]
    
    results = []
    all_metrics = []
    
    print(f"\nRunning all approaches with {max_workers} workers each...")
    print(f"   Total samples per approach: {max_samples}")
    print(f"   CPU cores available: {multiprocessing.cpu_count()}\n")
    
    for approach_func, approach_name in approaches:
        df_result, metrics = evaluate_approach(
            df, approach_func, approach_name, 
            max_samples=max_samples, 
            max_workers=max_workers,
            use_concurrency=True
        )
        results.append(df_result)
        all_metrics.append(metrics)
    
    return results, all_metrics


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test prompting approaches for rating prediction')
    parser.add_argument('--workers', type=int, default=None, help='Number of concurrent workers')
    parser.add_argument('--samples', type=int, default=5, help='Number of samples to test')
    parser.add_argument('--sequential', action='store_true', help='Use sequential processing instead of concurrent')
    args = parser.parse_args()
    
    # Load sample data
    try:
        df = pd.read_csv("yelp_sample.csv")
        print(f"Loaded {len(df)} reviews from yelp_sample.csv")
    except FileNotFoundError:
        print("Error: yelp_sample.csv not found. Please run download_data.py first.")
        exit(1)
    
    workers = args.workers or DEFAULT_MAX_WORKERS
    print(f"\nConfiguration:")
    print(f"   Workers: {workers}")
    print(f"   CPU Cores: {multiprocessing.cpu_count()}")
    print(f"   Concurrent: {not args.sequential}")
    
    # Test with a small sample first
    test_sample = args.samples
    print(f"\nTesting with {test_sample} samples...\n")
    
    test_df = df.head(test_sample)
    
    if args.sequential:
        # Sequential testing
        print("\n--- Testing Approach 1: Direct Sentiment (Sequential) ---")
        for idx, row in test_df.iterrows():
            result = approach_1_direct_sentiment(row['text'])
            print(f"Actual: {row['stars']}, Predicted: {result['predicted_stars']}")
            time.sleep(0.1)
        
        print("\n--- Testing Approach 2: Aspect-Based (Sequential) ---")
        for idx, row in test_df.iterrows():
            result = approach_2_aspect_based(row['text'])
            print(f"Actual: {row['stars']}, Predicted: {result['predicted_stars']}")
            time.sleep(0.1)
        
        print("\n--- Testing Approach 3: Few-Shot (Sequential) ---")
        for idx, row in test_df.iterrows():
            result = approach_3_few_shot(row['text'])
            print(f"Actual: {row['stars']}, Predicted: {result['predicted_stars']}")
            time.sleep(0.1)
    else:
        # Concurrent testing
        print("--- Testing All Approaches (Concurrent) ---")
        
        reviews = [(i, row['text'], row['stars']) for i, (_, row) in enumerate(test_df.iterrows())]
        
        for approach_func, approach_name in [
            (approach_1_direct_sentiment, "Approach 1: Direct Sentiment"),
            (approach_2_aspect_based, "Approach 2: Aspect-Based"),
            (approach_3_few_shot, "Approach 3: Few-Shot"),
        ]:
            print(f"\n{approach_name}:")
            start = time.time()
            results = process_reviews_batch(reviews, approach_func, max_workers=workers)
            elapsed = time.time() - start
            
            for idx in sorted(results.keys()):
                actual = test_df.iloc[idx]['stars']
                predicted = results[idx]['predicted_stars']
                print(f"  Actual: {actual}, Predicted: {predicted}")
            
            print(f"  Time: {elapsed:.2f}s")
    
    print("\nAll approaches working. Ready for full evaluation.")
