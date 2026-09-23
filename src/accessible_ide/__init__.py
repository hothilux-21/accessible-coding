"""
AccessibleIDE - A fully accessible IDE for dyslexic and neurodivergent learners.
"""
import os

from flask import Flask

__version__ = "0.1.0-beta"
__author__ = "AccessibleIDE Contributors"


def create_app():
    """Application factory."""
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'accessible-ide-dev')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app