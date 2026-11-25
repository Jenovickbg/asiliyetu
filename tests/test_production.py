"""Production boundary checks, without opening ports or using a real database."""
import pytest
from flask import Flask, request, session
from waitress.proxy_headers import proxy_headers_middleware

import serve


def test_only_local_proxy_can_supply_client_ip_and_https():
    app = Flask(__name__)

    @app.get('/')
    def inspect_request():
        return {'ip': request.remote_addr, 'scheme': request.scheme}

    app.wsgi_app = proxy_headers_middleware(app.wsgi_app, **serve.PROXY_OPTIONS, clear_untrusted=True)
    client = app.test_client()
    forwarded = {'X-Forwarded-For': '198.51.100.23', 'X-Forwarded-Proto': 'https'}
    trusted = client.get('/', headers=forwarded, environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
    assert trusted.json == {'ip': '198.51.100.23', 'scheme': 'https'}
    untrusted = client.get('/', headers=forwarded, environ_overrides={'REMOTE_ADDR': '198.51.100.50'})
    assert untrusted.json == {'ip': '198.51.100.50', 'scheme': 'http'}


@pytest.fixture
def production(monkeypatch):
    app = Flask(__name__)
    app.config.update(APP_ENV='production', SECRET_KEY='test-only-secret-' * 4,
                      TRUSTED_HOSTS=['asiliyetu.online', 'www.asiliyetu.online'],
                      SQLALCHEMY_DATABASE_URI='sqlite:////var/lib/asili-yetu/asili_yetu.db',
                      SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    monkeypatch.setattr(serve, 'create_app', lambda: app)
    return app


@pytest.mark.parametrize('key,value', [
    ('APP_ENV', 'development'), ('SECRET_KEY', 'short'),
    ('SECRET_KEY', 'remplacer-par-une-cle-aleatoire-de-64-caracteres'),
    ('TRUSTED_HOSTS', None), ('SQLALCHEMY_DATABASE_URI', 'sqlite:///asili_yetu.db'),
])
def test_production_rejects_unsafe_configuration(production, key, value):
    production.config[key] = value
    with pytest.raises(RuntimeError):
        serve.production_app()


def test_production_host_and_secure_cookie(production):
    app = serve.production_app()

    @app.get('/')
    def homepage():
        session['check'] = True
        return 'ok'

    client = app.test_client()
    response = client.get('/', base_url='https://asiliyetu.online')
    assert response.status_code == 200
    cookie = response.headers['Set-Cookie']
    assert all(flag in cookie for flag in ['Secure', 'HttpOnly', 'SameSite=Lax'])
    assert client.get('/', base_url='https://untrusted.example').status_code == 400
