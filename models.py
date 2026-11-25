from datetime import datetime, timezone
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def now():
    return datetime.now(timezone.utc)


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), nullable=False)
    postnom = db.Column(db.String(80), nullable=False)
    prenom = db.Column(db.String(80), nullable=False)
    telephone = db.Column(db.String(30), nullable=False)
    telephone_normalise = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(254))
    email_normalise = db.Column(db.String(254), unique=True)
    statut = db.Column(db.String(20), nullable=False, default='confirmée', index=True)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    cancelled_at = db.Column(db.DateTime)

    @property
    def full_name(self):
        return f'{self.nom} {self.postnom} {self.prenom}'


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=now)


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    max_participants = db.Column(db.Integer, nullable=False, default=100)
    registrations_open = db.Column(db.Boolean, nullable=False, default=True)
    event_name = db.Column(db.String(100), default='ASILI YETU', nullable=False)
    slogan = db.Column(db.String(150), default='Retour à nos racines', nullable=False)
    theme = db.Column(db.String(250), default="Décolonisation de l’esprit : notre culture, notre identité", nullable=False)
    event_date = db.Column(db.String(10), default='2026-12-19', nullable=False)
    start_time = db.Column(db.String(5), default='12:00', nullable=False)
    end_time = db.Column(db.String(5), default='16:00', nullable=False)
    venue = db.Column(db.String(150), default='Silikin Village, Kinshasa', nullable=False)
    address = db.Column(db.String(250), default='Concession COTEX n° 63, avenue Colonel Mondjiba, Kinshasa', nullable=False)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)


class RateLimit(db.Model):
    key = db.Column(db.String(64), primary_key=True)
    hits = db.Column(db.Integer, nullable=False)
    expires = db.Column(db.Integer, nullable=False)
