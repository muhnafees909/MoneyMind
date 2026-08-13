#!/usr/bin/env bash
#
# Enforce the backup retention window on the B2 bucket.
#
#   daily/   keep DAILY_RETENTION_DAYS  (default 14) — the "oops, I dropped a table" window
#   weekly/  keep WEEKLY_RETENTION_DAYS (default 63) — ~2 months of Sunday snapshots
#
# Age comes from the date embedded in the object key (moneymind_backup_YYYY-MM-DD.dump),
# not from the object's mtime, so re-uploading or server-side-copying a file never
# resets its clock.
#
# Environment:
#   B2_BUCKET, B2_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
#   DAILY_RETENTION_DAYS   (optional, default 14)
#   WEEKLY_RETENTION_DAYS  (optional, default 63)
#   MIN_KEEP               (optional, default 3)  newest N per prefix are never deleted
#   DRY_RUN=1              (optional) print deletions instead of performing them
#   BACKUP_LIST_FILE       (optional) read keys from this file instead of calling B2;
#                                     used by the local test harness
set -euo pipefail

# AWS CLI v2 sends output through a pager unless told not to; it has no business
# running here, and on some platforms it errors or blocks. Safe to set unconditionally.
export AWS_PAGER=''

DAILY_RETENTION_DAYS="${DAILY_RETENTION_DAYS:-14}"
WEEKLY_RETENTION_DAYS="${WEEKLY_RETENTION_DAYS:-63}"
MIN_KEEP="${MIN_KEEP:-3}"
DRY_RUN="${DRY_RUN:-0}"

if [ -z "${BACKUP_LIST_FILE:-}" ]; then
  : "${B2_BUCKET:?B2_BUCKET is required}"
  : "${B2_ENDPOINT:?B2_ENDPOINT is required}"
fi

# List every key under a prefix, one per line.
list_keys() {
  local prefix="$1"
  if [ -n "${BACKUP_LIST_FILE:-}" ]; then
    grep -E "^${prefix}" "$BACKUP_LIST_FILE" || true
  else
    aws s3api list-objects-v2 \
      --bucket "$B2_BUCKET" \
      --prefix "$prefix" \
      --endpoint-url "$B2_ENDPOINT" \
      --query 'Contents[].Key' \
      --output text 2>/dev/null | tr '\t' '\n' | grep -v '^None$' || true
  fi
}

delete_key() {
  local key="$1"
  if [ "$DRY_RUN" = "1" ]; then
    echo "  [dry-run] would delete ${key}"
    return
  fi
  aws s3api delete-object \
    --bucket "$B2_BUCKET" \
    --key "$key" \
    --endpoint-url "$B2_ENDPOINT" > /dev/null
  echo "  deleted ${key}"
}

prune_prefix() {
  local prefix="$1" retention_days="$2"
  local cutoff kept=0 deleted=0 total=0

  cutoff="$(date -u -d "${retention_days} days ago" +%Y-%m-%d)"
  echo "Pruning ${prefix} — keeping backups dated ${cutoff} or newer (${retention_days} days)."

  # Newest first, so the MIN_KEEP guard protects the most recent backups.
  # LC_ALL=C so ordering is plain bytewise and does not shift with the runner's locale.
  local keys
  keys="$(list_keys "$prefix" | LC_ALL=C sort -r)"
  [ -n "$keys" ] || { echo "  (nothing under ${prefix})"; return; }

  while IFS= read -r key; do
    [ -n "$key" ] || continue

    if [[ ! "$key" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
      echo "  skipping ${key} (no date in the key — not ours to delete)"
      continue
    fi
    local key_date="${BASH_REMATCH[1]}"
    # Only dated backups count toward MIN_KEEP; a stray unrelated object in the
    # bucket must not consume one of the protected slots.
    total=$((total + 1))

    # Safety net: never let a bad clock or a misconfigured retention value empty the
    # bucket. The newest MIN_KEEP objects survive regardless of how old they look.
    if [ "$total" -le "$MIN_KEEP" ]; then
      kept=$((kept + 1))
      continue
    fi

    # ISO-8601 dates compare correctly as plain strings.
    if [[ "$key_date" < "$cutoff" ]]; then
      delete_key "$key"
      deleted=$((deleted + 1))
    else
      kept=$((kept + 1))
    fi
  done <<< "$keys"

  echo "  ${prefix}: ${kept} kept, ${deleted} deleted (${total} seen)."
}

echo "Retention: daily=${DAILY_RETENTION_DAYS}d weekly=${WEEKLY_RETENTION_DAYS}d min_keep=${MIN_KEEP} dry_run=${DRY_RUN}"
prune_prefix "daily/" "$DAILY_RETENTION_DAYS"
prune_prefix "weekly/" "$WEEKLY_RETENTION_DAYS"
echo "Retention pass complete."
