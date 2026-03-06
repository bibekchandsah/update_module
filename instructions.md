

## Python Application Auto-Update Module (PyQt6)

### Goal

Create a **reusable Python module** that developers can import into their applications to enable **automatic update checking, downloading, and installing** from GitHub Releases.

The module must:

* Work with **any Python desktop application**
* Use **PyQt6 for GUI elements**
* Show **system tray notifications**
* Automatically check updates
* Download updates with **progress, speed, ETA**
* Allow **manual "Check for Updates"**
* Allow **auto restart after update**
* Be configurable by the developer

The developer should only need to **import the module and modify a few variables**.

Example usage:

```python
from updater import UpdateManager

CURRENT_VERSION = "v0.0.1"
GITHUB_REPO = "bibekchandsah/brightness"

UpdateManager.initialize(
    current_version=CURRENT_VERSION,
    repo=GITHUB_REPO,
    auto_update=True,
    auto_restart=True
)
```

---

# 1. Project Structure

```
updater/
│
├── __init__.py
├── config.py
├── updater.py
├── github_api.py
├── downloader.py
├── installer.py
├── tray_ui.py
├── update_window.py
├── utils.py
└── assets/
    └── update_icon.png
```

The module must be **fully self-contained**.

---

# 2. Configuration (Developer Customization)

File: `config.py`

```python
CURRENT_VERSION = "v0.0.1"
GITHUB_REPO = "username/repo"

AUTO_UPDATE = True
AUTO_RESTART = True

CHECK_INTERVAL_HOURS = 6

DOWNLOAD_FOLDER = "updates"

ALLOW_PRERELEASE = False
```

The developer should only modify these variables.

---

# 3. GitHub Release Detection

File: `github_api.py`

Use GitHub API:

```
https://api.github.com/repos/{repo}/releases/latest
```

Return data:

```
tag_name
assets
browser_download_url
published_at
```

### Functions

```
get_latest_release(repo)
get_release_assets(repo)
compare_versions(current, latest)
```

### Version Comparison

Example:

```
current = v1.0.0
latest = v1.1.0
```

Must detect:

```
major updates
minor updates
patch updates
```

Use semantic version comparison.

---

# 4. Update Workflow

### Startup

When application starts:

```
if AUTO_UPDATE:
    check_for_updates()
```

---

### Update Flow

```
App Start
   ↓
Check GitHub release
   ↓
Is new version available?
   ↓
No → wait next interval
Yes → show notification
   ↓
User clicks download
   ↓
Download update
   ↓
Show progress window
   ↓
Download finished
   ↓
Show "Restart to update"
   ↓
Restart application
   ↓
Install update
```

---

# 5. Download System

File: `downloader.py`

Use:

```
requests
threading
```

The downloader must display:

```
download percentage
download speed
estimated remaining time
downloaded size
total size
```

Example UI:

```
Downloading Update

Progress: 65%

Speed: 2.1 MB/s
Downloaded: 32MB / 50MB
Remaining Time: 8 seconds
```

---

### Speed Calculation

```
speed = downloaded_bytes / elapsed_time
```

ETA:

```
eta = remaining_bytes / speed
```

Update every:

```
500 ms
```

---

# 6. PyQt6 Progress Window

File: `update_window.py`

Design a **modern minimal UI**

Components:

```
QProgressBar
QLabel (percentage)
QLabel (speed)
QLabel (time remaining)
QPushButton (cancel)
```

Example layout:

```
--------------------------------
 Update Available

 Version v1.2.0 is available

 [ Download Update ]

--------------------------------
 Downloading...

 [█████████-----] 65%

 Speed: 2.3 MB/s
 Remaining: 7 seconds

 Cancel
--------------------------------
```

---

# 7. System Tray Integration

File: `tray_ui.py`

Use:

```
QSystemTrayIcon
QMenu
```

Tray menu items:

```
Check for Updates
Download Update
Restart to Update
Open Release Page
Exit
```

Notification examples:

```
Update Available
Version v1.2.0 is ready to download
```

```
Update Downloaded
Restart application to install update
```

---

# 8. Background Update Checker

Use:

```
QTimer
```

Check every:

```
CHECK_INTERVAL_HOURS
```

Converted to milliseconds.

---

# 9. Installer System

File: `installer.py`

After download completes:

### Strategy

Download:

```
update.zip
```

Then:

```
extract to temp folder
replace old files
restart application
```

Steps:

```
close running instance
replace files
launch new version
```

Use:

```
subprocess
shutil
zipfile
```

---

# 10. Safe Update Mechanism

Must prevent:

```
partial updates
file corruption
update crash
```

Use:

```
temp update folder
```

Process:

```
download → verify → extract → replace
```

---

# 11. Restart Mechanism

If:

```
AUTO_RESTART = True
```

Then automatically restart after download.

Otherwise:

Show notification:

```
Restart to update
```

Restart command:

```
subprocess.Popen(sys.executable)
sys.exit()
```

---

# 12. Error Handling

Must handle:

### Network errors

```
GitHub unreachable
timeout
connection reset
```

### Download errors

```
interrupted download
invalid file
```

### Version parsing errors

Log error but don't crash application.

---

# 13. Logging System

Create file:

```
update.log
```

Log:

```
update checks
download status
errors
install results
```

---

# 14. Optional Features (Highly Recommended)

The module should optionally support:

### Silent update

```
AUTO_DOWNLOAD = True
```

Automatically download update.

---

### Delta updates (advanced)

Only download changed files.

---

### SHA256 verification

GitHub release may contain:

```
checksum.txt
```

Verify file integrity.

---

### Update channel

Support:

```
stable
beta
nightly
```

---

# 15. API for Developers

Expose simple functions:

```
initialize()
check_for_updates()
download_update()
restart_to_update()
```

Example:

```python
UpdateManager.initialize(
    current_version="v0.0.1",
    repo="username/repo",
    auto_update=True
)
```

---

# 16. Threading Requirements

Network and download operations must **NOT block GUI**.

Use:

```
QThread
```

or

```
threading.Thread
```

---

# 17. Example Integration

Example application:

```python
import sys
from PyQt6.QtWidgets import QApplication
from updater import UpdateManager

app = QApplication(sys.argv)

UpdateManager.initialize(
    current_version="v0.0.1",
    repo="bibekchandsah/brightness",
    auto_update=True,
    auto_restart=True
)

sys.exit(app.exec())
```

---

# 18. Performance Requirements

The updater must:

* Use **minimal CPU**
* Use **minimal RAM**
* Run **silently in background**
* Never freeze UI

---

# 19. Security Requirements

Must prevent:

```
malicious update download
```

Implement:

```
GitHub source validation
optional SHA verification
```

---

# 20. Final Result

The module must allow developers to simply do:

```
pip install updater-module
```

or copy folder:

```
/updater
```

Then enable updates with **3 lines of code**.

---

# End Goal

A **plug-and-play Python updater module** similar to:

```
electron-updater
squirrel
sparkle updater (macOS)
```

But designed for **Python + PyQt6 applications**.

