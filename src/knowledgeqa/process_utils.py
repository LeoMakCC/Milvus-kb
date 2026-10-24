from __future__ import annotations

import subprocess
import sys

_CREATE_NO_WINDOW = 0x08000000


def hidden_window_kwargs() -> dict[str, object]:
    """让子进程不弹出控制台窗口。

    Windows 下便携版是无控制台的 GUI 进程，直接调用 ``docker`` 等控制台程序时，
    系统会为每个子进程新建一个控制台窗口，表现为窗口一闪而过。
    """
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", _CREATE_NO_WINDOW),
        "startupinfo": startupinfo,
    }
