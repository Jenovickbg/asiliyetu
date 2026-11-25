# Mettre ASILI YETU en ligne sur un VPS Hostinger

Ce guide est prévu pour **un VPS neuf ou dédié sous Ubuntu 24.04 LTS**, avec accès root, et le domaine **asiliyetu.online**. Les fichiers sont préparés, mais aucune connexion à votre VPS ni publication GitHub n’a été effectuée. Ne réinstallez pas un VPS contenant déjà des sites : sa configuration doit alors être adaptée.

Architecture : navigateur → Caddy (HTTPS, ports 80/443) → Waitress (127.0.0.1:8000) → Flask → SQLite. Aucun port 5000 ou 8000 n’est à ouvrir sur Internet.

| Emplacement VPS | Contenu |
| --- | --- |
| `/opt/asili-yetu` | Code cloné depuis GitHub et environnement Python |
| `/etc/asili-yetu.env` | Secrets et configuration de production |
| `/var/lib/asili-yetu/asili_yetu.db` | Réservations, administrateurs et paramètres |
| `/var/backups/asili-yetu` | Sauvegardes quotidiennes, conservation de 30 jours |

## 1. Envoyer le projet sur GitHub depuis votre PC

Sur GitHub, créer un dépôt **privé**, nommé par exemple `asiliyetu`, vide (sans README, licence ou .gitignore ajoutés par GitHub). Puis dans PowerShell :

```powershell
cd C:\Users\jenov\OneDrive\Desktop\asiliyetu
git status
git add .
git diff --cached --name-only
```

Avant de valider, la liste doit contenir le code, les images et `deploy/`, mais **pas `.env`, `.venv/`, `instance/` ou une base `.db`**. Les règles `.gitignore` sont préparées ; les fichiers `.env.example` et `deploy/production.env.example` sont des modèles sans secret et doivent être publiés.

```powershell
git commit -m "Prepare ASILI YETU for VPS deployment"
git branch -M main
git remote add origin https://github.com/VOTRE_COMPTE/asiliyetu.git
git push -u origin main
```

Remplacer `VOTRE_COMPTE` par votre nom GitHub. Le dépôt Git local existe déjà. Si `origin` est déjà configuré, vérifier avec `git remote -v` et omettre `git remote add` s’il est correct. Utiliser la connexion GitHub proposée par Git Credential Manager ; ne pas mettre de jeton dans l’URL ni dans un fichier du projet.

Les mises à jour suivantes sur le PC : `git add .`, vérifier les fichiers, `git commit`, puis `git push`.

## 2. Préparer le VPS et le domaine

Dans Hostinger, relever l’IPv4 du VPS et ses informations SSH. Les paramètres du VPS se trouvent dans son tableau de bord. Dans la zone DNS qui gère réellement votre domaine, créer :

| Type | Nom | Valeur |
| --- | --- | --- |
| A | `@` | IPv4 du VPS |
| CNAME | `www` | `asiliyetu.online` |

Remplacer seulement les anciens enregistrements web conflictuels pour `@`/`www` ; conserver les enregistrements de messagerie. Ne laisser un enregistrement AAAA que si l’IPv6 pointe réellement vers ce VPS et que celui-ci accepte les connexions. Attendre que le DNS pointe vers le VPS avant l’étape HTTPS.

Depuis PowerShell :

```powershell
ssh root@IP_DU_VPS
```

**Les commandes suivantes, jusqu’à la fin du guide sauf mention contraire, s’exécutent dans le terminal Linux du VPS, en root.** Remplacer les valeurs en majuscules, notamment `IP_DU_VPS` et `VOTRE_COMPTE`.

