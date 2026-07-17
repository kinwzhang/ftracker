class ContentSecurityPolicyMiddleware:
    """Minimal Content-Security-Policy header for production."""

    # Relax during development; tighten for production.
    DEV_CSP = "default-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:5173; script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:5173; style-src 'self' 'unsafe-inline' http://localhost:5173; img-src 'self' data:; font-src 'self'; connect-src 'self' http://localhost:5173"
    PROD_CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # CSP only makes sense on HTML responses
        content_type = response.get("Content-Type", "")
        if "text/html" in content_type:
            from django.conf import settings
            csp = self.PROD_CSP if not settings.DEBUG else self.DEV_CSP
            response["Content-Security-Policy"] = csp
        return response
