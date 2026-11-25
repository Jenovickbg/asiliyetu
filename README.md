# ASILI YETU — Réservations

**Hébergement Hostinger VPS + GitHub : suivre [DEPLOIEMENT_VPS.md](DEPLOIEMENT_VPS.md).** Les fichiers prêts à installer (Caddy, systemd, sauvegardes) se trouvent dans `deploy/`.

Application Flask en français pour la Fondation DYNASTIE Bantou. Réservation gratuite, confirmation à l’écran et administration privée. Aucun e-mail, SMS, QR code ou billet n’est envoyé.

## Installation locale (Windows / PowerShell)

Python 3.11 ou supérieur est recommandé. Depuis ce dossier :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Reporter la clé générée dans `SECRET_KEY` du fichier `.env`. Ne jamais publier ce fichier. Lors de la réalisation initiale, un `.env` local avec une clé aléatoire a déjà été créé : il est inutile de l’écraser.

```powershell
.\.venv\Scripts\python.exe -m flask --app app init-db
.\.venv\Scripts\python.exe -m flask --app app create-admin
.\.venv\Scripts\python.exe -m flask --app app run
```

Le compte administrateur est créé par saisie interactive : identifiant et mot de passe masqué, confirmé, de 12 à 256 caractères. Aucun compte par défaut n’existe. La commande `init-db` conserve les données existantes ; elle ne réalise pas de migrations de schéma.

Accueil : http://127.0.0.1:5000 — Administration : http://127.0.0.1:5000/admin

Sur macOS/Linux, utiliser `.venv/bin/python` à la place de `.\.venv\Scripts\python.exe`.

## Fonctionnement

- Une réservation individuelle par téléphone et par e-mail, avec e-mail facultatif stocké en `NULL` lorsqu’il est absent.
- Numéros mobiles RDC : `0812345678`, `812345678`, `243812345678`, `+243 812 345 678`, `00243812345678` sont normalisés vers `+243812345678`. Espaces, points, tirets et parenthèses acceptés. Les numéros étrangers et fixes ne sont pas pris en charge.
- Les adresses e-mail sont validées et normalisées en minuscules.
- Les réservations actives déterminent les places restantes. À capacité atteinte, les nouvelles réservations sont refusées automatiquement. Une annulation libère une place si les inscriptions restent ouvertes.
- **Après annulation**, le téléphone et l’e-mail restent réservés : une nouvelle inscription avec ces coordonnées est refusée. La trace administrative est conservée (`statut`, `cancelled_at`). Il n’existe pas de suppression physique ni de réactivation publique.
- Le contrôle de capacité et l’insertion s’exécutent sous `BEGIN IMMEDIATE` : SQLite sérialise ces opérations, y compris entre processus. Les modifications de capacité et annulations utilisent le même verrou d’écriture.
- La confirmation n’est accessible qu’au navigateur ayant réservé via sa session signée. Elle n’utilise aucun identifiant dans l’URL ; un rafraîchissement ne réenvoie pas le formulaire (redirection après POST).
- Administration : recherche par nom/postnom/prénom/téléphone, tri, pagination (20 lignes), annulation avec confirmation JavaScript, export CSV de toutes les inscriptions, paramètres et changement de mot de passe.
- Le CSV utilise UTF-8 avec BOM et point-virgule pour Excel ; les cellules pouvant être interprétées comme formules sont neutralisées.
- Les horaires de réservation sont enregistrés en UTC, affichés en heure de Kinshasa (UTC+1).
- Modifier l’événement met aussi à jour les confirmations existantes ; les détails de l’événement ne constituent pas un historique figé.

## Logos et affiche officielle

Déposer les fichiers réels, sans modifier leur nom :

```text
static/images/logo-horizontal.png
static/images/logo-asili-yetu.png
static/images/logo-compact.png
static/images/affiche-officielle.jpg
```

Le site les détecte automatiquement au prochain chargement. Le logo compact sert aussi de favicon. L’affiche apparaît dans le hero, conserve son ratio et peut être agrandie dans une fenêtre native fermable avec Échap. Elle est également utilisée en Open Graph. Aucune affiche ni aucun logo de remplacement n’a été fabriqué ; sans fichiers, une signature textuelle et un emplacement signalé sont affichés.

Les logos officiels DYNASTIE Bantou et ASILI YETU fournis le 24 novembre 2026 sont intégrés. Les PNG originaux sont conservés sans retouche. Leurs grandes marges transparentes sont exclues uniquement de l’affichage par les fenêtres SVG de `templates/_logos.html` : aucun élément du dessin n’est coupé. Le logo de la Fondation apparaît dans l’en-tête et le pied de page ; celui de l’événement apparaît sur fond crème dans l’accueil. Si de nouveaux fichiers ont des dimensions ou marges différentes, adapter ces fenêtres d’affichage. Le logo compact reste à fournir.

