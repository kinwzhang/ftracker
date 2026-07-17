from django.contrib import admin
from django.urls import include, path
from tracker.views import react_index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('tracker.api.urls')),
    # Legacy Django action endpoints (non-conflicting with React routes)
    path('', include('tracker.urls')),
    # React SPA — root and catch-all (must be last)
    path('', react_index, name='react_index'),
    path('<path:path>', react_index),
]
