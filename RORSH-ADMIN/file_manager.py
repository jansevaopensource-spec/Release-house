import os
import json
import threading
import struct
import time
from datetime import datetime


class FileManager:
    def __init__(self, service):
        self.service = service

    @staticmethod
    def is_path_allowed(path):
        path = os.path.normpath(os.path.expandvars(path)).upper()
        if not path.startswith("C:\\"):
            return True
        user_profile = os.path.expandvars("%USERPROFILE%").upper()
        desktop = os.path.join(user_profile, "DESKTOP")
        documents = os.path.join(user_profile, "DOCUMENTS")
        downloads = os.path.join(user_profile, "DOWNLOADS")
        return (path.startswith(desktop) or
                path.startswith(documents) or
                path.startswith(downloads) or
                path == user_profile)

    def handle_file_op(self, op, src, dest):
        try:
            src_path = os.path.expandvars(src)
            if not self.is_path_allowed(src_path):
                self._send_op_result(False, "Access restricted.")
                return
            if op == "execute":
                if os.path.isfile(src_path):
                    os.startfile(src_path)
                    self._send_op_result(True, None)
                else:
                    self._send_op_result(False, "File not found.")
            else:
                self._send_op_result(False, f"Unsupported file operation: {op}")
        except Exception as e:
            self._send_op_result(False, str(e))

    def _send_op_result(self, success, error):
        payload = json.dumps({"success": success, "error": error}).encode("utf-8")
        self.service.send_message_sync(0x0E, payload)

    def list_directory(self, request_id, raw_path):
        try:
            path = os.path.expandvars(raw_path) if raw_path else "D:\\"
            if not path:
                path = "D:\\"
            if not self.is_path_allowed(path):
                self._send_error(request_id, path, "Access to this C: drive path is restricted for security.")
                return
            entries = []
            with os.scandir(path) as it:
                for entry in it:
                    st = entry.stat()
                    mod = datetime.fromtimestamp(st.st_mtime).strftime("%m/%d/%Y %I:%M %p")
                    if entry.is_dir():
                        entries.append({"name": entry.name, "isDir": True, "size": 0, "modified": mod})
                    else:
                        entries.append({"name": entry.name, "isDir": False, "size": st.st_size, "modified": mod})

            payload = json.dumps({
                "requestId": request_id,
                "path": path,
                "entries": entries
            }).encode("utf-8")
            self.service.send_message_sync(0x0C, payload)
        except Exception as e:
            self._send_error(request_id, raw_path, str(e))

    def download_file_or_folder(self, request_id, raw_path):
        def _download():
            try:
                path = os.path.expandvars(raw_path)
                if not self.is_path_allowed(path):
                    self._send_download_result(request_id, False, "Access restricted.")
                    return
                if os.path.isfile(path):
                    self._send_single_file(request_id, path, os.path.basename(path))
                    self._send_download_result(request_id, True, None)
                elif os.path.isdir(path):
                    parent = os.path.dirname(path) or (os.path.splitdrive(path)[0] + "\\")
                    for root, dirs, files in os.walk(path):
                        for f in files:
                            full = os.path.join(root, f)
                            rel = os.path.relpath(full, parent)
                            self._send_single_file(request_id, full, rel)
                    self._send_download_result(request_id, True, None)
                else:
                    self._send_download_result(request_id, False, "File or directory does not exist.")
            except Exception as e:
                self._send_download_result(request_id, False, str(e))
        threading.Thread(target=_download, daemon=True).start()

    def _send_single_file(self, request_id, file_path, relative_path):
        size = os.path.getsize(file_path)
        start_json = json.dumps({
            "requestId": request_id,
            "relativePath": relative_path,
            "fileSize": size
        }).encode("utf-8")
        self.service.send_message_sync(0x18, start_json)

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                payload = struct.pack(">I", request_id) + chunk
                self.service.send_message_sync(0x19, payload)
                time.sleep(0.005)

        end_json = json.dumps({"requestId": request_id}).encode("utf-8")
        self.service.send_message_sync(0x1A, end_json)

    def _send_download_result(self, request_id, success, error):
        payload = json.dumps({
            "requestId": request_id,
            "success": success,
            "error": error
        }).encode("utf-8")
        self.service.send_message_sync(0x1B, payload)

    def _send_error(self, request_id, path, error):
        payload = json.dumps({
            "requestId": request_id,
            "path": path,
            "error": error
        }).encode("utf-8")
        self.service.send_message_sync(0x0C, payload)
