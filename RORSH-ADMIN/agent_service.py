import asyncio
import json
import os
import sys
import socket as sock
import struct
import ctypes
import threading

from protocol import WsProtocol
from screen_capture import ScreenCapture
from input_controller import InputController
from file_manager import FileManager
from cmd_executor import CmdExecutor
from file_receiver import FileReceiver
from url_opener import UrlOpener


def show_error_popup(title, message):
    def _show():
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10 | 0x1000)
    threading.Thread(target=_show, daemon=True).start()


class AgentService:
    SERVER_URI = "wss://rorsh-net-serverbase.onrender.com/ws/agent"

    def __init__(self):
        self.loop = None
        self.protocol = None
        self.running = False
        self._failure_shown = False

        self.screen_capture = ScreenCapture(self)
        self.input_controller = InputController()
        self.file_manager = FileManager(self)
        self.cmd_executor = CmdExecutor(self)
        self.file_receiver = FileReceiver(self)
        self.url_opener = UrlOpener()

    def get_exe_dir(self):
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def get_local_ip(self):
        try:
            hostname = sock.gethostname()
            for info in sock.getaddrinfo(hostname, None, sock.AF_INET):
                return info[4][0]
        except:
            pass
        return "127.0.0.1"

    def get_client_name(self):
        path = os.path.join(self.get_exe_dir(), "name.json")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("name"):
                        return data["name"]
        except:
            pass
        name = sock.gethostname()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"name": name}, f)
        except:
            pass
        return name

    def update_client_name(self, new_name):
        path = os.path.join(self.get_exe_dir(), "name.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"name": new_name}, f)
            print("Client name updated to:", new_name)
        except Exception as e:
            print("Error updating name:", e)

    async def send_message(self, msg_type, payload=None):
        if self.protocol:
            await self.protocol.send(msg_type, payload)

    def send_message_sync(self, msg_type, payload=None):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.send_message(msg_type, payload), self.loop)

    async def start(self):
        self.running = True
        self.loop = asyncio.get_running_loop()
        while self.running:
            try:
                self.protocol = WsProtocol()
                self.protocol.on_message = self._on_message
                self.protocol.on_disconnect = self._on_disconnect
                await self.protocol.connect(self.SERVER_URI)
                self._failure_shown = False

                info = {
                    "hostname": sock.gethostname(),
                    "ipv4": self.get_local_ip(),
                    "version": "2.0.0",
                    "name": self.get_client_name()
                }
                await self.protocol.send_json(0x01, info)
                print("Connected to server.")

                while self.protocol and self.protocol.connected:
                    await asyncio.sleep(0.5)

            except Exception as e:
                if not self._failure_shown:
                    show_error_popup(
                        "RORSH Agent - Connection Failed",
                        f"Failed to connect to the server.\n\nError: {e}\n\nRetrying every 5 seconds..."
                    )
                    self._failure_shown = True
                print("Connection failed:", e)
                await asyncio.sleep(5)

    async def _on_disconnect(self):
        print("Disconnected from server.")
        self.screen_capture.stop()
        self.protocol = None

    async def _on_message(self, msg_type, payload):
        try:
            if msg_type == 0x11:
                if len(payload) > 4:
                    transfer_id = struct.unpack(">I", payload[:4])[0]
                    chunk = payload[4:]
                    self.file_receiver.handle_file_chunk(transfer_id, chunk)
                return
            if msg_type == 0x1D:
                if len(payload) > 4:
                    transfer_id = struct.unpack(">I", payload[:4])[0]
                    chunk = payload[4:]
                    self.file_receiver.handle_silent_upload_chunk(transfer_id, chunk)
                return

            text = payload.decode("utf-8") if payload else ""
            data = json.loads(text) if text else {}

            if msg_type == 0x16:
                await self.send_message(0x16, b"")
            elif msg_type == 0x03:
                self.screen_capture.start()
            elif msg_type == 0x04:
                self.screen_capture.stop()
            elif msg_type == 0x05:
                self.input_controller.handle_mouse_event(
                    int(data["x"]), int(data["y"]),
                    data["button"], data["action"],
                    int(data["screenW"]), int(data["screenH"])
                )
            elif msg_type == 0x06:
                self.input_controller.handle_key_event(
                    data["key"], False, False, False, data["action"]
                )
            elif msg_type == 0x07:
                self.cmd_executor.open_session(data["sessionId"], data["mode"])
            elif msg_type == 0x08:
                self.cmd_executor.send_input(data["sessionId"], data["input"])
            elif msg_type == 0x0A:
                self.cmd_executor.close_session(data["sessionId"])
            elif msg_type == 0x0B:
                self.file_manager.list_directory(int(data["requestId"]), data["path"])
            elif msg_type == 0x0D:
                self.file_manager.handle_file_op(data["op"], data["src"], data.get("dest"))
            elif msg_type == 0x0F:
                self.file_receiver.handle_send_file_start(
                    int(data["transferId"]), data["filename"], int(data["size"])
                )
            elif msg_type == 0x12:
                self.file_receiver.handle_file_complete(int(data["transferId"]))
            elif msg_type == 0x13:
                self.url_opener.open_url(data["url"])
            elif msg_type == 0x14:
                self.file_manager.download_file_or_folder(int(data["requestId"]), data["path"])
            elif msg_type == 0x17:
                if data.get("name"):
                    self.update_client_name(data["name"])
            elif msg_type == 0x1C:
                self.file_receiver.handle_silent_upload_start(
                    int(data["transferId"]), data["destPath"]
                )
            elif msg_type == 0x1E:
                self.file_receiver.handle_silent_upload_complete(int(data["transferId"]))
        except Exception as e:
            print("Error handling message:", e)
