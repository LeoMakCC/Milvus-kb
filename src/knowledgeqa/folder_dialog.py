from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

BIF_RETURNONLYFSDIRS = 0x0001
BIF_EDITBOX = 0x0010
BIF_NEWDIALOGSTYLE = 0x0040

OFN_ALLOWMULTISELECT = 0x00000200
OFN_EXPLORER = 0x00080000
OFN_FILEMUSTEXIST = 0x00001000
OFN_PATHMUSTEXIST = 0x00000800
OFN_HIDEREADONLY = 0x00000004
OFN_NOCHANGEDIR = 0x00000008

DEFAULT_DOCUMENT_FILTER = (
    "支持的文档|*.md;*.markdown;*.txt;*.html;*.htm;*.csv;*.pdf;*.docx;*.xlsx;*.pptx"
    "|Markdown|*.md;*.markdown"
    "|PDF|*.pdf"
    "|Word|*.docx"
    "|Excel|*.xlsx"
    "|CSV|*.csv"
    "|PowerPoint|*.pptx"
    "|文本|*.txt;*.html;*.htm"
    "|所有文件|*.*"
)


class _BrowseInfoW(ctypes.Structure):
    _fields_ = [
        ("hwndOwner", wintypes.HWND),
        ("pidlRoot", ctypes.c_void_p),
        ("pszDisplayName", wintypes.LPWSTR),
        ("lpszTitle", wintypes.LPCWSTR),
        ("ulFlags", wintypes.UINT),
        ("lpfn", ctypes.c_void_p),
        ("lParam", wintypes.LPARAM),
        ("iImage", ctypes.c_int),
    ]


class _OpenFileNameW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", ctypes.c_void_p),
        ("dwReserved", wintypes.DWORD),
        ("FlagsEx", wintypes.DWORD),
    ]


def _filter_text(file_filter: str) -> str:
    """把 "说明|*.md" 形式转换为 Win32 需要的 \0 分隔格式。"""
    parts = file_filter.split("|")
    chunks = []
    for index in range(0, len(parts) - 1, 2):
        chunks.append(parts[index])
        chunks.append(parts[index + 1])
    return "\0".join(chunks) + "\0\0"


def split_multiselect(raw: str) -> list[str]:
    """解析 GetOpenFileNameW 的多选结果。

    单选时返回 ``"D:\\dir\\a.md"``；多选时返回
    ``"D:\\dir\\0a.md\\0b.md\\0\\0"``，首段是目录，其余是文件名。
    """
    parts = [part for part in raw.split("\x00") if part]
    if not parts:
        return []
    if len(parts) == 1:
        return [parts[0]]
    directory = parts[0]
    return [os.path.join(directory, name) for name in parts[1:]]


def select_files(
    title: str = "选择文档",
    initial: str = "",
    file_filter: str = DEFAULT_DOCUMENT_FILTER,
) -> list[str]:
    """弹出文件选择框（支持多选），返回绝对路径列表；取消时返回空列表。"""
    if sys.platform != "win32":
        return []

    comdlg32 = ctypes.WinDLL("comdlg32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)

    comdlg32.GetOpenFileNameW.restype = wintypes.BOOL
    comdlg32.GetOpenFileNameW.argtypes = [ctypes.POINTER(_OpenFileNameW)]

    buffer_size = 65536
    buffer = ctypes.create_unicode_buffer(buffer_size)

    ole32.CoInitialize(None)
    try:
        info = _OpenFileNameW()
        info.lStructSize = ctypes.sizeof(_OpenFileNameW)
        info.hwndOwner = None
        info.hInstance = None
        info.lpstrFilter = _filter_text(file_filter)
        info.lpstrCustomFilter = None
        info.nMaxCustFilter = 0
        info.nFilterIndex = 1
        info.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
        info.nMaxFile = buffer_size
        info.lpstrFileTitle = None
        info.nMaxFileTitle = 0
        info.lpstrInitialDir = initial or None
        info.lpstrTitle = title
        info.Flags = (
            OFN_ALLOWMULTISELECT
            | OFN_EXPLORER
            | OFN_FILEMUSTEXIST
            | OFN_PATHMUSTEXIST
            | OFN_HIDEREADONLY
            | OFN_NOCHANGEDIR
        )
        info.nFileOffset = 0
        info.nFileExtension = 0
        info.lpstrDefExt = None
        info.lCustData = 0
        info.lpfnHook = None
        info.lpTemplateName = None
        info.pvReserved = None
        info.dwReserved = 0
        info.FlagsEx = 0

        if not comdlg32.GetOpenFileNameW(ctypes.byref(info)):
            return []

        raw = ctypes.string_at(
            ctypes.addressof(buffer),
            buffer_size * ctypes.sizeof(ctypes.c_wchar),
        ).decode("utf-16-le", errors="ignore")
        return split_multiselect(raw)
    except OSError:
        return []
    finally:
        ole32.CoUninitialize()



def select_folder(title: str = "选择文档目录", initial: str = "") -> str:
    """弹出系统文件夹选择框，返回绝对路径；用户取消时返回空字符串。

    直接调用 Shell API，而不是 GUI 框架自带对话框：pywebview 的 js_api
    回调运行在独立线程，WinForms 对话框在非 GUI 线程中会抛跨线程异常。
    """
    if sys.platform != "win32":
        return ""

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)

    shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
    shell32.SHBrowseForFolderW.argtypes = [ctypes.POINTER(_BrowseInfoW)]
    shell32.SHGetPathFromIDListW.restype = wintypes.BOOL
    shell32.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]
    shell32.SHParseDisplayName.restype = ctypes.c_long
    shell32.SHParseDisplayName.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]

    ole32.CoInitialize(None)
    root_pidl = ctypes.c_void_p()
    try:
        if initial:
            parsed = ctypes.c_void_p()
            attributes = wintypes.DWORD()
            if (
                shell32.SHParseDisplayName(
                    initial,
                    None,
                    ctypes.byref(parsed),
                    0,
                    ctypes.byref(attributes),
                )
                == 0
            ):
                root_pidl = parsed

        display = ctypes.create_unicode_buffer(260)
        info = _BrowseInfoW()
        info.hwndOwner = None
        info.pidlRoot = root_pidl
        info.pszDisplayName = ctypes.cast(display, wintypes.LPWSTR)
        info.lpszTitle = title
        info.ulFlags = BIF_RETURNONLYFSDIRS | BIF_EDITBOX | BIF_NEWDIALOGSTYLE
        info.lpfn = None
        info.lParam = 0
        info.iImage = 0

        pidl = shell32.SHBrowseForFolderW(ctypes.byref(info))
        if not pidl:
            return ""
        try:
            path = ctypes.create_unicode_buffer(1024)
            if not shell32.SHGetPathFromIDListW(pidl, path):
                return ""
            return path.value
        finally:
            ole32.CoTaskMemFree(ctypes.c_void_p(pidl))
    except OSError:
        return ""
    finally:
        if root_pidl:
            ole32.CoTaskMemFree(root_pidl)
        ole32.CoUninitialize()
