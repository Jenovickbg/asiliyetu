#!/usr/bin/env bash
set -euo pipefail
umask 077
backup_dir=/var/backups/asili-yetu
test -d "$backup_dir"
# Serialize manual and timer invocations; SQLite's backup API includes WAL data.
exec 9>"$backup_dir/.backup.lock"
flock -n 9 || exit 0
stamp=$(date -u +%Y%m%dT%H%M%S)
destination="$backup_dir/asili-yetu-$stamp-$$.db"
bash /opt/asili-yetu/deploy/manage.sh backup-db "$destination"
/opt/asili-yetu/.venv/bin/python - "$destination" <<'PY'
import sqlite3
import sys
with sqlite3.connect(sys.argv[1]) as connection:
    result = connection.execute('PRAGMA integrity_check').fetchone()[0]
    if result != 'ok':
        raise SystemExit('Sauvegarde invalide : ' + result)
print('Intégrité de la sauvegarde : OK')
PY
# Prune only dated backup files in this fixed directory, after successful verification.
find "$backup_dir" -maxdepth 1 -type f -name 'asili-yetu-*.db' -mtime +30 -delete
