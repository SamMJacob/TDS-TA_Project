import os
import json
import requests
import tiktoken
from tqdm import tqdm

# Config
SCRAPED_FOLDER = "scraped_pages"
DISCOURSE_FOLDER = "discourse_threads"
OUTPUT_FILE = "embedded_chunks.jsonl"
CHUNK_SIZE = 500  # tokens per chunk
EMBEDDING_API_URL = "https://aipipe.org/openai/v1/embeddings"
EMBEDDING_MODEL = "text-embedding-3-small"  # Changed to 3-small
API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIzZjMwMDI1MjVAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.WYVf2JnaQ4W9bGrILpHSHuYsXgWqjl92tDTjBpSoUok"

# Use correct tokenizer for the embedding model
tokenizer = tiktoken.encoding_for_model(EMBEDDING_MODEL)

def read_txt_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def read_json_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def chunk_text(text, max_tokens=CHUNK_SIZE):
    tokens = tokenizer.encode(text)
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i:i+max_tokens]
        yield tokenizer.decode(chunk_tokens)

def get_embedding(text):
    """Call embedding API with proper authentication"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"  # Added missing API key
        }
        payload = {
            "model": EMBEDDING_MODEL,
            "input": text,
            "service_tier": "flex"  # Added service tier like first implementation
        }
        response = requests.post(EMBEDDING_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        return data["data"][0]["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def process_scraped_pages():
    scraped_count = 0
    if os.path.exists(SCRAPED_FOLDER):
        for filename in os.listdir(SCRAPED_FOLDER):
            if not filename.endswith(".txt"):
                continue
            
            txt_path = os.path.join(SCRAPED_FOLDER, filename)
            json_path = os.path.join(SCRAPED_FOLDER, filename.replace(".txt", ".json"))
            
            text = read_txt_file(txt_path)
            
            # Read metadata if it exists
            metadata = {}
            if os.path.exists(json_path):
                metadata = read_json_file(json_path)
            
            url = metadata.get("url", "unknown")
            title = metadata.get("title", filename.replace(".txt", ""))
            date = metadata.get("date") or metadata.get("created_at")
            
            for chunk in chunk_text(text):
                embedding = get_embedding(chunk)
                if embedding:  # Only yield if embedding was successful
                    scraped_count += 1
                    yield {
                        "embedding": embedding,
                        "text": chunk,
                        "source": "scraped_page",
                        "url": url,
                        "title": title,
                        "date": date
                    }
    print(f"Processed {scraped_count} scraped page chunks")

def process_discourse_threads():
    discourse_count = 0
    if os.path.exists(DISCOURSE_FOLDER):
        for filename in os.listdir(DISCOURSE_FOLDER):
            if not filename.endswith(".txt"):
                continue
            
            txt_path = os.path.join(DISCOURSE_FOLDER, filename)
            json_path = os.path.join(DISCOURSE_FOLDER, filename.replace(".txt", ".json"))
            
            text = read_txt_file(txt_path)
            
            # Read metadata if it exists  
            metadata = {}
            if os.path.exists(json_path):
                metadata = read_json_file(json_path)
            
            url = metadata.get("url", "unknown")
            title = metadata.get("title", filename.replace(".txt", ""))
            date = metadata.get("date") or metadata.get("created_at")
            
            for chunk in chunk_text(text):
                embedding = get_embedding(chunk)
                if embedding:  # Only yield if embedding was successful
                    discourse_count += 1
                    yield {
                        "embedding": embedding,
                        "text": chunk,
                        "source": "discourse",
                        "url": url,
                        "title": title,
                        "date": date
                    }
    print(f"Processed {discourse_count} discourse thread chunks")

def main():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
        # Process scraped pages
        print("Processing scraped pages...")
        for chunk_data in process_scraped_pages():
            out_f.write(json.dumps(chunk_data) + "\n")
        
        # Process discourse threads
        print("Processing discourse threads...")
        for chunk_data in process_discourse_threads():
            out_f.write(json.dumps(chunk_data) + "\n")
    
    print(f"✅ Embedding extraction complete. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()