import asyncio
import sys
import os
import ctypes
import traceback


def _get_exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _silent_hook(exc_type, exc_value, exc_traceback):
    try:
        log_path = os.path.join(_get_exe_dir(), "agent_error.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("--- Unhandled Exception ---\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
            f.write("\n")
    except:
        pass


sys.excepthook = _silent_hook

if sys.platform == "win32":
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass
    if getattr(sys, "frozen", False):
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except:
            pass

from agent_service import AgentService


async def main():
    service = AgentService()
    await service.start()


if __name__ == "__main__":
    asyncio.run(main())
