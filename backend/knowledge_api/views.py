import logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Document, DocumentChunk
from .serializers import DocumentSerializer, DocumentUploadSerializer, QuestionSerializer
from .rag_engine import parse_pdf, parse_txt, chunk_pages, retrieve_relevant_chunks, generate_answer

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """GET /api/health/ — system status check."""

    def get(self, request):
        doc_count = Document.objects.filter(status='ready').count()
        chunk_count = DocumentChunk.objects.count()
        has_api_key = bool(settings.ANTHROPIC_API_KEY)

        return Response({
            'status': 'ok',
            'ready_documents': doc_count,
            'total_chunks': chunk_count,
            'ai_generation': 'enabled' if has_api_key else 'disabled (set ANTHROPIC_API_KEY)',
            'retrieval': 'tfidf-cosine',
        })


class DocumentListView(APIView):
    """GET /api/documents/ — list all uploaded documents."""

    def get(self, request):
        docs = Document.objects.all()
        serializer = DocumentSerializer(docs, many=True)
        return Response({'documents': serializer.data, 'count': docs.count()})


class DocumentUploadView(APIView):
    """POST /api/documents/upload/ — upload and process a document."""
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = serializer.validated_data['file']
        file_name = uploaded_file.name
        file_ext = file_name.rsplit('.', 1)[-1].lower()

        # Save document record
        doc = Document.objects.create(
            name=file_name,
            file=uploaded_file,
            file_type=file_ext,
            status='processing',
        )

        try:
            file_path = doc.file.path

            # Parse
            if file_ext == 'pdf':
                pages = parse_pdf(file_path)
            else:
                pages = parse_txt(file_path)

            if not pages:
                raise ValueError("No readable text found in the document.")

            # Chunk
            chunk_size = getattr(settings, 'CHUNK_SIZE', 500)
            chunk_overlap = getattr(settings, 'CHUNK_OVERLAP', 50)
            chunks = chunk_pages(pages, chunk_size=chunk_size, overlap=chunk_overlap)

            if not chunks:
                raise ValueError("Document produced no usable text chunks.")

            # Persist chunks
            chunk_objs = [
                DocumentChunk(
                    document=doc,
                    chunk_index=c['chunk_index'],
                    content=c['content'],
                    page_number=c['page_number'],
                )
                for c in chunks
            ]
            DocumentChunk.objects.bulk_create(chunk_objs)

            doc.chunk_count = len(chunk_objs)
            doc.status = 'ready'
            doc.save()

            return Response({
                'message': 'Document uploaded and processed successfully.',
                'document': DocumentSerializer(doc).data,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error processing document {file_name}: {e}")
            doc.status = 'error'
            doc.error_message = str(e)
            doc.save()
            return Response({
                'error': f'Failed to process document: {str(e)}',
                'document_id': str(doc.id),
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class DocumentDeleteView(APIView):
    """DELETE /api/documents/<id>/ — delete a document and its chunks."""

    def delete(self, request, doc_id):
        try:
            doc = Document.objects.get(id=doc_id)
            # Delete file from disk
            if doc.file:
                try:
                    import os
                    os.remove(doc.file.path)
                except FileNotFoundError:
                    pass
            doc.delete()
            return Response({'message': 'Document deleted.'}, status=status.HTTP_200_OK)
        except Document.DoesNotExist:
            return Response({'error': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)


class AskView(APIView):
    """POST /api/ask/ — ask a question against uploaded documents."""

    def post(self, request):
        serializer = QuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        question = serializer.validated_data['question']
        document_ids = serializer.validated_data.get('document_ids', [])

        # Fetch chunks from ready documents only
        chunks_qs = DocumentChunk.objects.filter(
            document__status='ready'
        ).select_related('document')

        if document_ids:
            chunks_qs = chunks_qs.filter(document__id__in=document_ids)

        chunks = list(chunks_qs)

        if not chunks:
            return Response({
                'answer': 'No ready documents found. Please upload and process a document first.',
                'sources': [],
                'question': question,
            })

        # Retrieve top-k relevant chunks
        top_k = getattr(settings, 'TOP_K_RESULTS', 3)
        relevant = retrieve_relevant_chunks(question, chunks, top_k=top_k)

        # Filter out very low-scoring chunks (below threshold)
        relevant = [(chunk, score) for chunk, score in relevant if score > 0.01]

        # Generate answer
        result = generate_answer(question, relevant)

        return Response({
            'question': question,
            'answer': result['answer'],
            'sources': result['sources'],
            'chunks_searched': len(chunks),
        })
