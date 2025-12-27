# 2025 Holiday Bakeoff (Christmas Competition App)

A festive, real-time judging app for a holiday dessert bakeoff.

## Features
- **Real-time leaderboard** (updates instantly when judges submit scores)
- **Admin controls** to add/remove/disable participants, edit desserts, open/close voting
- **Criteria + weights** (taste, presentation, creativity, holiday spirit — fully editable)
- **Backups & restore** (export/import JSON, plus a 1-click timestamped backup)
- **Download DB** (admin-only) so you always have your raw data
- **Optional AI "Holiday Commentary"** to generate fun announcements (requires OpenAI API key)

## Local run
1. Install Python 3.11+
2. From the project folder:
   ```
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Set env vars:
   ```
   export SECRET_KEY='dev-secret'
   export ADMIN_PASSWORD='change-me'
   # optional:
   export OPENAI_API_KEY='...'
   ```
4. Start:
   ```
   python app.py
   ```
5. Open:
   - App: http://localhost:5000
   - Admin: http://localhost:5000/admin

## Deploy on Render with a disk (so data NEVER disappears)
Render free/ephemeral storage can be wiped on redeploy/restart. A **Disk** gives you a persistent folder.

1. In Render, open your service → **Disks** → **Add Disk**
   - Name: `bakeoff-data`
   - Mount path: `/var/data`
   - Size: 1GB+ (your call)
2. In Render, open your service → **Environment** and set:
   - `DATA_DIR` = `/var/data`
   - `SECRET_KEY` = (a long random string)
   - `ADMIN_PASSWORD` = (your admin password)
3. Set the **Start Command**:
   ```
   gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT app:app
   ```
4. Deploy.

### What the disk does
This app stores its SQLite database at:
- `${DATA_DIR}/bakeoff.sqlite3`

If `DATA_DIR=/var/data` is a mounted Render disk, your data survives restarts and deploys.

## Admin usage
- Login: `/admin` → enter `ADMIN_PASSWORD`
- Add people: type a name → Add Participant
- Add desserts: pick a participant → dessert name/description/category → Save
- Close voting: toggle **Voting open**
- Backups:
  - **Create Backup**: writes a timestamped JSON to `${DATA_DIR}/backups/`
  - **Export JSON**: downloads everything as one file
  - **Import JSON**: restores from a file (replace or merge)
  - **Download DB**: downloads the raw SQLite file

## AI Commentary (optional)
If you set `OPENAI_API_KEY`, the admin page can generate short "MC-style" commentary.
You can also set `OPENAI_MODEL` (default is `gpt-5`).

## Repo update (same Render link)
If you keep the same Render service connected to the same GitHub repo + disk:
- You can deploy new code while keeping the same URL.
- The data remains safe because it lives on the disk.

