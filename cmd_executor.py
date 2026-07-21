import subprocess
import threading
import json


class CmdExecutor:
    def __init__(self, service):
        self.service = service
        self.sessions = {}

    def open_session(self, session_id, mode):
        if session_id in self.sessions:
            return
        flags = 0
        if mode == "silent":
            flags = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.Popen(
                "cmd.exe",
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=flags
            )
            self.sessions[session_id] = proc

            def reader(pipe, is_err):
                try:
                    for line in iter(pipe.readline, ""):
                        self._send_output(session_id, line)
                except:
                    pass

            threading.Thread(target=reader, args=(proc.stdout, False), daemon=True).start()
            threading.Thread(target=reader, args=(proc.stderr, True), daemon=True).start()

            def on_exit():
                proc.wait()
                self.close_session(session_id)

            threading.Thread(target=on_exit, daemon=True).start()
        except Exception as e:
            self._send_output(session_id, f"Error: {e}\n")

    def send_input(self, session_id, text):
        proc = self.sessions.get(session_id)
        if proc and proc.stdin:
            try:
                proc.stdin.write(text)
                proc.stdin.flush()
            except:
                pass

    def close_session(self, session_id):
        proc = self.sessions.pop(session_id, None)
        if proc:
            try:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
            except:
                pass

    def _send_output(self, session_id, output):
        if not output:
            return
        payload = json.dumps({"sessionId": session_id, "output": output}).encode("utf-8")
        self.service.send_message_sync(0x09, payload)
