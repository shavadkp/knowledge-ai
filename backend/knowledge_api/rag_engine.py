"""
RAG Engine: Handles document parsing, chunking, embedding, retrieval, and generation.
Uses Anthropic's API for embeddings (via voyage-ai compatible approach) and generation.
Falls back to TF-IDF cosine similarity if no embedding API is configured.
"""
import re
import math
import logging
from typing import List, Dict, Tuple, Any
from collections import Counter

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Document Parsing
# ---------------------------------------------------------------------------

def parse_pdf(file_path: str) -> List[Dict]:
    """Extract text from PDF, returning list of {text, page_number} dicts."""
    try:
        import pypdf
        pages = []
        with open(file_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ''
                if text.strip():
                    pages.append({'text': text, 'page_number': i + 1})
        return pages
    except ImportError:
        raise ImportError("pypdf is required for PDF parsing. Install it with: pip install pypdf")


def parse_txt(file_path: str) -> List[Dict]:
    """Read plain text file, returning a single-page dict."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    return [{'text': content, 'page_number': None}]


# ---------------------------------------------------------------------------
# 2. Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks.
    Tries to split on sentence boundaries first, then falls back to character splits.
    """
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_len + sentence_len > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            # Keep overlap: drop sentences from front until we're under overlap size
            while current_chunk and current_len > overlap:
                removed = current_chunk.pop(0)
                current_len -= len(removed) + 1

        current_chunk.append(sentence)
        current_len += sentence_len + 1

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return [c for c in chunks if len(c.strip()) > 20]


def chunk_pages(pages: List[Dict], chunk_size: int = 500, overlap: int = 50) -> List[Dict]:
    """Chunk a list of page dicts into a flat list of chunk dicts."""
    all_chunks = []
    idx = 0
    for page in pages:
        text_chunks = chunk_text(page['text'], chunk_size, overlap)
        for chunk in text_chunks:
            all_chunks.append({
                'content': chunk,
                'chunk_index': idx,
                'page_number': page.get('page_number'),
            })
            idx += 1
    return all_chunks


# ---------------------------------------------------------------------------
# 3. Embeddings (TF-IDF fallback — no extra API cost)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    return re.findall(r'\b[a-z]{2,}\b', text.lower())


def _tfidf_vector(text: str, idf: Dict[str, float]) -> Dict[str, float]:
    tokens = _tokenize(text)
    tf = Counter(tokens)
    total = sum(tf.values()) or 1
    vec = {}
    for term, count in tf.items():
        if term in idf:
            vec[term] = (count / total) * idf[term]
    return vec


def build_idf(corpus: List[str]) -> Dict[str, float]:
    """Build IDF table from a list of documents/chunks."""
    N = len(corpus)
    df: Counter = Counter()
    for doc in corpus:
        terms = set(_tokenize(doc))
        df.update(terms)
    return {term: math.log((N + 1) / (count + 1)) + 1 for term, count in df.items()}


def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    shared = set(vec_a) & set(vec_b)
    if not shared:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in shared)
    mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# 4. Retrieval
# ---------------------------------------------------------------------------

def retrieve_relevant_chunks(
    query: str,
    chunks: List[Any],   # QuerySet or list of DocumentChunk
    top_k: int = 3,
) -> List[Tuple[Any, float]]:
    """
    Retrieve top-k most relevant chunks for a query using TF-IDF cosine similarity.
    Returns list of (chunk, score) tuples sorted by score descending.
    """
    corpus = [c.content for c in chunks]
    if not corpus:
        return []

    idf = build_idf(corpus + [query])
    query_vec = _tfidf_vector(query, idf)

    scored = []
    for chunk in chunks:
        chunk_vec = _tfidf_vector(chunk.content, idf)
        score = cosine_similarity(query_vec, chunk_vec)
        scored.append((chunk, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# 5. Generation (Anthropic Claude)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a precise document assistant. Your ONLY job is to answer questions
based strictly on the provided document excerpts (context). 

Rules:
- Answer ONLY from the provided context. Do not use outside knowledge.
- If the answer is not in the context, say: "I couldn't find information about that in the uploaded documents."
- Be concise and factual.
- When citing information, mention which document it came from.
- Do not hallucinate, infer, or guess beyond what the context states.
"""


def generate_answer(query: str, context_chunks: List[Tuple[Any, float]]) -> Dict:
    """
    Generate a grounded answer using Claude, based only on retrieved context chunks.
    Returns dict with 'answer' and 'sources'.
    """
    if not context_chunks:
        return {
            'answer': "No documents have been uploaded yet. Please upload a document first.",
            'sources': []
        }

    # Build context block
    context_parts = []
    sources = []
    for i, (chunk, score) in enumerate(context_chunks, 1):
        doc_name = chunk.document.name
        page_info = f", Page {chunk.page_number}" if chunk.page_number else ""
        context_parts.append(
            f"[Excerpt {i} — {doc_name}{page_info}]\n{chunk.content}"
        )
        sources.append({
            'document': doc_name,
            'document_id': str(chunk.document.id),
            'chunk_index': chunk.chunk_index,
            'page_number': chunk.page_number,
            'snippet': chunk.content[:300] + ('...' if len(chunk.content) > 300 else ''),
            'relevance_score': round(score, 4),
        })

    context_text = "\n\n---\n\n".join(context_parts)

    user_message = f"""Context from uploaded documents:

{context_text}

---

Question: {query}

Answer based strictly on the context above:"""

    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        # Return context-only response if no API key
        return {
            'answer': (
                "⚠️ ANTHROPIC_API_KEY is not set. "
                "Here are the most relevant excerpts I found:\n\n" +
                "\n\n".join(f"**{s['document']}**: {s['snippet']}" for s in sources)
            ),
            'sources': sources,
        }

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )
        answer = message.content[0].text
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        answer = f"Error generating answer: {str(e)}"

    return {
        'answer': answer,
        'sources': sources,
    }
