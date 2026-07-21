import threading
import time
import io
from mss import mss
from PIL import Image


class ScreenCapture:
    def __init__(self, service):
        self.service = service
        self._capturing = False
        self._thread = None

    def start(self):
        if self._capturing:
            return
        self._capturing = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._capturing = False

    def _loop(self):
        with mss() as sct:
            monitor = sct.monitors[0]
            while self._capturing:
                try:
                    img = sct.grab(monitor)
                    pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=40)
                    self.service.send_message_sync(0x02, buf.getvalue())
                except Exception as e:
                    print("Capture error:", e)
                time.sleep(0.333)
