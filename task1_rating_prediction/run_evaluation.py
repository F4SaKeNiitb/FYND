"""
Run complete evaluation of all three prompting approaches
With concurrent processing for faster execution
"""

import pandas as pd
import json
import argparse
import multiprocessing
import time
from prompt_approaches import (
    approach_1_direct_sentiment,
    approach_2_aspect_based,
    approach_3_few_shot,
    evaluate_approach,
    evaluate_all_approaches_concurrent,
    DEFAULT_MAX_WORKERS
)

def main():
    parser = argparse.ArgumentParser(description='Evaluate all prompting approaches')
    parser.add_argument('--samples', type=int, default=200, help='Number of samples to evaluate')
    parser.add_argument('--workers', type=int, default=None, help='Number of concurrent workers')
    parser.add_argument('--sequential', action='store_true', help='Use sequential processing')
    args = parser.parse_args()
    
    # Load data
    print("Loading dataset...")
    df = pd.read_csv("yelp_sample.csv")
    print(f"Loaded {len(df)} reviews\n")
    
    # Ensure we have the required columns
    if 'text' not in df.columns or 'stars' not in df.columns:
        print("Error: Dataset must have 'text' and 'stars' columns")
        return
    
    # Configuration
    n_samples = min(args.samples, len(df))
    max_workers = args.workers or DEFAULT_MAX_WORKERS
    use_concurrency = not args.sequential
    
    print(f"Configuration:")
    print(f"   Samples: {n_samples}")
    print(f"   Workers: {max_workers}")
    print(f"   CPU Cores: {multiprocessing.cpu_count()}")
    print(f"   Concurrent: {use_concurrency}")
    
    total_start = time.time()
    
    # Run evaluations
    all_metrics = []
    
    # Approach 1
    df_approach1, metrics1 = evaluate_approach(
        df, 
        approach_1_direct_sentiment, 
        "Approach 1: Direct Sentiment",
        max_samples=n_samples,
        max_workers=max_workers,
        use_concurrency=use_concurrency
    )
    df_approach1.to_csv("results_approach1.csv", index=False)
    all_metrics.append(metrics1)
    
    # Approach 2
    df_approach2, metrics2 = evaluate_approach(
        df, 
        approach_2_aspect_based, 
        "Approach 2: Aspect-Based Analysis",
        max_samples=n_samples,
        max_workers=max_workers,
        use_concurrency=use_concurrency
    )
    df_approach2.to_csv("results_approach2.csv", index=False)
    all_metrics.append(metrics2)
    
    # Approach 3
    df_approach3, metrics3 = evaluate_approach(
        df, 
        approach_3_few_shot, 
        "Approach 3: Few-Shot Learning",
        max_samples=n_samples,
        max_workers=max_workers,
        use_concurrency=use_concurrency
    )
    df_approach3.to_csv("results_approach3.csv", index=False)
    all_metrics.append(metrics3)
    
    total_time = time.time() - total_start
    
    # Create comparison table
    comparison_df = pd.DataFrame(all_metrics)
    comparison_df.to_csv("comparison_results.csv", index=False)
    
    print("\n" + "="*80)
    print("FINAL COMPARISON TABLE")
    print("="*80)
    print(comparison_df.to_string(index=False))
    print("\n")
    
    # Save detailed report
    with open("evaluation_report.json", "w") as f:
        json.dump({
            "total_samples": n_samples,
            "max_workers": max_workers,
            "concurrent_processing": use_concurrency,
            "total_time_seconds": round(total_time, 2),
            "approaches": all_metrics,
            "summary": {
                "best_mae": min(m['mean_absolute_error'] for m in all_metrics),
                "best_exact_accuracy": max(m['exact_accuracy'] for m in all_metrics),
                "best_json_validity": max(m['json_validity_rate'] for m in all_metrics),
                "total_reviews_processed": n_samples * 3,
                "avg_reviews_per_second": round((n_samples * 3) / total_time, 2)
            }
        }, f, indent=2)
    
    print(f"Total evaluation time: {total_time:.2f}s")
    print(f"Total reviews processed: {n_samples * 3}")
    print(f"Average speed: {(n_samples * 3) / total_time:.2f} reviews/second")
    
    print("\nEvaluation complete!")
    print("Results saved to:")
    print("   - results_approach1.csv")
    print("   - results_approach2.csv")
    print("   - results_approach3.csv")
    print("   - comparison_results.csv")
    print("   - evaluation_report.json")

if __name__ == "__main__":
    main()