```bash
apt update
apt upgrade -y
apt install -y python3 python3-venv python3-pip git curl ufw dnsutils openssh-client
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

Si votre SSH utilise un port personnalisé, autoriser **ce port avant `ufw enable`**. Dans le pare-feu Hostinger, autoriser également le port SSH utilisé et 80/443 TCP. Garder votre session SSH ouverte pendant les réglages. Aucun changement de port SSH n’est nécessaire pour ce guide.

## 3. Autoriser le VPS à lire le dépôt privé

Créer une clé dédiée au dépôt, dans un emplacement neuf :

```bash
mkdir -p /root/.ssh
chmod 700 /root/.ssh
ssh-keygen -t ed25519 -C "asili-yetu-vps" -f /root/.ssh/asili_github
cat /root/.ssh/asili_github.pub
```

Ne pas écraser une clé existante. Vous pouvez protéger la clé par une phrase secrète (elle sera demandée lors des mises à jour). Copier **seulement le contenu du fichier `.pub`** dans GitHub → dépôt → Settings → Deploy keys → Add deploy key. Ne pas cocher « Allow write access » : le VPS a seulement besoin de lire le dépôt.

Pour cette session, puis pour chaque future session de déploiement :

```bash
export GIT_SSH_COMMAND='ssh -i /root/.ssh/asili_github -o IdentitiesOnly=yes'
git clone git@github.com:VOTRE_COMPTE/asiliyetu.git /opt/asili-yetu
```

Lors de la première connexion SSH à GitHub, comparer l’empreinte affichée aux [empreintes officielles GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints) avant de l’accepter. La clé privée reste sur le VPS, jamais dans GitHub ou la conversation.

Pour un dépôt public, la clé de déploiement est facultative : `git clone https://github.com/VOTRE_COMPTE/asiliyetu.git /opt/asili-yetu` fonctionne sans authentification.

## 4. Installer l’application

```bash
useradd --system --user-group --home-dir /var/lib/asili-yetu --shell /usr/sbin/nologin asili
install -d -o asili -g asili -m 700 /var/lib/asili-yetu
install -d -o asili -g asili -m 700 /var/backups/asili-yetu
install -d -o root -g root -m 755 /opt/asili-yetu/instance
cd /opt/asili-yetu
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pytest -q
```

Le code appartient à root ; le service `asili` ne peut écrire que ses données. Le dossier `instance` vide satisfait Flask, mais la base réelle sera placée dans `/var/lib/asili-yetu`. Si un compte Linux `asili` existe déjà, vérifier son rôle et omettre `useradd` si c’est bien le compte de cette application.

Créer la configuration une seule fois, avec une clé générée sur le serveur. La commande refuse d’écraser un fichier existant :

```bash
python3 - <<'PY'
import os
import secrets
from pathlib import Path
os.umask(0o077)
path = Path('/etc/asili-yetu.env')
with path.open('x', encoding='utf-8') as output:
    output.write('APP_ENV=production\n')
    output.write('SECRET_KEY=' + secrets.token_urlsafe(48) + '\n')
    output.write('DATABASE_URL=sqlite:////var/lib/asili-yetu/asili_yetu.db\n')
    output.write('TRUSTED_HOSTS=asiliyetu.online,www.asiliyetu.online\n')
PY
chown root:asili /etc/asili-yetu.env
chmod 640 /etc/asili-yetu.env
```

Ne pas recopier le `.env` de développement, et ne pas changer cette clé à chaque mise à jour.

Initialiser la nouvelle base et créer votre administrateur :

```bash
sudo -u asili bash /opt/asili-yetu/deploy/manage.sh init-db
sudo -u asili bash /opt/asili-yetu/deploy/manage.sh create-admin
```

Le mot de passe est saisi à l’aveugle et doit avoir au moins 12 caractères. **Le compte local de votre PC n’est pas transféré automatiquement.** Le nouveau site commence avec une base vide et les horaires 12 h–16 h. Si vous voulez transférer des réservations locales, suivre la section « Transférer la base locale » avant de créer l’administrateur.

## 5. Démarrer le service de production

```bash
install -m 644 deploy/asili-yetu.service /etc/systemd/system/asili-yetu.service
systemctl daemon-reload
systemctl enable --now asili-yetu
systemctl status asili-yetu --no-pager
curl --fail -I -H 'Host: asiliyetu.online' http://127.0.0.1:8000/
```

La dernière commande doit retourner HTTP 200. Le service démarre automatiquement au redémarrage du VPS. Il écoute seulement sur `127.0.0.1:8000`. Ne pas utiliser `flask run` en production.

En cas d’échec :

```bash
journalctl -u asili-yetu -n 80 --no-pager
```

## 6. Installer Caddy et activer HTTPS

