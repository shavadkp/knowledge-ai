from rest_framework import serializers
from .models import Document, DocumentChunk


class DocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunk
        fields = ['id', 'chunk_index', 'content', 'page_number']


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'name', 'file_type', 'uploaded_at', 'chunk_count', 'status', 'error_message']


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        name = value.name.lower()
        if not (name.endswith('.pdf') or name.endswith('.txt')):
            raise serializers.ValidationError("Only PDF and TXT files are supported.")
        max_size = 20 * 1024 * 1024  # 20MB
        if value.size > max_size:
            raise serializers.ValidationError("File size must be under 20MB.")
        return value


class QuestionSerializer(serializers.Serializer):
    question = serializers.CharField(min_length=3, max_length=1000)
    document_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text="Optional: limit search to specific document IDs."
    )
