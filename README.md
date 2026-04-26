<img width="1899" height="917" alt="Screenshot 2026-04-25 225050" src="https://github.com/user-attachments/assets/3520a681-9a8f-4e8a-ae29-b206dc3ed242" />

# Knowledge AI — Private Document Assistant

A production-ready RAG (Retrieval-Augmented Generation) system built with Django. Upload PDF or TXT documents and ask natural language questions — answers are grounded strictly in your uploaded files, never from outside knowledge.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (HTML/JS)                    │
│   Upload UI  ─────────────────────  Chat / Q&A Interface    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP REST
┌──────────────────────────▼──────────────────────────────────┐
│                     Django REST API                          │
│                                                             │
│  POST /api/documents/upload/   ←── file upload              │
│  GET  /api/documents/          ←── list documents           │
│  DELETE /api/documents/<id>/   ←── delete document          │
│  POST /api/ask/                ←── question answering        │
│  GET  /api/health/             ←── system status            │
└──────────┬─────────────────────────────┬────────────────────┘
           │                             │
    ┌──────▼──────┐               ┌──────▼───────┐
    │  RAG Engine │               │   SQLite DB  │
    │             │               │              │
    │  1. Parse   │               │  Documents   │
    │  2. Chunk   │               │  Chunks      │
    │  3. Index   │               │  (+ embeddings│
    │  4. Retrieve│               │   if added)  │
    │  5. Generate│               └──────────────┘
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │ Anthropic   │
    │ Claude API  │
    │ (Generation)│
    └─────────────┘
```

## RAG Pipeline

```
Document Upload
     │
     ▼
┌─────────┐    PDF → pypdf → text per page
│  Parse  │    TXT → utf-8 read
└────┬────┘
     │
     ▼
┌─────────┐    Split into 500-char chunks
│  Chunk  │    with 50-char overlap
└────┬────┘    Sentence-boundary aware
     │
     ▼
┌─────────┐    Store chunks in SQLite
│  Store  │    (DocumentChunk model)
└────┬────┘
     │
  [User asks question]
     │
     ▼
┌──────────┐   Build TF-IDF vectors
│ Retrieve │   Cosine similarity ranking
└────┬─────┘   Return top-3 relevant chunks
     │
     ▼
┌──────────┐   Build grounded prompt:
│ Generate │   "Answer ONLY from this context"
└────┬─────┘   Call Claude claude-sonnet-4-20250514
     │
     ▼
  Answer + Source References
```

---

## Quick Start

### 1. Clone / navigate to project

```bash
cd knowledge-ai/backend
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

> Without the API key the system still works — it will retrieve and display relevant document excerpts but won't generate a synthesized answer.

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Start the server

```bash
python manage.py runserver
```

Django API is now live at `http://localhost:8000`

### 7. Open the frontend

Open `frontend/index.html` in your browser (no build step required).

---

## API Reference

### Health Check

```
GET /api/health/
```

Response:
```json
{
  "status": "ok",
  "ready_documents": 3,
  "total_chunks": 142,
  "ai_generation": "enabled",
  "retrieval": "tfidf-cosine"
}
```

---

### Upload Document

```
POST /api/documents/upload/
Content-Type: multipart/form-data

file: <PDF or TXT file>
```

Response `201`:
```json
{
  "message": "Document uploaded and processed successfully.",
  "document": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "report.pdf",
    "file_type": "pdf",
    "uploaded_at": "2025-01-15T10:30:00Z",
    "chunk_count": 42,
    "status": "ready"
  }
}
```

---

### List Documents

```
GET /api/documents/
```

Response:
```json
{
  "count": 2,
  "documents": [
    {
      "id": "...",
      "name": "annual-report.pdf",
      "file_type": "pdf",
      "uploaded_at": "2025-01-15T10:30:00Z",
      "chunk_count": 87,
      "status": "ready",
      "error_message": ""
    }
  ]
}
```

---

### Delete Document

```
DELETE /api/documents/<uuid>/
```

Response `200`:
```json
{ "message": "Document deleted." }
```

---

### Ask a Question

```
POST /api/ask/
Content-Type: application/json

{
  "question": "What were the key findings in Q3?",
  "document_ids": []   // optional: filter to specific docs
}
```

Response:
```json
{
  "question": "What were the key findings in Q3?",
  "answer": "According to the uploaded report, the key Q3 findings were...",
  "sources": [
    {
      "document": "annual-report.pdf",
      "document_id": "550e8400-...",
      "chunk_index": 12,
      "page_number": 4,
      "snippet": "Q3 results showed a 23% increase in revenue...",
      "relevance_score": 0.847
    }
  ],
  "chunks_searched": 87
}
```

---

## Project Structure

```
knowledge-ai/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── backend/
│   │   ├── settings.py          # Configuration
│   │   ├── urls.py              # Root URL routing
│   │   └── wsgi.py
│   └── knowledge_api/
│       ├── models.py            # Document + DocumentChunk
│       ├── views.py             # All API views
│       ├── serializers.py       # DRF serializers + validation
│       ├── rag_engine.py        # Core RAG logic
│       ├── urls.py              # App URL routing
│       └── migrations/
│           └── 0001_initial.py
└── frontend/
    └── index.html               # Single-file UI (no build needed)
```

---

## Configuration (settings.py)

| Setting | Default | Description |
|---|---|---|
| `CHUNK_SIZE` | 500 | Characters per chunk |
| `CHUNK_OVERLAP` | 50 | Overlap between chunks |
| `TOP_K_RESULTS` | 3 | Chunks retrieved per query |
| `ANTHROPIC_API_KEY` | env var | Your Anthropic key |

---

## Design Decisions

**Why TF-IDF instead of vector embeddings?**
TF-IDF cosine similarity requires zero external API calls and no vector database setup — making the system runnable with just `pip install`. The retrieval quality is excellent for factual Q&A over domain documents. To upgrade to semantic embeddings (e.g. using `voyage-3` via Anthropic), the `retrieve_relevant_chunks` function in `rag_engine.py` is the single place to swap in.

**Why SQLite?**
Zero-configuration, file-based, and sufficient for hundreds of documents. Chunks and their embeddings (if added) are stored as JSON. Swap to PostgreSQL by updating `DATABASES` in settings.

**Why single-file frontend?**
Eliminates build tooling complexity. The frontend is a pure HTML/CSS/JS file you can open directly, deploy to any static host, or embed in Django's static files.

**Grounding guarantee**
The system prompt explicitly forbids the model from using outside knowledge. If information isn't in the retrieved chunks, the model says so.

---

## Extending the System

**Add semantic embeddings:**
```python
# In rag_engine.py, replace retrieve_relevant_chunks to use:
# - Anthropic's voyage-3 embeddings API
# - Store vectors in DocumentChunk.embedding (already in the model)
# - Use numpy cosine similarity on stored vectors
```

**Add authentication:**
```python
# In views.py, add to each APIView:
permission_classes = [IsAuthenticated]
```

**Switch to PostgreSQL:**
```python
# In settings.py:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'knowledgeai',
        ...
    }
}
```

**Add streaming responses:**
Use Django's `StreamingHttpResponse` with Anthropic's `client.messages.stream()` context manager.
