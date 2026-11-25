import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, IntegerField, DateField, TimeField, EmailField, TelField
from wtforms.validators import DataRequired, Length, Optional, Email, NumberRange, ValidationError


def clean(value):
    return ' '.join(value.split()) if value else value


def normalize_phone(value):
    value = re.sub(r'[\s().-]', '', value)
    if value.startswith('00243'):
        value = '+' + value[2:]
    if re.fullmatch(r'0[89]\d{8}', value):
        value = '+243' + value[1:]
    elif re.fullmatch(r'[89]\d{8}', value):
        value = '+243' + value
    elif re.fullmatch(r'243[89]\d{8}', value):
        value = '+' + value
    if not re.fullmatch(r'\+243[89]\d{8}', value):
        raise ValueError('Utilisez un numéro mobile congolais valide, par exemple +243 812 345 678.')
    return value


class FrenchForm(FlaskForm):
    class Meta:
        locales = ['fr']


class ReservationForm(FrenchForm):
    nom = StringField('Nom', filters=[clean], validators=[DataRequired(), Length(max=80)])
    postnom = StringField('Postnom', filters=[clean], validators=[DataRequired(), Length(max=80)])
    prenom = StringField('Prénom', filters=[clean], validators=[DataRequired(), Length(max=80)])
    telephone = TelField('Numéro de téléphone', filters=[clean], validators=[DataRequired(), Length(max=30)])
    email = EmailField('Adresse e-mail', filters=[clean], validators=[Optional(), Email(message='Indiquez une adresse e-mail valide.'), Length(max=254)])
    consent = BooleanField('J’accepte que mes données soient utilisées uniquement pour organiser les réservations de cette conférence.', validators=[DataRequired(message='Votre consentement est nécessaire pour réserver.')])

    def validate_telephone(self, field):
        try:
            normalize_phone(field.data)
        except ValueError as error:
            raise ValidationError(str(error))


class LoginForm(FrenchForm):
    username = StringField('Identifiant', filters=[clean], validators=[DataRequired(), Length(max=80)])
    password = PasswordField('Mot de passe', validators=[DataRequired(), Length(max=256)])


class SettingsForm(FrenchForm):
    max_participants = IntegerField('Capacité maximale', validators=[DataRequired(), NumberRange(min=1, max=100000)])
    registrations_open = BooleanField('Ouvrir les inscriptions')
    event_name = StringField('Nom de l’événement', filters=[clean], validators=[DataRequired(), Length(max=100)])
    slogan = StringField('Slogan', filters=[clean], validators=[DataRequired(), Length(max=150)])
    theme = StringField('Thème', filters=[clean], validators=[DataRequired(), Length(max=250)])
    event_date = DateField('Date', validators=[DataRequired()])
    start_time = TimeField('Début', validators=[DataRequired()])
    end_time = TimeField('Fin', validators=[DataRequired()])
    venue = StringField('Lieu', filters=[clean], validators=[DataRequired(), Length(max=150)])
    address = StringField('Adresse', filters=[clean], validators=[DataRequired(), Length(max=250)])


class PasswordForm(FrenchForm):
    current_password = PasswordField('Mot de passe actuel', validators=[DataRequired()])
    new_password = PasswordField('Nouveau mot de passe (12 caractères minimum)', validators=[DataRequired(), Length(min=12, max=256)])
