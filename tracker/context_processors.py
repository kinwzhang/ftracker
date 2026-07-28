from django.conf import settings


def application_name(request):
    """Make the configurable application name available to every template."""
    return {"application_name": settings.APPLICATION_NAME}
