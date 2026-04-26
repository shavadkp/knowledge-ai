from django.urls import path
from .views import HealthView, DocumentListView, DocumentUploadView, DocumentDeleteView, AskView

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('documents/', DocumentListView.as_view(), name='document-list'),
    path('documents/upload/', DocumentUploadView.as_view(), name='document-upload'),
    path('documents/<uuid:doc_id>/', DocumentDeleteView.as_view(), name='document-delete'),
    path('ask/', AskView.as_view(), name='ask'),
]
