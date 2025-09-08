from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.concurrency import run_in_threadpool
from app.database import get_db
from app.auth import get_current_user
from app import models, crud
from app.services.vector_db import query_vectors
from app.utils.usage_checker import check_usage_limit
from openai import OpenAI
from pydantic import BaseModel
import os

# ===========================
# Environment config
# ===========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = os.getenv("OPENAI_MODEL_EMBEDDING", "text-embedding-3-large")
LLM_MODEL = os.getenv("OPENAI_MODEL_COMPLETION", "gpt-4o")

# Init OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

router = APIRouter(prefix="/ai", tags=["ai"])

class ChatRequest(BaseModel):
    query: str


@router.post("/chat")
async def chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Check usage limits
    if await check_usage_limit(current_user, "ai_queries", db):
        raise HTTPException(403, detail="AI query limit reached.")

    # ✅ Step 1: Check if user has uploaded any docs
    has_docs = await crud.user_has_documents(db, current_user.id)
    if not has_docs:
        return {"answer": "Please upload files before asking questions.", "sources": []}

    # ✅ Step 2: Embed query
    def _embed(q):
        resp = client.embeddings.create(model=EMBED_MODEL, input=q)
        return resp.data[0].embedding

    q_emb = await run_in_threadpool(_embed, query)

    # ✅ Step 3: Query vector DB for uploaded docs
    where = {"user_id": current_user.id}
    res = await query_vectors(q_emb, top_k=6, where=where)

    metadatas = res.get("metadatas", []) or []
    documents = res.get("documents", []) or []

    docs = []
    sources = []

    for i, md in enumerate(metadatas):
        excerpt = None
        source_info = {}

        if isinstance(md, dict):
            excerpt = md.get("text_excerpt")
            source_info = {
                "document_id": md.get("document_id"),
                "chunk_index": md.get("chunk_index"),
                "url": md.get("url"),
            }
        elif isinstance(md, list):
            parts = []
            for item in md:
                if isinstance(item, dict) and item.get("text_excerpt"):
                    parts.append(item["text_excerpt"])
                elif isinstance(item, str):
                    parts.append(item)
            excerpt = " ".join(parts)
        else:
            excerpt = str(md) if md is not None else None

        # Fallback: use documents[i]
        if not excerpt and i < len(documents):
            val = documents[i]
            excerpt = " ".join(val) if isinstance(val, list) else str(val)

        if excerpt:
            docs.append(excerpt)
            sources.append(source_info)

    # ✅ Step 4: Build context
    context = "\n\n".join(docs)[:6000]

    # ✅ Step 5: Build prompt
    if context:
        # If query is related to uploaded docs → professional, accurate, context-based
        prompt = (
            f"Use ONLY the following document excerpts to answer the question.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer clearly and directly based ONLY on the context. "
            "Do not add extra information or explanations. "
            "Provide a professional response."
        )
    else:
        # If query is unrelated → simple professional reply
        prompt = (
            f"Question: {query}\n\n"
            "Answer in a professional and concise way. "
            "Do not add extra explanations."
        )

    # ✅ Step 6: Chat with GPT
    def _chat(p):
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are an assistant that answers based on user-provided documents or general queries professionally."},
                {"role": "user", "content": p}
            ],
            max_tokens=800
        )
        return resp.choices[0].message.content

    answer = await run_in_threadpool(_chat, prompt)

    # ✅ Step 7: Increment usage counter
    await crud.increment_queries_counter(db, current_user.id, by=1)

    return {"answer": answer, "sources": sources if context else []}