Optimiser une copie de l’affiche sans recadrage ni perte de lisibilité (environ 1 200 à 1 600 pixels de large, idéalement moins de 500 Ko). Conserver l’original hors du dossier public. Les polices sont locales au système, aucun CDN ni traceur n’est chargé.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Les tests utilisent des bases temporaires isolées et conservent le CSRF actif. Ils vérifient les réservations avec/sans e-mail, les doublons normalisés, les validations, le consentement, la fermeture, la capacité, deux demandes concurrentes pour la dernière place, l’authentification et les accès privés, l’annulation, la confirmation et son rafraîchissement, la persistance des paramètres après recréation de l’application, l’export, l’échappement HTML, le changement de mot de passe, la limitation de connexion, les commandes et la sauvegarde.

Validation effectuée le 22 novembre 2026 : **32 tests réussis**. L’accueil a été inspecté visuellement dans le navigateur ; le formulaire a été ouvert via son bouton. Les mesures du document aux largeurs 390 et 820 pixels n’ont révélé aucun débordement horizontal sur les pages contrôlées. La capture d’écran aux dimensions simulées a échoué dans l’outil : la validation visuelle complète sur appareils mobiles réels, la confirmation et le tableau de bord restent à effectuer. Les parcours serveur de ces pages sont couverts par les tests automatisés. Les visuels officiels absents n’ont pas pu être contrôlés.

## Sauvegarde et restauration

La base par défaut est `instance/asili_yetu.db`, exclue de Git. Pour une sauvegarde cohérente, même en mode WAL :

```powershell
.\.venv\Scripts\python.exe -m flask --app app backup-db C:/sauvegardes/asili-2026-12-19.db
```

La destination doit être nouvelle : la commande refuse l’écrasement. Protéger les sauvegardes comme les données originales et vérifier régulièrement une restauration. Pour restaurer : arrêter tous les processus de l’application, archiver le dossier `instance` complet (y compris les fichiers `-wal` et `-shm` éventuels), puis placer la sauvegarde dans un nouveau dossier persistant et configurer `DATABASE_URL` vers celle-ci. Ne pas juxtaposer une ancienne base avec des fichiers WAL provenant d’une autre version.

## Production

1. Utiliser un disque local persistant hors du dossier servi publiquement ; éviter SQLite sur un partage réseau et hors d’un dossier synchronisé OneDrive. Le dossier de travail actuel convient au développement, pas à l’hébergement de données réelles.
2. Définir une clé secrète forte et stable via l’environnement, `APP_ENV=production` et une URL SQLite absolue, par exemple `DATABASE_URL=sqlite:///C:/donnees/asili_yetu.db` (Linux : `sqlite:////srv/asili/asili_yetu.db`).
3. Installer les dépendances, initialiser la base et créer l’administrateur sur l’hôte.
4. Utiliser Waitress derrière un serveur HTTPS (Caddy, nginx ou équivalent), jamais `flask run` :

```powershell
.\.venv\Scripts\waitress-serve.exe --host=127.0.0.1 --port=8000 --call app:create_app
```

5. Le reverse proxy doit transmettre le schéma HTTPS correctement. Avec Waitress, configurer explicitement son proxy de confiance et les en-têtes transmis, uniquement pour l’adresse du proxy ; ne pas exposer le port applicatif à Internet. Les cookies `Secure` sont obligatoires en production : les formulaires nécessitent donc HTTPS.
6. La limitation de fréquence est persistée en SQLite : 12 soumissions de réservation par 10 minutes et 8 tentatives de connexion/changement de mot de passe par 15 minutes, par IP. Les IP sont hachées avec la clé secrète ; les compteurs expirés sont purgés lors des soumissions. Sans configuration du proxy de confiance, plusieurs utilisateurs peuvent partager l’IP du proxy. Régler la transmission fiable de l’IP et compléter avec une limitation au reverse proxy selon le trafic réel.
7. Activer les sauvegardes automatiques, restreindre les permissions du dossier de données, surveiller les erreurs et définir une durée de conservation des données avec la Fondation. L’application ne supprime pas automatiquement les participants après l’événement.
8. Vérifier les visuels officiels, le partage WhatsApp/Facebook sur le domaine HTTPS définitif, les parcours sur les appareils visés, et créer un mot de passe administrateur unique avant ouverture au public.

Protection CSRF sur toutes les actions POST, mots de passe hachés par Werkzeug, cookies HttpOnly/SameSite, sessions administrateur limitées à deux heures, requêtes ORM paramétrées, échappement Jinja, CSP et absence de mise en cache des pages privées. Aucun secret ou compte de production n’est inclus. La modification du mot de passe déconnecte la session courante ; les autres sessions existantes expirent selon leur durée de vie (changer la clé secrète permet de toutes les invalider immédiatement).

## Structure

`app.py` : fabrique d’application, routes et commandes. `models.py` : modèles SQLite. `forms.py` : formulaires et normalisation. `config.py` : configuration. `templates/` : pages françaises. `static/` : styles, JavaScript et visuels officiels. `tests/` : tests d’intégration.

`requirements.txt` décrit les versions compatibles ; `requirements-lock.txt` capture les versions exactes validées dans l’environnement de développement. Pour une installation reproductible, utiliser `pip install -r requirements-lock.txt`.
