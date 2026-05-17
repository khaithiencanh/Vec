import os
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma")
COLLECTION_NAME = "tiki_products"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = chroma_client.get_collection(COLLECTION_NAME)


def embed_query(text: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def search(query: str, top_k: int = 5) -> list[dict]:
    query_vector = embed_query(query)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    products = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        products.append({
            "name": meta.get("name", ""),
            "price": meta.get("price", 0),
            "rating": meta.get("rating", 0),
            "sold": meta.get("sold", 0),
            "brand": meta.get("brand", ""),
            "keyword": meta.get("keyword", ""),
            "url": meta.get("url", ""),
            "similarity": round(1 - distance, 3),  # cosine: 1 = giống nhất
            "document": results["documents"][0][i],
        })

    return products


if __name__ == "__main__":
    queries = [
        "áo mặc đi biển mùa hè",
        "tai nghe chống ồn giá rẻ",
        "giày chạy bộ êm chân",
    ]

    for q in queries:
        print(f"\nQuery: '{q}'")
        print("-" * 50)
        results = search(q, top_k=3)
        for r in results:
            print(f"  [{r['similarity']}] {r['name'][:60]}")
            print(f"           Giá: {r['price']:,.0f} VND | Rating: {r['rating']} | {r['url']}")
