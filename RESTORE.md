# Database Backup & Restore

Production data lives in **Neon Postgres**. The app itself runs on Render, which only
holds the `DATABASE_URL` pointing at Neon — restoring means restoring Neon, then
re-pointing Render at the result.

Backups are taken by [`.github/workflows/db-backup.yml`](.github/workflows/db-backup.yml):
daily at **03:00 UTC**, plus on demand via **Actions → Database Backup → Run workflow**.

---

## 1. Emergency restore — the short version

If the database is gone and you need it back right now:

```bash
# 1. Find the newest backup
aws s3 ls s3://$B2_BUCKET/daily/ --endpoint-url $B2_ENDPOINT

# 2. Download it
aws s3 cp s3://$B2_BUCKET/daily/moneymind_backup_2026-08-13.dump . \
  --endpoint-url $B2_ENDPOINT

# 3. Restore into a fresh, empty Neon database (direct URL, not -pooler)
pg_restore --no-owner --no-privileges --clean --if-exists \
  -d "postgresql://USER:PASS@ep-xxxx.REGION.aws.neon.tech/neondb?sslmode=require" \
  moneymind_backup_2026-08-13.dump

# 4. Point Render's DATABASE_URL at the restored database and redeploy.
```

Then read [section 5](#5-after-the-restore--do-not-skip-this), which covers the one
thing that will silently break if you miss it (Plaid token decryption).

---

## 2. Before you restore from a dump: check Neon's own recovery first

A dump restore loses everything written since the last 03:00 UTC run. Neon has two
faster, lower-loss options — try these first:

- **Point-in-time restore / branching.** Neon retains a history window (7 days on the
  free plan, longer on paid). In the Neon console: **Branches → Restore**, pick a
  timestamp *just before* the incident. This recovers data written since the last
  nightly dump, which the dump physically cannot.
- **Branch from an existing branch.** If only one table was damaged, branch the database
  at a past timestamp, then copy just that table across instead of rolling everything back.

Use the B2 dump when Neon's history window has already passed, when the whole Neon
project is gone, or when you are rebuilding somewhere else entirely.

---

## 3. Full restore, step by step

### 3.1 Get the tools

You need Postgres client tools whose major version is **at least** the server's.

```bash
# macOS
brew install libpq && brew link --force libpq
# Ubuntu/Debian — Neon was running Postgres 18.4 as of 2026-08-17
sudo apt-get install -y postgresql-client-18
# Windows: install PostgreSQL from postgresql.org and use the bundled psql/pg_restore,
# or just run the restore from a GitHub Codespace / any Linux box.

pg_restore --version
```

You also need the AWS CLI (B2 speaks the S3 API) configured with the same B2 key used by
the backup job:

```bash
export AWS_ACCESS_KEY_ID=<B2_KEY_ID>           # from the GitHub secret / Backblaze
export AWS_SECRET_ACCESS_KEY=<B2_APPLICATION_KEY>
export AWS_DEFAULT_REGION=us-east-005
export B2_BUCKET=moneymind-db-backup
export B2_ENDPOINT=https://s3.us-east-005.backblazeb2.com
export AWS_PAGER=''                            # AWS CLI v2 otherwise pipes through a pager
```

The two key values are deliberately not written down here — read them from the GitHub
repository secrets, or mint a fresh application key in the Backblaze console (the bucket
contents are readable by any key with `readFiles` on this bucket).

### 3.2 Pick and download a backup

```bash
# Daily backups (last 14 days)
aws s3 ls s3://$B2_BUCKET/daily/  --endpoint-url $B2_ENDPOINT
# Weekly Sunday snapshots (last ~9 weeks)
aws s3 ls s3://$B2_BUCKET/weekly/ --endpoint-url $B2_ENDPOINT

aws s3 cp s3://$B2_BUCKET/daily/moneymind_backup_YYYY-MM-DD.dump . \
  --endpoint-url $B2_ENDPOINT
```

Confirm the file is a valid archive **before** you touch any database:

```bash
pg_restore --list moneymind_backup_YYYY-MM-DD.dump | head -30
```

That lists the restorable objects. If it errors, the file is truncated — use the
previous day's backup instead.

### 3.3 Create a destination database

In the [Neon console](https://console.neon.tech): create a new project (or a new branch
of the existing one), then copy its connection string.

**Use the direct connection string, not the pooled one.** Neon shows both; the pooled
host has `-pooler` in it:

```
pooled  → ep-wandering-sky-xxxx-pooler.c-5.us-east-2.aws.neon.tech   ← not for restore
direct  → ep-wandering-sky-xxxx.c-5.us-east-2.aws.neon.tech          ← use this
```

The pooled endpoint runs PgBouncer in transaction mode, which cannot carry the
session-level state `pg_restore` relies on.

### 3.4 Restore

```bash
export TARGET="postgresql://USER:PASS@ep-xxxx.REGION.aws.neon.tech/neondb?sslmode=require"

pg_restore \
  --no-owner \
  --no-privileges \
  --clean --if-exists \
  --jobs=4 \
  --dbname="$TARGET" \
  moneymind_backup_YYYY-MM-DD.dump
```

| Flag | Why |
| --- | --- |
| `--no-owner` / `--no-privileges` | The dump was taken without role info; Neon role names differ per project, so a restore that tried to reassign ownership would fail. |
| `--clean --if-exists` | Drops existing objects first. **Omit both if the target is already empty** — they are only needed when overwriting a populated database. |
| `--jobs=4` | Parallel restore. Only valid with a custom-format dump (which is what the job produces). |

Some harmless noise is expected on a fresh database: `role does not exist`, `schema
public already exists`, and errors from `DROP ... IF EXISTS` on objects that were never
there. What matters is that the command exits 0 and the verification below passes.

To read the dump as plain SQL instead (useful for extracting one table by hand):

```bash
pg_restore -f - moneymind_backup_YYYY-MM-DD.dump | less
```

### 3.5 Verify the restore

```bash
psql "$TARGET" -c "\dt"

# Note: the users table is named "user" (singular) — a reserved word in Postgres,
# so it must stay double-quoted.
psql "$TARGET" -c "
  SELECT 'user' t, count(*) FROM \"user\"
  UNION ALL SELECT 'transactions', count(*) FROM transactions
  UNION ALL SELECT 'budgets', count(*) FROM budgets
  UNION ALL SELECT 'financial_goals', count(*) FROM financial_goals
  UNION ALL SELECT 'plaid_items', count(*) FROM plaid_items
  UNION ALL SELECT 'envelope_allocations', count(*) FROM envelope_allocations;"

# Migration state travels inside the dump — this should match the newest file
# in backend/migrations/versions/, meaning no 'flask db upgrade' is needed.
psql "$TARGET" -c "SELECT version_num FROM alembic_version;"
```

---

## 4. Re-point the application

1. Render dashboard → the MoneyMind backend service → **Environment**.
2. Set `DATABASE_URL` to the new connection string. For the running app, the **pooled**
   (`-pooler`) URL is the right choice — the app opens many short-lived connections, which
   is exactly what the pooler is for. Direct is only for dump/restore.
3. Save and let it redeploy.
4. Smoke-test: log in, load the dashboard, open Transactions, confirm balances look right.

---

## 5. After the restore — do not skip this

**Plaid access tokens are Fernet-encrypted at rest** (`backend/utils/token_crypto.py`),
with the key from `PLAID_TOKEN_ENCRYPTION_KEY` (falling back to `JWT_SECRET_KEY`). The
dump contains the *encrypted* tokens.

If the restored app runs with a **different** `PLAID_TOKEN_ENCRYPTION_KEY` than the one in
use when those rows were written, every stored Plaid token becomes permanently
undecryptable — bank syncing breaks and every user has to reconnect their bank through
Plaid Link. Nothing else visibly fails, which is what makes it easy to miss.

So: **keep `PLAID_TOKEN_ENCRYPTION_KEY` (and `JWT_SECRET_KEY`, if it is the fallback in
use) identical to the values from before the incident.** Store them somewhere outside
Render before you ever need them. If the key really is lost, the recovery path is to
clear the `plaid_items` / `plaid_accounts` tables and have users reconnect.

Also worth knowing:

- Rotating `JWT_SECRET_KEY` invalidates every active session — everyone is logged out.
  Harmless, but expect the support noise.
- Manual transactions, budgets, goals, and envelope ledger rows restore completely.
- Plaid `sync_cursor` values restore too, so transaction sync resumes incrementally
  rather than re-pulling history.

---

## 6. Retention policy

| Tier | Prefix | Kept for | Contents |
| --- | --- | --- | --- |
| Daily | `daily/` | 14 days | Every night's dump |
| Weekly | `weekly/` | 63 days (~9 weeks) | A copy of each Sunday's dump |

Pruning runs at the end of every backup, in
[`.github/scripts/prune-backups.sh`](.github/scripts/prune-backups.sh). Age is read from
the date in the filename, not the object's mtime, so copying a file never resets its clock.
Two guardrails: the newest 3 objects in each prefix are never deleted regardless of age
(so a clock or config error cannot empty the bucket), and objects whose names contain no
date are skipped entirely.

Tune the window by editing the `DAILY_RETENTION_DAYS` / `WEEKLY_RETENTION_DAYS` defaults
in that script. Dry-run any change first:

```bash
DRY_RUN=1 bash .github/scripts/prune-backups.sh
```

---

## 7. Required GitHub secrets

**Settings → Secrets and variables → Actions → New repository secret.** All eight are
needed; the workflow fails on the first step with a clear message if any are missing.

| Secret name | Value |
| --- | --- |
| `BACKUP_DATABASE_URL` | Neon **direct** (non-pooled) connection string — Neon console → Connection Details → toggle *Connection pooling* **off**. Looks like `postgresql://neondb_owner:PASS@ep-wandering-sky-ayv4d6hl.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require`. Note there is **no** `-pooler` in the host. (If you paste the pooled URL by mistake the job rewrites it and logs a warning, but set it correctly.) |
| `B2_KEY_ID` | Backblaze **keyID** for the `moneymind-backup-github-actions` key (starts `005051d5...`). |
| `B2_APPLICATION_KEY` | Backblaze **applicationKey** for that same key — shown exactly once at creation. If it was not saved, delete the key and create a replacement. |
| `B2_BUCKET` | `moneymind-db-backup` |
| `B2_ENDPOINT` | `https://s3.us-east-005.backblazeb2.com` |
| `B2_REGION` | `us-east-005` |
| `RESEND_API_KEY` | Existing Resend API key (`re_...`) — the same one the backend uses. |
| `BACKUP_ALERT_EMAIL_TO` | Where failure alerts go, e.g. `ahsannafees909@gmail.com`. |
| `BACKUP_ALERT_EMAIL_FROM` | Optional. Sender, e.g. `MoneyMind <alerts@yourdomain.com>`. Defaults to `MoneyMind <onboarding@resend.dev>`, which Resend only delivers to the address that owns the Resend account. |

### Backblaze setup

Already provisioned: private bucket `moneymind-db-backup` in `us-east-005`, with an
application key named `moneymind-backup-github-actions` restricted to that bucket. Its
capabilities were verified to include `readFiles`, `writeFiles`, `listFiles`, and
`deleteFiles` — the last is what the retention pass needs. B2's free tier is 10 GB, far
more than these dumps will use for a long time.

**To rotate the key** (do this if it is ever pasted somewhere it shouldn't be):

1. Backblaze console → **Application Keys → Add a New Application Key**.
2. Name it, restrict it to `moneymind-db-backup` only, grant **Read and Write**.
3. Copy `keyID` and `applicationKey` — the secret is shown exactly once.
4. Update the `B2_KEY_ID` and `B2_APPLICATION_KEY` GitHub secrets.
5. Run the workflow manually to confirm the new key works, **then** delete the old key.
   Deleting first means a failed run with no way back.

---

## 8. Testing and troubleshooting

**Run it manually:** Actions → **Database Backup** → **Run workflow** → *Run workflow*.
A green run means dump + verify + upload + retention all succeeded; the run summary shows
the filename and byte size. Confirm the object is really there:

```bash
aws s3 ls s3://$B2_BUCKET/daily/ --endpoint-url $B2_ENDPOINT
```

**Last verified end to end: 2026-08-17.** A manual run produced
`daily/moneymind_backup_2026-08-17.dump` (64 KiB) in B2; the archive was downloaded and
checked with `pg_restore --list`, showing 182 entries and all 19 tables including
`alembic_version`. Server was Postgres 18.4.

**Test the restore path, not just the backup.** A backup nobody has restored is a guess.
Once a quarter, restore the newest dump into a throwaway Neon branch and run the row-count
query from §3.5. That is the only thing that actually proves this works.

| Symptom | Cause and fix |
| --- | --- |
| `server version mismatch` in pg_dump | Neon's major version moved past the installed client. The workflow auto-detects the server version and installs a matching client, so this should not happen; if detection failed it logs a warning and falls back to major 18. If Neon has since moved to 19+, bump that fallback in the workflow's install step. |
| `SSL connection has been closed unexpectedly` | Usually the pooled endpoint. Confirm `BACKUP_DATABASE_URL` has no `-pooler`. |
| `SignatureDoesNotMatch` on upload | `B2_REGION` doesn't match the region inside `B2_ENDPOINT`. They must agree. |
| `AccessDenied` on upload or prune | The B2 application key lacks write/delete, or is scoped to a different bucket. Recreate it with Read and Write on this bucket. |
| Job succeeds, no failure email arrives | Alerts only send on failure. If a real failure sent nothing, check `RESEND_API_KEY` / `BACKUP_ALERT_EMAIL_TO`, and note that the `onboarding@resend.dev` sender only delivers to the Resend account owner's own address. |
| Dump under 10 KB | Deliberate failure — the job refuses to upload a suspiciously small dump rather than quietly replacing good backups with an empty one. Check that `BACKUP_DATABASE_URL` points at the production database and not an empty one. |
