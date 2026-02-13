import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.config import Settings
import os

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Ensure both ingestion and retrieval use SAME DB path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "chroma_db")

print("Using DB path:", DB_PATH)

client = chromadb.PersistentClient(path=DB_PATH)

collection = client.get_or_create_collection(name="requirements")

print("DEBUG: Collection count =", collection.count())


def retrieve_similar_requirements(query, k=3):
    query_emb = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_emb],
        n_results=k,
        include=["documents", "metadatas"]
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]

    combined = []
    for d, m in zip(docs, metas):
        combined.append({
            "description": d,
            "metadata": m
        })

    return combined
