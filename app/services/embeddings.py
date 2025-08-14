# app/services/embeddings.py
import os
import uuid
from fastapi.concurrency import run_in_threadpool
from .storage import download_to_tmpfile
from .text_utils import extract_text_from_file, chunk_text
from .vector_db import add_vectors
from app import crud, models
from app.database import async_session
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = os.getenv("OPENAI_MODEL_EMBEDDING", "text-embedding-3-large")
client = OpenAI(api_key=OPENAI_API_KEY)

async def process_document_embeddings(document_id: int):
    async with async_session() as db:
        doc = await db.get(models.Document, document_id)
        if not doc:
            return

        tmp_path = await download_to_tmpfile(doc.storage_key)

        text = await run_in_threadpool(
            extract_text_from_file, tmp_path, doc.content_type
        )

        if not text or not text.strip():
            # No extractable text (e.g., image without OCR available). Skip gracefully.
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return

        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        if not chunks:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return

        ids, embeddings, metadatas, docs_texts = [], [], [], []

        for idx, chunk in enumerate(chunks):
            def _embed(c):
                resp = client.embeddings.create(model=EMBED_MODEL, input=c)
                return resp.data[0].embedding

            emb = await run_in_threadpool(_embed, chunk)

            vid = f"{document_id}_{idx}_{uuid.uuid4().hex}"
            ids.append(vid)
            embeddings.append(emb)
            metadatas.append({
                "document_id": document_id,
                "chunk_index": idx,
                "user_id": doc.user_id,
                "filename": getattr(doc, "filename", None),
                "text_excerpt": chunk[:500]
            })
            docs_texts.append(chunk[:2000])

        await add_vectors(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=docs_texts
        )

        for idx, (vid, chunk) in enumerate(zip(ids, chunks)):
            await crud.create_document_chunk(
                db,
                document_id=document_id,
                chunk_index=idx,
                text=chunk,
                vector_id=vid
            )

        try:
            os.remove(tmp_path)
        except Exception:
            pass
