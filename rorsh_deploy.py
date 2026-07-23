import os
import sys
import json
import time
import shutil
import socket
import ctypes
import subprocess
import tempfile
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

# ─── Configuration ───────────────────────────────────────────────────────────

SERVER_URL = "https://x7kq9mp2vl4nr8st3wf6yh1jb5cz0au-1.onrender.com"
INSTALL_DIR_NAME = "RORSH"
APP_NAME = "RORSH-ADMIN"

# ─── SSL Context (Bypass verification for cloud VMs without root certs) ─────

# Create an SSL context that doesn't verify certificates
# This is needed on fresh/cloud Windows VMs that lack updated root CA stores
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ─── Logging ─────────────────────────────────────────────────────────────────

class Logger:
    def __init__(self):
        self.log_file = self._get_log_path()
        self._ensure_dir()
        self.log("=== RORSH Deployment Started ===")
        self.log(f"Log file: {self.log_file}")

    def _get_log_path(self):
        # Try D: drive first
        d_path = Path("D:/RORSH-Room/Installer")
        try:
            d_path.mkdir(parents=True, exist_ok=True)
            test_file = d_path / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return d_path / f"{timestamp}.txt"
        except (OSError, PermissionError):
            pass

        # Fallback to temp directory
        temp_dir = Path(tempfile.gettempdir()) / "RORSH-Room" / "Installer"
        temp_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return temp_dir / f"{timestamp}.txt"

    def _ensure_dir(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass

logger = Logger()

# ─── Helpers ─────────────────────────────────────────────────────────────────

def show_error(message):
    """Show error popup and log it."""
    logger.log(f"ERROR: {message}")
    ctypes.windll.user32.MessageBoxW(0, message, "RORSH Deployment Error", 0x10)

def show_success(message):
    """Show success popup and log it."""
    logger.log(f"SUCCESS: {message}")
    ctypes.windll.user32.MessageBoxW(0, message, "RORSH Deployment Success", 0x40)

def get_machine_guid():
    """Read Windows Machine GUID from registry."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return value
    except Exception as e:
        logger.log(f"WARNING: Could not read MachineGuid: {e}")
        return f"UNKNOWN-{socket.gethostname()}"

def get_hostname():
    return socket.gethostname()

def http_post_json(url, data):
    """POST JSON data and return parsed response."""
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    # Use custom SSL context to bypass cert verification
    with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
        return json.loads(response.read().decode('utf-8'))

def http_download(url, dest_path):
    """Download file from URL to destination path."""
    req = urllib.request.Request(url, headers={'User-Agent': 'RORSH-Installer/1.0'})
    # Use custom SSL context to bypass cert verification
    with urllib.request.urlopen(req, timeout=60, context=ssl_context) as response:
        with open(dest_path, 'wb') as f:
            f.write(response.read())

def kill_processes_in_directory(directory):
    """Kill all processes whose executable is inside the given directory."""
    norm_dir = str(Path(directory).resolve()).lower()
    logger.log(f"Scanning processes in: {norm_dir}")

    try:
        result = subprocess.run(
            ['wmic', 'process', 'get', 'ProcessId,ExecutablePath', '/format:csv'],
            capture_output=True, text=True, timeout=30
        )
        lines = result.stdout.strip().split('\n')
        killed = 0

        for line in lines:
            parts = line.strip().split(',')
            if len(parts) >= 3:
                exe_path = parts[-2].strip().strip('"')
                pid_str = parts[-1].strip().strip('"')
                if exe_path and pid_str.isdigit():
                    try:
                        if exe_path.lower().startswith(norm_dir):
                            pid = int(pid_str)
                            logger.log(f"Killing process: {exe_path} (PID {pid})")
                            subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                                         capture_output=True, timeout=10)
                            killed += 1
                    except Exception as e:
                        logger.log(f"Warning: Could not kill PID {pid_str}: {e}")

        logger.log(f"Killed {killed} process(es)")
        time.sleep(2)
    except Exception as e:
        logger.log(f"Warning: Process scan failed: {e}")

def set_autostart(name, exe_path):
    """Add executable to HKCU Run registry for auto-start."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, f'"{exe_path}"')
            logger.log(f"Registry autostart set: {name} -> {exe_path}")
    except Exception as e:
        logger.log(f"ERROR: Failed to set autostart for {name}: {e}")
        raise

def launch_silent(exe_path):
    """Launch executable without showing a window."""
    logger.log(f"Launching: {exe_path}")
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    subprocess.Popen(
        [exe_path],
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

# ─── Main Deployment Logic ───────────────────────────────────────────────────

def main():
    try:
        # Determine install directory
        app_data = os.environ.get('APPDATA', tempfile.gettempdir())
        install_dir = Path(app_data) / INSTALL_DIR_NAME
        logger.log(f"Install directory: {install_dir}")

        # Step 1: Check for existing installation
        logger.log("Step 1: Checking for existing RORSH installation...")
        if install_dir.exists():
            logger.log("Existing installation found — entering Reinstall flow.")
            kill_processes_in_directory(install_dir)

            retries = 5
            while retries > 0:
                try:
                    shutil.rmtree(install_dir)
                    logger.log("Existing directory removed successfully.")
                    break
                except PermissionError:
                    retries -= 1
                    if retries == 0:
                        raise
                    logger.log(f"Directory locked, retrying... ({retries} left)")
                    time.sleep(2)
        else:
            logger.log("No existing installation found — fresh install.")

        # Step 2: Read machine identity
        logger.log("Step 2: Reading machine identity...")
        machine_guid = get_machine_guid()
        hostname = get_hostname()
        logger.log(f"Machine GUID: {machine_guid}")
        logger.log(f"Hostname: {hostname}")

        # Step 3: Register with server
        logger.log("Step 3: Registering with server...")
        register_url = urljoin(SERVER_URL, "/register")
        logger.log(f"POST {register_url}")

        response = http_post_json(register_url, {
            "guid": machine_guid,
            "hostname": hostname
        })

        logger.log(f"Server response: {json.dumps(response)}")
        process = int(response.get("process", 0))
        client_id = response.get("clientId", "unknown")
        logger.log(f"Process: {process}, Client ID: {client_id}")

        # Step 4: Create install directory
        install_dir.mkdir(parents=True, exist_ok=True)
        logger.log(f"Created install directory: {install_dir}")

        # Step 5: Download files
        logger.log("Step 5: Downloading installation files...")

        # 5a. version.json
        version_path = install_dir / "version.json"
        http_download(urljoin(SERVER_URL, "/setup/files/version"), version_path)
        logger.log(f"Downloaded version.json -> {version_path}")

        with open(version_path, 'r', encoding='utf-8') as f:
            version_info = json.load(f)
        exe_name = version_info.get("Name", "RORSH-ADMIN.exe")
        logger.log(f"Executable name from version.json: {exe_name}")

        # 5b. Main executable
        exe_path = install_dir / exe_name
        http_download(urljoin(SERVER_URL, "/setup/files/exe"), exe_path)
        logger.log(f"Downloaded {exe_name} -> {exe_path}")

        # 5c. Updater
        updater_path = install_dir / "Updater-2.exe"
        http_download(urljoin(SERVER_URL, "/setup/files/updater"), updater_path)
        logger.log(f"Downloaded Updater-2.exe -> {updater_path}")

        # Step 6: Write myinfo.json
        logger.log("Step 6: Writing client identity file...")
        myinfo = {
            "windows_machine_guid": machine_guid,
            "application_uuid": client_id,
            "created_at": datetime.now().strftime("%d%m%Y %H:%M:%S")
        }
        myinfo_path = install_dir / "myinfo.json"
        with open(myinfo_path, 'w', encoding='utf-8') as f:
            json.dump(myinfo, f, indent=2, ensure_ascii=False)
        logger.log(f"Written myinfo.json -> {myinfo_path}")

        # Step 7: Set autostart
        logger.log("Step 7: Configuring auto-start...")
        set_autostart("RORSH-ADMIN", str(exe_path))
        set_autostart("RORSH-Updater-2", str(updater_path))

        # Step 8: Launch processes
        logger.log("Step 8: Launching processes...")
        launch_silent(str(exe_path))
        launch_silent(str(updater_path))

        # Step 9: Success
        logger.log(f"=== Deployment completed successfully (Process {process}) ===")
        show_success(
            f"RORSH Deployment Complete!\n\n"
            f"Process: {process}\n"
            f"Client ID: {client_id}\n"
            f"Install Path: {install_dir}\n\n"
            f"RORSH ADMIN and Updater are now running in the background."
        )

    except urllib.error.URLError as e:
        show_error(f"RORSH Deploy Server Are running\n\nConnection failed: {e.reason}")
    except urllib.error.HTTPError as e:
        show_error(f"RORSH Deploy Server Are running\n\nServer returned HTTP {e.code}: {e.reason}")
    except json.JSONDecodeError as e:
        show_error(f"RORSH Deploy Server Are running\n\nInvalid server response: {e}")
    except PermissionError as e:
        show_error(f"Permission denied. Run as administrator?\n\n{e}")
    except Exception as e:
        show_error(f"Deployment failed:\n\n{type(e).__name__}: {e}")

# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass
    main()
