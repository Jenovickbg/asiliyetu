import csv
import hashlib
import hmac
import io
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import click
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for, Response, g
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect, CSRFError
from sqlalchemy import text, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from forms import ReservationForm, LoginForm, SettingsForm, PasswordForm, normalize_phone
from models import db, Reservation, Admin, Settings, RateLimit, now

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = 'admin_login'
login_manager.login_message = 'Veuillez vous connecter pour accéder à l’administration.'


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get('SECRET_KEY') or app.config['SECRET_KEY'] == 'remplacer-par-une-cle-aleatoire-longue':
        raise RuntimeError('Configurez une SECRET_KEY aléatoire dans .env (voir README.md).')
    Path(app.instance_path).mkdir(exist_ok=True)
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Admin, int(user_id)) if user_id.isdigit() else None

    def settings():
        value = db.session.get(Settings, 1)
        if value is None:
            abort(503)
        return value

    def count_active():
        return db.session.scalar(db.select(db.func.count(Reservation.id)).where(Reservation.statut == 'confirmée'))

    def begin_write():
        # Serialize the capacity check AND insertion across SQLite connections/workers.
        db.session.rollback()
        db.session.execute(text('BEGIN IMMEDIATE'))

    def limited(bucket, maximum, seconds):
        if app.config.get('TESTING') and not app.config.get('TEST_RATE_LIMIT'):
            return False
        identity = request.remote_addr or 'unknown'  # Never trust arbitrary X-Forwarded-For.
        key = hmac.new(app.secret_key.encode(), f'{bucket}:{identity}'.encode(), hashlib.sha256).hexdigest()
        begin_write()
        timestamp = int(time.time())
        db.session.execute(db.delete(RateLimit).where(RateLimit.expires <= timestamp))
        record = db.session.get(RateLimit, key)
        if record is None:
            record = RateLimit(key=key, hits=0, expires=timestamp + seconds)
            db.session.add(record)
        record.hits += 1
        denied = record.hits > maximum
        db.session.commit()
        return denied

    @app.context_processor
    def context():
        if getattr(g, 'error_page', False):
            return {}
        event = settings()
        active = count_active()
        images = Path(app.static_folder) / 'images'
        return dict(event=event, remaining=max(0, event.max_participants-active),
                    available=event.registrations_open and active < event.max_participants,
                    has_poster=(images / 'affiche-officielle.jpg').is_file(),
                    has_logo=(images / 'logo-horizontal.png').is_file(),
                    has_event_logo=(images / 'logo-asili-yetu.png').is_file(),
                    has_compact=(images / 'logo-compact.png').is_file())

    @app.template_filter('date_fr')
    def date_fr(value):
        date = datetime.strptime(value, '%Y-%m-%d')
        months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
        return f'{date.day} {months[date.month-1]} {date.year}'

    @app.template_filter('kinshasa')
    def kinshasa(value):
        return (value + timedelta(hours=1)).strftime('%d/%m/%Y à %H:%M')

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        if request.path.startswith(('/admin', '/reservation')):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        if app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/reservation', methods=['GET', 'POST'])
    def reservation():
        form = ReservationForm()
        if request.method == 'POST' and limited('reservation', 12, 600):
            abort(429)
        if form.validate_on_submit():
            phone = normalize_phone(form.telephone.data)
            email = form.email.data.casefold() if form.email.data else None
            begin_write()
            event = settings()
            if not event.registrations_open:
                db.session.rollback()
                flash('Les réservations pour ASILI YETU sont actuellement clôturées. Merci pour votre intérêt.', 'error')
            elif count_active() >= event.max_participants:
                db.session.rollback()
                flash('Toutes les places ont été réservées. Merci pour votre intérêt.', 'error')
            else:
                record = Reservation(nom=form.nom.data, postnom=form.postnom.data, prenom=form.prenom.data,
                                     telephone=phone, telephone_normalise=phone, email=email, email_normalise=email)
                db.session.add(record)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    flash('Une réservation existe déjà avec ce numéro de téléphone ou cette adresse e-mail.', 'error')
                else:
                    session['reservation_id'] = record.id
                    return redirect(url_for('confirmation'), code=303)
        elif request.method == 'POST':
            flash('Veuillez vérifier les champs du formulaire.', 'error')
        return render_template('reservation.html', form=form)

    @app.route('/reservation/confirmation')
    def confirmation():
        record = db.session.get(Reservation, session.get('reservation_id', 0))
        if record is None:
            return redirect(url_for('reservation'))
        return render_template('confirmation.html', reservation=record)

    @app.route('/admin/connexion', methods=['GET', 'POST'])
    def admin_login():
        form = LoginForm()
        if request.method == 'POST' and limited('login', 8, 900):
            abort(429)
        if form.validate_on_submit():
            admin = db.session.scalar(db.select(Admin).where(Admin.username == form.username.data))
            valid = check_password_hash(admin.password_hash if admin else app.config['DUMMY_HASH'], form.password.data)
            if admin and valid:
                session.clear()
                login_user(admin)
                session.permanent = True
                return redirect(url_for('admin_dashboard'))
            flash('Identifiant ou mot de passe incorrect.', 'error')
        return render_template('admin_login.html', form=form)

    @app.post('/admin/deconnexion')
    @login_required
    def admin_logout():
        logout_user()
        session.clear()
        return redirect(url_for('index'))

    @app.get('/admin')
    @login_required
    def admin_dashboard():
        event = settings()
        form = SettingsForm(obj=event, data={'event_date': datetime.strptime(event.event_date, '%Y-%m-%d').date(),
                                          'start_time': datetime.strptime(event.start_time, '%H:%M').time(),
                                          'end_time': datetime.strptime(event.end_time, '%H:%M').time()})
        # Date/Time fields need Python values when populated from the persisted strings.
        form.event_date.data = datetime.strptime(event.event_date, '%Y-%m-%d').date()
        form.start_time.data = datetime.strptime(event.start_time, '%H:%M').time()
        form.end_time.data = datetime.strptime(event.end_time, '%H:%M').time()
        search = request.args.get('q', '').strip()[:100]
        sort = request.args.get('tri', 'recent')
        orders = {'recent': Reservation.created_at.desc(), 'ancien': Reservation.created_at.asc(), 'nom': Reservation.nom.asc()}
        query = db.select(Reservation)
        if search:
            query = query.where(or_(*(column.contains(search, autoescape=True) for column in
                                     [Reservation.nom, Reservation.postnom, Reservation.prenom, Reservation.telephone])))
        page = db.paginate(query.order_by(orders.get(sort, orders['recent']), Reservation.id), per_page=20, error_out=False)
        return render_template('admin_dashboard.html', page=page, total=count_active(), form=form,
                               password_form=PasswordForm(), search=search, sort=sort)

    @app.post('/admin/reservations/<int:reservation_id>/annuler')
    @login_required
    def cancel(reservation_id):
        begin_write()
        record = db.get_or_404(Reservation, reservation_id)
        record.statut = 'annulée'
        record.cancelled_at = now()
        db.session.commit()
        flash('La réservation a été annulée. La place est de nouveau disponible.', 'success')
        return redirect(url_for('admin_dashboard'))

    @app.post('/admin/parametres')
    @login_required
    def update_settings():
        form = SettingsForm()
        if form.validate_on_submit():
            begin_write()
            event = settings()
            if form.max_participants.data < count_active():
                db.session.rollback()
                flash('La capacité ne peut pas être inférieure au nombre de réservations actives.', 'error')
            elif form.end_time.data <= form.start_time.data:
                db.session.rollback()
                flash('L’heure de fin doit être postérieure à l’heure de début.', 'error')
            else:
                for name in ['max_participants', 'registrations_open', 'event_name', 'slogan', 'theme', 'venue', 'address']:
                    setattr(event, name, getattr(form, name).data)
                event.event_date = form.event_date.data.isoformat()
                event.start_time = form.start_time.data.strftime('%H:%M')
                event.end_time = form.end_time.data.strftime('%H:%M')
                db.session.commit()
                flash('Les paramètres ont été enregistrés.', 'success')
        else:
            flash('Paramètres non enregistrés : vérifiez les champs, les dates et la capacité.', 'error')
        return redirect(url_for('admin_dashboard'))

    @app.post('/admin/mot-de-passe')
    @login_required
    def password():
        form = PasswordForm()
        if limited('password', 8, 900):
            abort(429)
        if form.validate_on_submit() and check_password_hash(current_user.password_hash, form.current_password.data):
            current_user.password_hash = generate_password_hash(form.new_password.data)
            db.session.commit()
            logout_user()
            session.clear()
            flash('Mot de passe modifié. Veuillez vous reconnecter.', 'success')
            return redirect(url_for('admin_login'))
        flash('Mot de passe actuel incorrect ou nouveau mot de passe trop court (12 caractères minimum).', 'error')
        return redirect(url_for('admin_dashboard'))

    @app.get('/admin/export.csv')
    @login_required
    def export_csv():
        output = io.StringIO(newline='')
        output.write('\ufeff')
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['N°', 'Nom', 'Postnom', 'Prénom', 'Téléphone', 'E-mail', 'Réservation (Kinshasa)', 'Statut', 'Annulation (Kinshasa)'])
        def safe(value):
            value = str(value or '')
            return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value
        for row in db.session.scalars(db.select(Reservation).order_by(Reservation.id)):
            writer.writerow([row.id, safe(row.nom), safe(row.postnom), safe(row.prenom), safe(row.telephone), safe(row.email),
                             kinshasa(row.created_at), row.statut, kinshasa(row.cancelled_at) if row.cancelled_at else ''])
        return Response(output.getvalue(), content_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename=asili-yetu-reservations.csv'})

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        g.error_page = True
        return render_template('error.html', code=400, message='Votre formulaire a expiré ou est invalide. Rechargez la page puis réessayez.'), 400

    def error_page(error):
        g.error_page = True
        messages = {404: 'Cette page est introuvable.', 429: 'Trop de tentatives. Veuillez réessayer dans quelques minutes.',
                    413: 'Le formulaire envoyé est trop volumineux.', 503: 'Le service est momentanément indisponible.',
                    500: 'Une erreur est survenue. Veuillez réessayer plus tard.'}
        db.session.rollback()
        # Error pages do not query the database, including during initialization/outage.
        return render_template('error.html', code=error.code, message=messages[error.code]), error.code

    for code in [404, 429, 413, 503, 500]:
        app.register_error_handler(code, error_page)

    @app.errorhandler(OperationalError)
    def database_busy(error):
        db.session.rollback()
        return Response('Service momentanément indisponible. Veuillez réessayer.', status=503, content_type='text/plain; charset=utf-8')

    @app.cli.command('init-db')
    def init_db():
        db.create_all()
        if not db.session.get(Settings, 1):
            db.session.add(Settings(id=1))
            db.session.commit()
        with db.engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA journal_mode=WAL')
        click.echo('Base de données initialisée (données existantes conservées).')

    @app.cli.command('create-admin')
    @click.option('--username', prompt='Identifiant')
    @click.password_option(confirmation_prompt=True)
    def create_admin(username, password):
        username = username.strip()
        if not username or len(username) > 80 or not 12 <= len(password) <= 256:
            raise click.ClickException('Identifiant valide et mot de passe de 12 à 256 caractères requis.')
        db.session.add(Admin(username=username, password_hash=generate_password_hash(password)))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise click.ClickException('Cet identifiant existe déjà.')
        click.echo('Compte administrateur créé.')

    @app.cli.command('backup-db')
    @click.argument('destination', type=click.Path())
    def backup_db(destination):
        target = Path(destination).resolve()
        if target.exists():
            raise click.ClickException('Le fichier de destination existe déjà.')
        source = db.engine.url.database
        target.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(source) as origin, sqlite3.connect(target) as backup:
            origin.backup(backup)
        click.echo(f'Sauvegarde créée : {target}')

    app.config['DUMMY_HASH'] = generate_password_hash(secrets.token_urlsafe(32))
    return app
