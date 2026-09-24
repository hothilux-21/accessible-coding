"""
AccessibleIDE - A fully accessible IDE for dyslexic and neurodivergent learners.
"""
import os
import secrets

from flask import Flask, jsonify, request

__version__ = "0.2.2-beta"
__author__ = "AccessibleIDE Contributors"


def create_app():
    """Application factory."""
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    # Host header validation.
    # On the public web (Render) the host is fixed, so this only applies to
    # the local desktop app. It blocks DNS-rebinding attacks that try to
    # reach the local server from a malicious website.
    @app.before_request
    def validate_host():
        if os.environ.get('RENDER'):
            return None
        host = request.host.split(':')[0].lower()
        if host not in ('localhost', '127.0.0.1', '::1'):
            return jsonify({'error': 'Invalid host.'}), 403
        return None

    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app