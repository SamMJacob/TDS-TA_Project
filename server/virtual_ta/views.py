from django.shortcuts import render
from django.conf import settings

# Create your views here.
import base64
import faiss
import json
import os
import numpy as np
import requests
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from PIL import Image
import io
import textwrap


# Load FAISS index and metadata once
FAISS_INDEX_PATH = os.path.join(settings.BASE_DIR, "faiss_data/faiss_index.index")
METADATA_PATH = os.path.join(settings.BASE_DIR, "faiss_data/metadata.jsonl")

# Load index
faiss_index = faiss.read_index(FAISS_INDEX_PATH)

# Load metadata
with open(METADATA_PATH, "r", encoding="utf-8") as f:
    metadata = [json.loads(line) for line in f]

# AIPIPE config
EMBEDDING_URL = "https://aipipe.org/openai/v1/embeddings"
COMPLETION_URL = "https://aipipe.org/openrouter/v1/chat/completions"
AIPIPE_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIzZjMwMDI1MjVAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.WYVf2JnaQ4W9bGrILpHSHuYsXgWqjl92tDTjBpSoUok"  # set this in env vars

def get_embedding(text):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AIPIPE_TOKEN}"
    }
    data = {
        "model": "text-embedding-3-small",
        "input": text,
        "service_tier": "flex"
    }
    response = requests.post(EMBEDDING_URL, headers=headers, json=data)
    response.raise_for_status()
    return np.array(response.json()["data"][0]["embedding"], dtype=np.float32)

def query_faiss(query_embedding, top_k=5):
    D, I = faiss_index.search(np.array([query_embedding]), top_k)
    return [metadata[i] for i in I[0]]

def build_prompt(question, context_chunks):
    context_texts = "\n\n".join(chunk["text"] for chunk in context_chunks)
    prompt = f"""You are a helpful teaching assistant. Use the context below to answer the student's question.

Context:
{context_texts}

Question: {question}
Answer:"""
    return prompt

@api_view(["POST"])
def tds_virtual_ta(request):
    question = request.data.get("question", "")
    image_b64 = request.data.get("image")

    if not question:
        return Response({"error": "Missing 'question'"}, status=400)



    try:
        query_embedding = get_embedding(question)
        relevant_chunks = query_faiss(query_embedding)

        prompt = build_prompt(question, relevant_chunks)

         # Optional: image processing
        if image_b64:
            image_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "low"}}
                ]
            }
        else:
            image_message = {"role": "user", "content": prompt}

        headers = {
            "Authorization": f"Bearer {AIPIPE_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o-mini",#"google/gemini-2.0-flash-lite-001",
            "messages": [
                {"role": "system", "content": "You are a helpful teaching assistant."},
                image_message
            ],
            "service_tier": "flex"
        }

        response = requests.post(COMPLETION_URL, headers=headers, json=data)
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]

        links = []
        for chunk in relevant_chunks:
            if "url" in chunk and "text" in chunk:
                links.append({
                    "url": chunk["url"],
                    "text": textwrap.shorten(chunk["text"].replace("\n", " "), width=150, placeholder="...")
                })

        return Response({
            "answer": answer.strip(),
            "links": links
        })

    except Exception as e:
        return Response({"error": str(e)}, status=500)
