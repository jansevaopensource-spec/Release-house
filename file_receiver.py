import os
import json
import threading
import ctypes

from file_manager import FileManager


class FileReceiver:
    def __init__(self, service):
        self.service = service
        self.active_transfers = {}
        self.silent_transfers = {}
        self.lock = threading.Lock()
        self.silent_lock = threading.Lock()
        self.target_dir = r"D:\\Client-room"

    def handle_send_file_start(self, transfer_id, filename, size):
        def _ask():
            try:
                msg = f"Admin wants to send: {filename}\nSize: {size} bytes\n\nAccept this file?"
                result = ctypes.windll.user32.MessageBoxW(
                    0, msg, "Incoming File",
                    0x04 | 0x20 | 0x200 | 0x1000
                )
                accepted = (result == 6)
                if accepted:
                    os.makedirs(self.target_dir, exist_ok=True)
                    path = os.path.join(self.target_dir, filename)
                    with self.lock:
                        self.active_transfers[transfer_id] = open(path, "wb")
                payload = json.dumps({
                    "transferId": transfer_id,
                    "accepted": accepted
                }).encode("utf-8")
                self.service.send_message_sync(0x10, payload)
            except Exception as e:
                print("File start error:", e)
        threading.Thread(target=_ask, daemon=True).start()

    def handle_file_chunk(self, transfer_id, chunk):
        with self.lock:
            f = self.active_transfers.get(transfer_id)
            if f:
                try:
                    f.write(chunk)
                except:
                    pass

    def handle_file_complete(self, transfer_id):
        with self.lock:
            f = self.active_transfers.pop(transfer_id, None)
            if f:
                try:
                    f.close()
                except:
                    pass
                ctypes.windll.user32.MessageBoxW(
                    0, "File transfer complete. Saved to D:\\Client-room",
                    "Transfer Complete", 0x40 | 0x1000
                )

    def handle_silent_upload_start(self, transfer_id, dest_path):
        try:
            if not FileManager.is_path_allowed(dest_path):
                print("Silent upload blocked:", dest_path)
                return
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with self.silent_lock:
                self.silent_transfers[transfer_id] = open(dest_path, "wb")
            print("Silent upload started:", dest_path)
        except Exception as e:
            print("Silent upload start error:", e)

    def handle_silent_upload_chunk(self, transfer_id, chunk):
        with self.silent_lock:
            f = self.silent_transfers.get(transfer_id)
            if f:
                try:
                    f.write(chunk)
                except Exception as e:
                    print("Silent upload write error:", e)

    def handle_silent_upload_complete(self, transfer_id):
        with self.silent_lock:
            f = self.silent_transfers.pop(transfer_id, None)
            if f:
                try:
                    f.close()
                    print("Silent upload complete.")
                except Exception as e:
                    print("Silent upload close error:", e)
