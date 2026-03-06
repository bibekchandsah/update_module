# ============================================================
#  updater/config.py  —  Developer Configuration
#  Modify ONLY the variables in this file for your application
# ============================================================

# ── Your application ─────────────────────────────────────────
CURRENT_VERSION = "v0.0.1"
GITHUB_REPO     = "username/repo"   # e.g. "bibekchandsah/brightness"

# Optional: GitHub Personal Access Token (PAT)
# Without a token: 60 requests/hour  (shared per public IP)
# With a token:  5 000 requests/hour
# Create one at https://github.com/settings/tokens  (no scopes needed for public repos)
# Set to None or "" to use unauthenticated requests.
GITHUB_TOKEN = ""   # e.g. "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# ── Update behaviour ─────────────────────────────────────────
AUTO_UPDATE     = True   # Check for updates automatically on startup
AUTO_DOWNLOAD   = False  # Silently download without asking the user
AUTO_RESTART    = True   # Restart automatically after download completes

# ── Scheduling ───────────────────────────────────────────────
CHECK_INTERVAL_HOURS = 6   # How often to re-check (0 = disabled)

# ── Storage ──────────────────────────────────────────────────
DOWNLOAD_FOLDER = "updates"   # Relative to the application directory

# ── Release filtering ────────────────────────────────────────
ALLOW_PRERELEASE = False
UPDATE_CHANNEL   = "stable"   # "stable" | "beta" | "nightly"

# ── Asset selection ──────────────────────────────────────────
# Set to None for auto-detection (.exe → .zip → first asset)
# Or specify an exact filename, e.g. "MyApp.exe" or "MyApp.zip"
ASSET_FILENAME = None

# ── Security ─────────────────────────────────────────────────
VERIFY_CHECKSUM    = False          # Verify SHA-256 after download
CHECKSUM_FILENAME  = "checksum.txt" # Filename in the release assets
