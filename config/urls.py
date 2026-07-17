from django.contrib import admin
from django.urls import include, path
from tracker.views import react_index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('tracker.api.urls')),
    # Legacy Django template routes (still used by some tests and direct access)
    path('', include('tracker.urls')),
    # React SPA catch-all — all unmatched routes serve the React index.html
    path('<path:path>', react_index),
]
