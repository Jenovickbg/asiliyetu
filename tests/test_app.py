import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from models import db, Admin, Reservation, Settings


@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret-only',
                      'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + (tmp_path / 'test.db').as_posix()})
    with app.app_context():
        db.create_all()
        db.session.add(Settings(id=1))
        db.session.add(Admin(username='gestion', password_hash=generate_password_hash('UnSecretDeTest!123')))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def token(client, path='/reservation'):
    response = client.get(path)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.text)
    assert match, response.text[:500]
    return match.group(1)


def data(**kwargs):
    return dict(nom='  KABILA  ', postnom='Mbuyi', prenom='Aline', telephone='0812345678', email='', consent='y', **kwargs)


def reserve(client, **changes):
    payload = data()
    payload.update(changes)
    payload['csrf_token'] = token(client)
    return client.post('/reservation', data=payload)


def login(client):
    return client.post('/admin/connexion', data={'csrf_token': token(client, '/admin/connexion'),
                       'username': 'gestion', 'password': 'UnSecretDeTest!123'})


def active(app):
    with app.app_context():
        return db.session.query(Reservation).filter_by(statut='confirmée').count()


def test_valid_and_refresh(client, app):
    response = reserve(client, email='aline@example.com')
    assert response.status_code == 303
    assert response.location.endswith('/reservation/confirmation')
    for _ in range(2):
        page = client.get(response.location)
        assert 'Votre réservation est confirmée' in page.text
        assert 'KABILA Mbuyi Aline' in page.text
        assert page.headers['Cache-Control'] == 'no-store'
    assert active(app) == 1
    with app.app_context():
        assert db.session.get(Reservation, 1).telephone_normalise == '+243812345678'
        assert db.session.get(Reservation, 1).nom == 'KABILA'


def test_two_without_email(client, app):
    assert reserve(client).status_code == 303
    assert reserve(client, telephone='0892345678').status_code == 303
    assert active(app) == 2
    with app.app_context():
        assert all(row.email_normalise is None for row in db.session.scalars(db.select(Reservation)))


@pytest.mark.parametrize('phone', ['0812345678', '+243 812 345 678', '00243812345678', '243812345678', '812345678'])
def test_duplicate_phone(client, app, phone):
    reserve(client)
    response = reserve(client, telephone=phone)
    assert 'Une réservation existe déjà' in response.text
    assert active(app) == 1


@pytest.mark.parametrize('email', ['aline@example.com', 'ALINE@EXAMPLE.COM'])
def test_duplicate_email(client, app, email):
    reserve(client, email='aline@example.com')
    response = reserve(client, telephone='0892345678', email=email)
    assert 'Une réservation existe déjà' in response.text
    assert active(app) == 1


@pytest.mark.parametrize('changes', [{'nom': '   '}, {'telephone': '+33123456789'}, {'email': 'invalide'}, {'consent': ''}])
def test_invalid(client, app, changes):
    response = reserve(client, **changes)
    assert 'Veuillez vérifier les champs' in response.text
    assert 'field-error' in response.text
    assert active(app) == 0


@pytest.mark.parametrize('closed', [True, False])
def test_closed_or_full(client, app, closed):
    csrf_token = token(client)
    with app.app_context():
        settings = db.session.get(Settings, 1)
        if closed:
            settings.registrations_open = False
        else:
            settings.max_participants = 1
            db.session.add(Reservation(nom='A', postnom='B', prenom='C', telephone='+243899999999', telephone_normalise='+243899999999'))
        db.session.commit()
    response = client.post('/reservation', data={**data(), 'csrf_token': csrf_token})
    assert ('clôturées' if closed else 'Toutes les places') in response.text
    assert active(app) == (0 if closed else 1)


def test_admin_visibility_cancel_and_uniqueness(client, app):
    reserve(client)
    assert login(client).status_code == 302
    page = client.get('/admin')
    assert page.status_code == 200
    assert 'KABILA' in page.text
    csrf_token = token(client, '/admin')
    assert client.post('/admin/reservations/1/annuler', data={'csrf_token': csrf_token}).status_code == 302
    assert active(app) == 0
    assert 'annulée' in client.get('/admin').text
    assert 'Une réservation existe déjà' in reserve(client).text


@pytest.mark.parametrize('path', ['/admin', '/admin/export.csv'])
def test_private_get(client, path):
    assert client.get(path).status_code == 302


@pytest.mark.parametrize('path', ['/admin/parametres', '/admin/mot-de-passe', '/admin/deconnexion', '/admin/reservations/1/annuler'])
def test_private_post(client, path):
    assert client.post(path, data={'csrf_token': token(client)}).status_code == 302


