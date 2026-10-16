from __future__ import annotations

import threading
from collections.abc import Callable


def build_menu_items(
    on_show: Callable[[], None],
    on_quit: Callable[[], None],
) -> list[tuple[str, Callable[[], None]]]:
    return [
        ("显示主窗口", on_show),
        ("退出", on_quit),
    ]


def _default_icon_factory(items):
    import pystray
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (64, 64), (37, 99, 235))
    draw = ImageDraw.Draw(image)
    draw.rectangle((14, 14, 50, 50), outline=(255, 255, 255), width=3)
    menu = pystray.Menu(
        *[
            pystray.MenuItem(label, callback, default=index == 0)
            for index, (label, callback) in enumerate(items)
        ]
    )
    return pystray.Icon("KnowledgeQA", image, "KnowledgeQA", menu)


class TrayController:
    def __init__(
        self,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        icon_factory=None,
    ) -> None:
        self._items = build_menu_items(on_show, on_quit)
        self._icon_factory = icon_factory or _default_icon_factory
        self._icon = None
        self._thread = None

    def start(self) -> None:
        self._icon = self._icon_factory(self._items)
        self._thread = threading.Thread(
            target=self._icon.run,
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
