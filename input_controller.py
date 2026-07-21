import ctypes

user32 = ctypes.windll.user32


class InputController:
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MIDDLEDOWN = 0x0020
    MOUSEEVENTF_MIDDLEUP = 0x0040
    KEYEVENTF_KEYUP = 0x0002

    def handle_mouse_event(self, x, y, button, action, screen_w, screen_h):
        vx = user32.GetSystemMetrics(76)
        vy = user32.GetSystemMetrics(77)
        vw = user32.GetSystemMetrics(78)
        vh = user32.GetSystemMetrics(79)

        if screen_w > 0 and screen_h > 0:
            target_x = int(x * (vw / screen_w)) + vx
            target_y = int(y * (vh / screen_h)) + vy
        else:
            target_x, target_y = x, y

        if action == "move":
            user32.SetCursorPos(target_x, target_y)
        elif action in ("down", "up"):
            user32.SetCursorPos(target_x, target_y)
            flags = 0
            if button == "left":
                flags = self.MOUSEEVENTF_LEFTDOWN if action == "down" else self.MOUSEEVENTF_LEFTUP
            elif button == "right":
                flags = self.MOUSEEVENTF_RIGHTDOWN if action == "down" else self.MOUSEEVENTF_RIGHTUP
            elif button == "middle":
                flags = self.MOUSEEVENTF_MIDDLEDOWN if action == "down" else self.MOUSEEVENTF_MIDDLEUP
            if flags:
                user32.mouse_event(flags, 0, 0, 0, 0)

    def handle_key_event(self, key, ctrl, alt, shift, action):
        vk = self._get_vk(key)
        if vk == 0:
            return
        flags = self.KEYEVENTF_KEYUP if action == "up" else 0
        user32.keybd_event(vk, 0, flags, 0)

    def _get_vk(self, key):
        if len(key) == 1:
            c = key[0]
            cl = c.lower()
            if "a" <= cl <= "z":
                return ord(c.upper())
            if "0" <= c <= "9":
                return ord(c)
            mapping = {
                ";": 0xBA, ":": 0xBA,
                "/": 0xBF, "?": 0xBF,
                "`": 0xC0, "~": 0xC0,
                "[": 0xDB, "{": 0xDB,
                "\\": 0xDC, "|": 0xDC,
                "]": 0xDD, "}": 0xDD,
                "'": 0xDE, '"': 0xDE,
                ",": 0xBC, "<": 0xBC,
                ".": 0xBE, ">": 0xBE,
                "-": 0xBD, "_": 0xBD,
                "=": 0xBB, "+": 0xBB,
                " ": 0x20,
            }
            if c in mapping:
                return mapping[c]

        named = {
            "enter": 0x0D, "shift": 0x10, "control": 0x11, "alt": 0x12,
            "meta": 0x5B, "os": 0x5B, "lwin": 0x5B, "rwin": 0x5B,
            "escape": 0x1B, "space": 0x20, "backspace": 0x08, "tab": 0x09,
            "capslock": 0x14, "numlock": 0x90, "scrolllock": 0x91,
            "arrowleft": 0x25, "arrowup": 0x26, "arrowright": 0x27, "arrowdown": 0x28,
            "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
            "pageup": 0x21, "pagedown": 0x22,
        }
        for i in range(1, 13):
            named[f"f{i}"] = 0x70 + i - 1
        return named.get(key.lower(), 0)