def test_confirmation_privacy(client, app):
    reserve(client)
    stranger = app.test_client()
    assert stranger.get('/reservation/confirmation?id=1').status_code == 302


def test_csrf(client, app):
    assert client.post('/reservation', data=data()).status_code == 400
    assert client.post('/reservation', data={**data(), 'csrf_token': 'invalid'}).status_code == 400
    assert active(app) == 0
    login(client)
    assert client.post('/admin/parametres', data={}).status_code == 400


def settings_payload(client, **changes):
    payload = dict(csrf_token=token(client, '/admin'), max_participants=120, registrations_open='y', event_name='ASILI YETU',
                   slogan='Retour à nos racines', theme='Notre culture', event_date='2026-12-19', start_time='12:00',
                   end_time='16:00', venue='Silikin Village', address='Concession COTEX')
    payload.update(changes)
    return payload


def test_settings_persist_and_reopen(client, app):
    login(client)
    payload = settings_payload(client)
    payload.pop('registrations_open')
    client.post('/admin/parametres', data=payload)
    restarted = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret-only', 'SQLALCHEMY_DATABASE_URI': app.config['SQLALCHEMY_DATABASE_URI']})
    with restarted.app_context():
        settings = db.session.get(Settings, 1)
        assert settings.max_participants == 120
        assert not settings.registrations_open
        assert settings.venue == 'Silikin Village'
        db.session.remove()
        db.engine.dispose()
    client.post('/admin/parametres', data=settings_payload(client))
    assert reserve(client).status_code == 303


def test_parallel_last_place(app):
    with app.app_context():
        db.session.get(Settings, 1).max_participants = 1
        db.session.commit()
    barrier = Barrier(2)
    def send(phone):
        with app.test_client() as client:
            csrf_token = token(client)
            barrier.wait(timeout=10)
            payload = data()
            payload.update(telephone=phone, csrf_token=csrf_token)
            return client.post('/reservation', data=payload).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(send, ['0812345678', '0892345678']))
    assert sorted(results) == [200, 303]
    assert active(app) == 1


def test_csv_xss_and_search(client):
    reserve(client, nom='=1+1', prenom='<script>alert(1)</script>')
    login(client)
    page = client.get('/admin?q=%3D1')
    assert '=1+1' in page.text
    assert '<script>alert(1)</script>' not in page.text
    assert '&lt;script&gt;' in page.text
    csv = client.get('/admin/export.csv')
    assert csv.text.startswith('\ufeff')
    assert "'=1+1" in csv.text
    assert "'+243812345678" in csv.text


def test_password_change(client):
    login(client)
    response = client.post('/admin/mot-de-passe', data={'csrf_token': token(client, '/admin'),
                           'current_password': 'UnSecretDeTest!123', 'new_password': 'NouveauSecret!456'})
    assert response.location.endswith('/admin/connexion')
    assert client.get('/admin').status_code == 302
    response = client.post('/admin/connexion', data={'csrf_token': token(client, '/admin/connexion'),
                           'username': 'gestion', 'password': 'NouveauSecret!456'})
    assert response.location.endswith('/admin')


def test_login_rate_limit(client, app):
    app.config['TEST_RATE_LIMIT'] = True
    csrf_token = token(client, '/admin/connexion')
    for _ in range(8):
        assert client.post('/admin/connexion', data={'csrf_token': csrf_token, 'username': 'absent', 'password': 'wrong'}).status_code == 200
    assert client.post('/admin/connexion', data={'csrf_token': csrf_token}).status_code == 429


def test_cli_and_backup(app, tmp_path):
    runner = app.test_cli_runner()
    assert runner.invoke(args=['init-db']).exit_code == 0
    assert runner.invoke(args=['create-admin', '--username', 'second'], input='AutreSecret!123\nAutreSecret!123\n').exit_code == 0
    backup = tmp_path / 'backup.db'
    assert runner.invoke(args=['backup-db', str(backup)]).exit_code == 0
    assert backup.exists()
    assert runner.invoke(args=['backup-db', str(backup)]).exit_code != 0


def test_pages_and_errors(client):
    for path in ['/', '/reservation', '/admin/connexion']:
        response = client.get(path)
        assert response.status_code == 200
        assert 'Content-Security-Policy' in response.headers
    assert client.get('/absent').status_code == 404


def test_minimum_capacity(client, app):
    reserve(client)
    reserve(client, telephone='0892345678')
    login(client)
    response = client.post('/admin/parametres', data=settings_payload(client, max_participants=1), follow_redirects=True)
    assert 'ne peut pas être inférieure' in response.text
    with app.app_context():
        assert db.session.get(Settings, 1).max_participants == 100
