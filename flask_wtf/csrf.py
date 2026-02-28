"""Flask-WTF benzeri temel CSRF koruması."""

import secrets
from flask import abort, request, session


class CSRFProtect:
    """Uygulama genelinde temel CSRF doğrulaması sağlar."""

    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """CSRF korumasını Flask uygulamasına bağlar."""

        @app.context_processor
        def inject_csrf_token():
            return {'csrf_token': self.generate_csrf}

        @app.before_request
        def validate_csrf():
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                session_token = session.get('csrf_token')
                request_token = (
                    request.headers.get('X-CSRFToken')
                    or request.form.get('csrf_token')
                    or (request.get_json(silent=True) or {}).get('csrf_token')
                )

                if not session_token or not request_token or session_token != request_token:
                    abort(400, description='CSRF token doğrulaması başarısız.')

    def generate_csrf(self):
        """Oturum için CSRF token üretir ve döndürür."""
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return session['csrf_token']
