from django.db import models
import uuid


class Document(models.Model):
    """Represents an uploaded document."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    file_type = models.CharField(max_length=10)  # 'pdf' or 'txt'
    uploaded_at = models.DateTimeField(auto_now_add=True)
    chunk_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[('processing', 'Processing'), ('ready', 'Ready'), ('error', 'Error')],
        default='processing'
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name


class DocumentChunk(models.Model):
    """A chunk of text from a document with its embedding."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = models.JSONField(null=True, blank=True)  # stored as list of floats
    page_number = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['document', 'chunk_index']

    def __str__(self):
        return f"{self.document.name} - Chunk {self.chunk_index}"
