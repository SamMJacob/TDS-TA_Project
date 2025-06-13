import os
import json
import uuid
import re
from pathlib import Path
from tqdm import tqdm
import textwrap

import nltk
nltk.download("punkt")
from nltk.tokenize import sent_tokenize

# Configuration
COURSE_DIR = "scraped_pages"
DISCOURSE_DIR = "discourse_threads"
OUTPUT_FILE = "preprocessed_chunks.jsonl"
CHUNK_CHAR_LIMIT = 1500  # roughly ~500 tokens

def clean_text(text):
    """Basic cleaning: strip, normalize whitespace"""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text

def chunk_text(text, chunk_limit=CHUNK_CHAR_LIMIT):
    """Split text into reasonably sized chunks based on sentences"""
    sentences = sent_tokenize(text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < chunk_limit:
            current_chunk += " " + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def process_folder(folder_path, source_type):
    """Process all text files in a folder"""
    chunks = []
    for file_path in tqdm(list(Path(folder_path).glob("*.txt")), desc=f"Processing {source_type}"):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        cleaned = clean_text(text)
        split_chunks = chunk_text(cleaned)
        for chunk in split_chunks:
            chunks.append({
                "id": str(uuid.uuid4()),
                "type": source_type,
                "text": chunk
            })
    return chunks

def main():
    all_chunks = []

    if os.path.exists(COURSE_DIR):
        all_chunks.extend(process_folder(COURSE_DIR, "course"))
    else:
        print(f"Warning: {COURSE_DIR} not found")

    if os.path.exists(DISCOURSE_DIR):
        all_chunks.extend(process_folder(DISCOURSE_DIR, "discourse"))
    else:
        print(f"Warning: {DISCOURSE_DIR} not found")

    print(f"\nTotal chunks: {len(all_chunks)}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for item in all_chunks:
            json.dump(item, out)
            out.write("\n")
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
