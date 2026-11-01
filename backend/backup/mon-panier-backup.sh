#!/usr/bin/env bash
# Mon Panier : sauvegarde PostgreSQL quotidienne, sans suppression automatique.
set -Eeuo pipefail
umask 077

if [[ "$(hostname)" != "mon-panier-api" || "$(id -u)" -ne 0 ]]; then
  echo "STOP : execute uniquement en root sur mon-panier-api" >&2
  exit 1
fi

PANIER_STACK="/opt/mon-panier"
PANIER_BACKUP_DIR="/var/backups/mon-panier/daily"
install -d -m 700 "$PANIER_BACKUP_DIR"
cd "$PANIER_STACK"

# N'utiliser qu'un fichier temporaire dans le repertoire exact des sauvegardes.
PANIER_TEMP="$(mktemp "$PANIER_BACKUP_DIR/.dump-partial.XXXXXXXX")"
trap 'rm -f -- "$PANIER_TEMP"' EXIT

docker compose exec -T db pg_dump -U monpanier -d monpanier -Fc > "$PANIER_TEMP"
test -s "$PANIER_TEMP"
docker compose exec -T db pg_restore --list < "$PANIER_TEMP" > /dev/null

PANIER_FINAL="$PANIER_BACKUP_DIR/auto-$(date -u +%Y%m%d-%H%M%S)-$$.dump"
mv -- "$PANIER_TEMP" "$PANIER_FINAL"
(cd "$PANIER_BACKUP_DIR" && sha256sum -- "$(basename "$PANIER_FINAL")") > "$PANIER_FINAL.sha256"
echo "Sauvegarde locale verifiee : $PANIER_FINAL"

# Optionnel : configurer PANIER_OFFSITE_DIR vers un point de montage independant
# par exemple /mnt/mon-panier-backup (NFS/CIFS ou disque dedie).
# Jamais de copie dans un simple dossier de la VM si le montage est absent.
if [[ -n "${PANIER_OFFSITE_DIR:-}" ]]; then
  if [[ "$PANIER_OFFSITE_DIR" != /mnt/* || "$PANIER_OFFSITE_DIR" == /mnt/ ]]; then
    echo "STOP : PANIER_OFFSITE_DIR doit etre un montage sous /mnt/" >&2
    exit 1
  fi
  if ! mountpoint -q -- "$PANIER_OFFSITE_DIR"; then
    echo "ERREUR : sauvegarde distante non montee : $PANIER_OFFSITE_DIR" >&2
    exit 1
  fi
  cp -p -- "$PANIER_FINAL" "$PANIER_OFFSITE_DIR/"
  cp -p -- "$PANIER_FINAL.sha256" "$PANIER_OFFSITE_DIR/"
  (cd "$PANIER_OFFSITE_DIR" && sha256sum -c -- "$(basename "$PANIER_FINAL").sha256")
  echo "Copie hors VM verifiee : $PANIER_OFFSITE_DIR"
fi

# Les anciennes sauvegardes ne sont pas effacees par ce script.
