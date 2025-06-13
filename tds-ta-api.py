import os
import base64
import json
import faiss
import numpy as np
from flask import Flask, request, jsonify
import requests
import logging

# === Configuration === #
EMBEDDING_DIM = 1536  # text-embedding-3-small returns 1536-d vectors
FAISS_INDEX_FILE = "faiss_data/faiss_index.index"
METADATA_FILE = "faiss_data/metadata.jsonl"
AIPIPE_API_URL = "https://aipipe.org/openai/v1/chat/completions"
EMBEDDING_API_URL = "https://aipipe.org/openai/v1/embeddings"
MODEL_NAME = "openai/gpt-4o"
AIPIPE_TOKEN = os.getenv("AIPIPE_TOKEN")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Validate environment and files === #
def validate_setup():
    if not AIPIPE_TOKEN:
        raise ValueError("AIPIPE_TOKEN environment variable not set")
    
    if not os.path.exists(FAISS_INDEX_FILE):
        raise FileNotFoundError(f"FAISS index file '{FAISS_INDEX_FILE}' not found")
    
    if not os.path.exists(METADATA_FILE):
        raise FileNotFoundError(f"Metadata file '{METADATA_FILE}' not found")

# === Load FAISS and metadata === #
def load_metadata_jsonl(file_path):
    """Load metadata from JSONL file"""
    metadata = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:  # Skip empty lines
                    try:
                        entry = json.loads(line)
                        metadata.append(entry)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping invalid JSON on line {line_num}: {e}")
                        continue
        return metadata
    except Exception as e:
        logger.error(f"Error loading metadata from {file_path}: {e}")
        raise

try:
    validate_setup()
    faiss_index = faiss.read_index(FAISS_INDEX_FILE)
    metadata = load_metadata_jsonl(METADATA_FILE)
    logger.info(f"Loaded FAISS index with {faiss_index.ntotal} vectors")
    logger.info(f"Loaded metadata with {len(metadata)} entries")
except Exception as e:
    logger.error(f"Failed to initialize: {e}")
    raise

# === Flask App === #
app = Flask(__name__)

# === Helper: Search FAISS === #
def search_similar_chunks(query_embedding, top_k=5):
    try:
        query_vector = np.array(query_embedding).astype("float32").reshape(1, -1)
        
        # Validate embedding dimension
        if query_vector.shape[1] != EMBEDDING_DIM:
            raise ValueError(f"Query embedding dimension {query_vector.shape[1]} doesn't match expected {EMBEDDING_DIM}")
        
        distances, indices = faiss_index.search(query_vector, top_k)
        
        # Filter out invalid indices and get metadata
        results = []
        for i, distance in zip(indices[0], distances[0]):
            if i != -1 and i < len(metadata):
                chunk = metadata[i].copy()
                chunk['similarity_score'] = float(distance)
                results.append(chunk)
        
        logger.info(f"Found {len(results)} similar chunks")
        return results
    
    except Exception as e:
        logger.error(f"Error in FAISS search: {e}")
        raise

# === Helper: Embed Query === #
def get_embedding(text):
    try:
        if not text or not text.strip():
            raise ValueError("Empty text provided for embedding")
        
        response = requests.post(
            EMBEDDING_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AIPIPE_TOKEN}"
            },
            json={
                "input": text.strip(),
                "model": "text-embedding-3-small",
                "service_tier": "flex"
            },
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        if "data" not in result or not result["data"]:
            raise ValueError("Invalid embedding response format")
        
        embedding = result["data"][0]["embedding"]
        if len(embedding) != EMBEDDING_DIM:
            raise ValueError(f"Embedding dimension {len(embedding)} doesn't match expected {EMBEDDING_DIM}")
        
        return embedding
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Embedding API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        raise

# === Helper: Validate and process base64 image === #
def process_image(image_b64):
    try:
        if not image_b64:
            return None, None
        
        # Remove any whitespace/newlines that might be present
        image_b64 = image_b64.strip()
        
        # Validate base64 format
        try:
            decoded = base64.b64decode(image_b64, validate=True)
        except Exception:
            raise ValueError("Invalid base64 image data")
        
        # Basic size check (prevent extremely large images)
        if len(decoded) > 10 * 1024 * 1024:  # 10MB limit
            raise ValueError("Image too large (max 10MB)")
        
        # Detect image format and return appropriate MIME type
        mime_type = "image/jpeg"  # default
        if decoded.startswith(b'\xFF\xD8\xFF'):  # JPEG
            mime_type = "image/jpeg"
        elif decoded.startswith(b'\x89PNG'):      # PNG
            mime_type = "image/png"
        elif decoded.startswith(b'RIFF') and b'WEBP' in decoded[:12]:  # WebP
            mime_type = "image/webp"
        elif decoded.startswith(b'GIF'):          # GIF
            mime_type = "image/gif"
        else:
            logger.warning("Unknown image format, defaulting to jpeg")
        
        return image_b64, mime_type
    
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise

