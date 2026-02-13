import os
import json
import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.config import Settings

print("Starting ChromaDB ingestion...")

model = SentenceTransformer("all-MiniLM-L6-v2")

with open("data/samples/evaluation_cases.json", "r", encoding="utf-8") as f:
    requirements = json.load(f)

print(f"Loaded {len(requirements)} requirements")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "chroma_db")

print("Using DB path:", DB_PATH)

client = chromadb.PersistentClient(path=DB_PATH)

collection = client.get_or_create_collection(name="requirements")

for req in requirements:
    description = req["description"]

    embedding = model.encode(description).tolist()

    collection.add(
        documents=[description],
        embeddings=[embedding],
        metadatas=[{
            "id": req["id"],
            "domain": req.get("domain", "unknown")
        }],
        ids=[req["id"]]
    )

print("✅ ChromaDB ingestion complete")
print("Final collection count:", collection.count())
