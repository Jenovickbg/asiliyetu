"""Production entry point: Caddy -> loopback Waitress -> Flask."""
from waitress import serve

from app import create_app

PROXY_OPTIONS = {
    'trusted_proxy': '127.0.0.1',
    'trusted_proxy_count': 1,
    'trusted_proxy_headers': {'x-forwarded-for', 'x-forwarded-proto'},
}

def production_app():
    app = create_app()
    if app.config['APP_ENV'] != 'production':
        raise RuntimeError('APP_ENV=production est obligatoire pour ce serveur.')
    if len(app.config['SECRET_KEY']) < 32 or app.config['SECRET_KEY'].startswith('remplacer-'):
        raise RuntimeError('SECRET_KEY doit contenir au moins 32 caractères en production.')
    if not app.config['TRUSTED_HOSTS']:
        raise RuntimeError('Configurez TRUSTED_HOSTS avec les domaines autorisés.')
    if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:////'):
        raise RuntimeError('Utilisez un chemin SQLite Linux absolu et persistant.')
    return app


if __name__ == '__main__':
    serve(
        production_app(),
        host='127.0.0.1',
        port=8000,
        threads=4,
        **PROXY_OPTIONS,
        clear_untrusted_proxy_headers=True,
        max_request_body_size=32768,
        expose_tracebacks=False,
    )