# === Helper: Call GPT-4o via AI Pipe === #
def query_gpt4o(question, retrieved_chunks, image_data=None):
    try:
        system_prompt = {
            "role": "system",
            "content": (
                "You are a helpful teaching assistant for the Tools in Data Science course. "
                "Use the provided context to answer questions accurately and concisely. "
                "If the context doesn't contain relevant information, say so clearly. "
                "Focus on giving direct, practical answers based on the course materials provided."
            )
        }
        
        # Build context from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks):
            text = chunk.get('text', '')
            url = chunk.get('url', '')
            title = chunk.get('title', '')
            source = chunk.get('source', '')
            
            context_part = f"[Source {i+1}]: {text}"
            if url:
                context_part += f"\nURL: {url}"
            if title:
                context_part += f"\nTitle: {title}"
            if source:
                context_part += f"\nSource Type: {source}"
            
            context_parts.append(context_part)
        
        context_text = "\n\n".join(context_parts)
        
        # Build user message content
        user_content = [{
            "type": "text", 
            "text": f"Context from course materials:\n{context_text}\n\nQuestion: {question}"
        }]
        
        # Add image if provided
        if image_data:
            image_b64, mime_type = image_data
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_b64}"
                }
            })
        
        response = requests.post(
            AIPIPE_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AIPIPE_TOKEN}"
            },
            json={
                "model": MODEL_NAME,
                "messages": [
                    system_prompt,
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": 1000,
                "temperature": 0.1,
                "service_tier": "flex"
            },
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        if "choices" not in result or not result["choices"]:
            raise ValueError("Invalid GPT-4o response format")
        
        return result["choices"][0]["message"]["content"]
    
    except requests.exceptions.RequestException as e:
        logger.error(f"GPT-4o API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error querying GPT-4o: {e}")
        raise

# === API Route === #
@app.route("/api/", methods=["POST"])
def api():
    try:
        # Validate request
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        question = data.get("question")
        image_b64 = data.get("image")
        
        # Validate required fields
        if not question:
            return jsonify({"error": "Missing 'question' in request"}), 400
        
        if not isinstance(question, str) or not question.strip():
            return jsonify({"error": "'question' must be a non-empty string"}), 400
        
        logger.info(f"Processing question: {question[:100]}...")
        
        # Step 1: Process image if provided
        processed_image = None
        if image_b64:
            try:
                processed_image = process_image(image_b64)
                logger.info("Image processed successfully")
            except Exception as e:
                return jsonify({"error": f"Image processing failed: {str(e)}"}), 400
        
        # Step 2: Embed the query
        try:
            query_embedding = get_embedding(question.strip())
        except Exception as e:
            return jsonify({"error": f"Failed to generate embedding: {str(e)}"}), 500
        
        # Step 3: Search FAISS index
        try:
            retrieved_chunks = search_similar_chunks(query_embedding, top_k=5)
            if not retrieved_chunks:
                return jsonify({"error": "No relevant context found"}), 404
        except Exception as e:
            return jsonify({"error": f"Search failed: {str(e)}"}), 500
        
        # Step 4: Send to GPT-4o
        try:
            response_text = query_gpt4o(question, retrieved_chunks, image_data=processed_image)
        except Exception as e:
            return jsonify({"error": f"Failed to generate response: {str(e)}"}), 500
        
        # Step 5: Format links from retrieved chunks
        links = []
        for chunk in retrieved_chunks:
            url = chunk.get('url')
            text = chunk.get('text', '')
            title = chunk.get('title', '')
            
            if url:  # Only include chunks that have URLs
                # Use title if available, otherwise use a truncated version of the text
                link_text = title if title else (text[:100] + "..." if len(text) > 100 else text)
                links.append({
                    "url": url,
                    "text": link_text
                })
        
        # Return response in the specified format
        return jsonify({
            "answer": response_text,
            "links": links
        })
    
    except Exception as e:
        logger.error(f"Unexpected error in API: {e}")
        return jsonify({"error": "Internal server error"}), 500

# === Health check endpoint === #
@app.route("/health", methods=["GET"])
def health():
    try:
        return jsonify({
            "status": "healthy",
            "faiss_vectors": faiss_index.ntotal,
            "metadata_entries": len(metadata),
            "faiss_index_file": FAISS_INDEX_FILE,
            "metadata_file": METADATA_FILE
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

# === Entry point === #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)