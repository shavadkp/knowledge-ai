from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('file', models.FileField(upload_to='documents/')),
                ('file_type', models.CharField(max_length=10)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('chunk_count', models.IntegerField(default=0)),
                ('status', models.CharField(
                    choices=[('processing', 'Processing'), ('ready', 'Ready'), ('error', 'Error')],
                    default='processing',
                    max_length=20
                )),
                ('error_message', models.TextField(blank=True)),
            ],
            options={'ordering': ['-uploaded_at']},
        ),
        migrations.CreateModel(
            name='DocumentChunk',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('document', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chunks',
                    to='knowledge_api.document'
                )),
                ('chunk_index', models.IntegerField()),
                ('content', models.TextField()),
                ('embedding', models.JSONField(blank=True, null=True)),
                ('page_number', models.IntegerField(blank=True, null=True)),
            ],
            options={'ordering': ['document', 'chunk_index']},
        ),
    ]
