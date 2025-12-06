"""
Script to download Yelp reviews dataset from Kaggle
Make sure you have kaggle.json configured in ~/.kaggle/
"""
import os
import pandas as pd

def download_yelp_dataset():
    """Download Yelp dataset from Kaggle"""
    print("Downloading Yelp Reviews dataset...")
    os.system("kaggle datasets download -d omkarsabnis/yelp-reviews-dataset")
    os.system("unzip -o yelp-reviews-dataset.zip")
    print("Dataset downloaded successfully!")

def load_and_sample_data(n_samples=200):
    """Load dataset and create a sample"""
    try:
        # Try to read the CSV file
        df = pd.read_csv("yelp.csv")
        print(f"Original dataset shape: {df.shape}")
        
        # Sample the data
        sampled_df = df.sample(n=min(n_samples, len(df)), random_state=42)
        
        # Save sampled data
        sampled_df.to_csv("yelp_sample.csv", index=False)
        print(f"Sampled {len(sampled_df)} reviews and saved to yelp_sample.csv")
        
        return sampled_df
    except FileNotFoundError:
        print("Error: yelp.csv not found. Please download the dataset first.")
        return None

if __name__ == "__main__":
    # Uncomment to download (requires kaggle credentials)
    download_yelp_dataset()
    
    # Sample the data
    load_and_sample_data(200)