Installation depuis le dépôt officiel Caddy sur ce VPS neuf :

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' -o /tmp/caddy-stable.key
gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg /tmp/caddy-stable.key
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' -o /etc/apt/sources.list.d/caddy-stable.list
chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install -y caddy
```

Si Caddy est déjà installé, ne pas réinstaller le dépôt. Vérifier que les ports 80/443 ne sont pas occupés par nginx, Apache ou un autre site avant de poursuivre.

```bash
dig +short asiliyetu.online A
dig +short www.asiliyetu.online
cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.before-asili
install -m 644 /opt/asili-yetu/deploy/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl enable --now caddy
systemctl reload caddy
```

Les réponses DNS doivent désigner votre VPS. Caddy demande et renouvelle automatiquement les certificats et redirige HTTP vers HTTPS. `www.asiliyetu.online` redirige vers `asiliyetu.online`. Cette configuration remplace le Caddyfile du VPS dédié ; pour plusieurs sites, fusionner les blocs au lieu de remplacer le fichier.

Vérifier :

```bash
curl --fail -I https://asiliyetu.online/
curl --fail -I https://asiliyetu.online/reservation
curl -I https://www.asiliyetu.online/reservation
```

Accueil et réservation : HTTP 200. Domaine `www` : redirection vers le domaine principal. En cas de problème de certificat : `journalctl -u caddy -n 80 --no-pager`, puis vérifier DNS, AAAA, pare-feu, ports et éventuels enregistrements CAA. Ne pas désactiver la validation des certificats.

## 7. Activer les sauvegardes quotidiennes

```bash
install -m 644 /opt/asili-yetu/deploy/asili-yetu-backup.service /etc/systemd/system/
install -m 644 /opt/asili-yetu/deploy/asili-yetu-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl start asili-yetu-backup.service
systemctl enable --now asili-yetu-backup.timer
systemctl list-timers asili-yetu-backup.timer --no-pager
journalctl -u asili-yetu-backup -n 30 --no-pager
ls -lh /var/backups/asili-yetu/
```

La sauvegarde s’exécute chaque jour vers **03 h 15, heure de Kinshasa**, avec un décalage aléatoire maximal de 5 minutes. La copie utilise l’API SQLite (compatible WAL), puis vérifie son intégrité. Seules les sauvegardes datées de plus de 30 jours sont supprimées, après une nouvelle sauvegarde réussie.

Prévoir également une copie hors du VPS : les sauvegardes locales ne protègent pas d’une perte du serveur. Depuis votre PC, pour télécharger une sauvegarde précise :

```powershell
scp root@IP_DU_VPS:/var/backups/asili-yetu/NOM_EXACT_DE_LA_SAUVEGARDE.db .
```

Stocker cette copie hors du dépôt Git et dans un emplacement protégé.

## 8. Vérifier le site avant de diffuser le lien

- Ouvrir l’accueil sur ordinateur et téléphone : logos, sponsors, affiche et horaires 12 h–16 h.
- Réserver avec des coordonnées de test, vérifier la confirmation et son rafraîchissement.
- Se connecter à `/admin/connexion`, retrouver la réservation, tester l’export puis annuler la réservation de test.
- Vérifier fermeture/réouverture des inscriptions et capacité.
- Vérifier une sauvegarde et tester sa restauration sur une copie isolée.

Liens définitifs :

- Accueil : **https://asiliyetu.online/**
- Réservation à partager : **https://asiliyetu.online/reservation**
- Administration : **https://asiliyetu.online/admin/connexion**

## 9. Mettre le site à jour depuis GitHub

Après `git push` depuis votre PC, se reconnecter au VPS en root :

```bash
export GIT_SSH_COMMAND='ssh -i /root/.ssh/asili_github -o IdentitiesOnly=yes'
cd /opt/asili-yetu
git status --short
git rev-parse HEAD
systemctl start asili-yetu-backup.service
systemctl stop asili-yetu
git pull --ff-only origin main
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pytest -q
systemctl start asili-yetu
systemctl status asili-yetu --no-pager
curl --fail -I https://asiliyetu.online/
```

Exécuter les commandes une à une ; **s’arrêter en cas d’erreur**, avant de relancer le site avec du code non validé. Noter le SHA affiché par `git rev-parse HEAD`. La procédure implique une courte interruption. Ne pas écraser de modifications locales signalées par `git status`. La base et les secrets restent hors du dépôt et ne sont pas remplacés par `git pull`.

Si les fichiers systemd ou le Caddyfile ont changé, réinstaller les fichiers concernés, exécuter `systemctl daemon-reload` et valider Caddy avant son rechargement. `init-db` ne fait pas de migration : tout futur changement de schéma nécessite une migration préparée avant mise à jour.

Retour au code précédent, si nécessaire et sans migration incompatible de la base :

```bash
systemctl stop asili-yetu
git switch --detach SHA_PRECEDENT
.venv/bin/python -m pip install -r requirements-lock.txt
systemctl start asili-yetu
```

Pour reprendre plus tard les mises à jour, revenir sur `main` avec `git switch main`. Ne restaurer une ancienne base qu’en connaissance des réservations qui seraient perdues depuis cette sauvegarde.

## Transférer la base locale (facultatif)

Cette opération conserve les réservations, paramètres et comptes locaux. Ne l’effectuer qu’avant l’ouverture du site public, ou lors d’une migration planifiée avec arrêt des inscriptions.

Sur votre PC, depuis le projet :

```powershell
.\.venv\Scripts\python.exe -m flask --app app backup-db instance/transfert-vps.db
scp instance/transfert-vps.db root@IP_DU_VPS:/root/asili-transfert.db
```

Sur le VPS, avant `init-db` et `create-admin`, vérifier que la destination n’existe pas :

```bash
test ! -e /var/lib/asili-yetu/asili_yetu.db && install -o asili -g asili -m 600 /root/asili-transfert.db /var/lib/asili-yetu/asili_yetu.db
```

Si la commande échoue parce que la base existe déjà, ne pas l’écraser. Utiliser la procédure de restauration ci-dessous après sauvegarde. Avec une base importée, ne pas recréer un identifiant administrateur déjà présent.

## Restaurer une sauvegarde sur le VPS

Arrêter application et timer pour éviter tout accès pendant la restauration. Archiver la base courante **avec ses fichiers WAL/SHM**, puis installer une sauvegarde vérifiée. Remplacer le chemin de sauvegarde ci-dessous avant exécution :

```bash
(
set -euo pipefail
backup_file=/var/backups/asili-yetu/NOM_EXACT_DE_LA_SAUVEGARDE.db
test -f "$backup_file"
/opt/asili-yetu/.venv/bin/python - "$backup_file" <<'PY'
import sqlite3
import sys
with sqlite3.connect(sys.argv[1]) as connection:
    if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise SystemExit('Sauvegarde invalide : restauration interrompue.')
PY
systemctl stop asili-yetu-backup.timer
systemctl stop asili-yetu-backup.service
systemctl stop asili-yetu
archive_dir="/var/backups/asili-yetu/avant-restauration-$(date -u +%Y%m%dT%H%M%S)"
install -d -m 700 "$archive_dir"
for file in /var/lib/asili-yetu/asili_yetu.db /var/lib/asili-yetu/asili_yetu.db-wal /var/lib/asili-yetu/asili_yetu.db-shm; do
    if [ -f "$file" ]; then mv -- "$file" "$archive_dir/"; fi
done
install -o asili -g asili -m 600 "$backup_file" /var/lib/asili-yetu/asili_yetu.db
systemctl start asili-yetu
curl --fail -I https://asiliyetu.online/
systemctl start asili-yetu-backup.timer
)
```

Ne pas continuer si l’installation de la sauvegarde échoue. Ne pas associer une base restaurée aux anciens fichiers WAL/SHM. Confirmer le nombre de réservations dans l’administration après restauration.

## Références officielles

- [Hostinger : relier le domaine au VPS](https://www.hostinger.com/support/1583227-how-to-point-a-domain-to-your-vps-at-hostinger/)
- [Hostinger : connexion SSH](https://www.hostinger.com/support/5723772-how-to-connect-to-your-vps-via-ssh-at-hostinger/)
- [GitHub : clés de déploiement](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys)
- [Caddy : installation Ubuntu](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)
- [Caddy : HTTPS automatique](https://caddyserver.com/docs/automatic-https)
- [Waitress : configuration du proxy de confiance](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html)

Les services Linux, l’émission du certificat HTTPS et la restauration réelle doivent être vérifiés sur le VPS ; ils ne sont pas considérés validés par les tests Windows locaux.

Vérifications locales du 25 novembre 2026 : **39 tests automatisés réussis**, dont les en-têtes du proxy de confiance, le refus des domaines non autorisés, les cookies HTTPS et le refus des configurations de production incomplètes. La syntaxe des scripts Bash a été contrôlée sans exécution. Les secrets et la base locale sont bien exclus par Git.
