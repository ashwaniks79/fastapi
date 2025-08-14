# app/services/vector_db.py
import os
from fastapi.concurrency import run_in_threadpool
import chromadb
from chromadb.config import Settings

_COLLECTION_NAME = "eredox_documents"

# Decide client type based on env vars
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = os.getenv("CHROMA_PORT")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "chroma_db")

if CHROMA_HOST and CHROMA_PORT:
    # HTTP mode (recommended for local + live consistency)
    _client = chromadb.HttpClient(
        host=CHROMA_HOST,
        port=int(CHROMA_PORT)
    )
else:
    # Embedded mode (fallback, mainly for quick local testing without extra container)
    
    _client = chromadb.Client(
        Settings(chroma_db_impl="duckdb+parquet", persist_directory=CHROMA_PERSIST_DIR)
    )

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        try:
            _collection = _client.get_collection(name=_COLLECTION_NAME)
        except Exception:
            _collection = _client.create_collection(name=_COLLECTION_NAME)
    return _collection


async def add_vectors(ids: list, embeddings: list, metadatas: list, documents: list = None):
    def _add():
        col = _get_collection()
        col.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
        # persist only in embedded mode
        if not CHROMA_HOST:
            _client.persist()
    await run_in_threadpool(_add)


async def query_vectors(query_embedding: list, top_k: int = 5, where: dict = None):
    def _query():
        col = _get_collection()
        return col.query(query_embeddings=[query_embedding], n_results=top_k, where=where)
    return await run_in_threadpool(_query)


async def delete_vectors_by_document(document_id: int):
    def _delete():
        col = _get_collection()
        res = col.get(where={"document_id": document_id})
        ids = res['ids']
        if ids:
            col.delete(ids=ids)
            if not CHROMA_HOST:
                _client.persist()
    await run_in_threadpool(_delete)
