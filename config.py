import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.environ.get('ASILI_ENV_FILE') or None)


class Config:
    APP_ENV = os.environ.get('APP_ENV', 'development')
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///asili_yetu.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'timeout': 20}}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('APP_ENV') == 'production'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    MAX_CONTENT_LENGTH = 32 * 1024
    WTF_CSRF_TIME_LIMIT = 7200
    TRUSTED_HOSTS = [host.strip() for host in os.environ.get('TRUSTED_HOSTS', '').split(',') if host.strip()] or None
