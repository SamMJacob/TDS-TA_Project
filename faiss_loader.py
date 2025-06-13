import json
import faiss
import numpy as np
import os

EMBEDDED_JSONL = "embedded_chunks.jsonl"
FAISS_INDEX_PATH = "faiss_index.index"
METADATA_PATH = "metadata.jsonl"

def load_embeddings_and_metadata(jsonl_path):
    embeddings = []
    metadata = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            emb = item["embedding"]
            embeddings.append(np.array(emb, dtype=np.float32))
            
            # Store all metadata except embedding for retrieval later
            meta = {k: v for k, v in item.items() if k != "embedding"}
            metadata.append(meta)
    return np.vstack(embeddings), metadata

def build_faiss_index(embeddings: np.ndarray):
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)  # L2 distance index
    index.add(embeddings)
    print(f"FAISS index built with {index.ntotal} vectors of dimension {dimension}")
    return index

def save_faiss_index(index, path):
    faiss.write_index(index, path)
    print(f"FAISS index saved to {path}")

def save_metadata(metadata, path):
    with open(path, "w", encoding="utf-8") as f:
        for meta in metadata:
            json.dump(meta, f)
            f.write("\n")
    print(f"Metadata saved to {path}")

if __name__ == "__main__":
    print(f"Loading embeddings and metadata from {EMBEDDED_JSONL} ...")
    embeddings, metadata = load_embeddings_and_metadata(EMBEDDED_JSONL)

    print("Building FAISS index ...")
    faiss_index = build_faiss_index(embeddings)

    print("Saving FAISS index and metadata ...")
    os.makedirs("faiss_data", exist_ok=True)
    save_faiss_index(faiss_index, os.path.join("faiss_data", FAISS_INDEX_PATH))
    save_metadata(metadata, os.path.join("faiss_data", METADATA_PATH))
