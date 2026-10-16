from knowledgeqa.tray import TrayController, build_menu_items


class FakeIcon:
    def __init__(self, items) -> None:
        self.items = items
        self.started = False
        self.stopped = False

    def run(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_tray_menu_contains_show_and_quit_callbacks() -> None:
    calls = []
    items = build_menu_items(
        on_show=lambda: calls.append("show"),
        on_quit=lambda: calls.append("quit"),
    )

    assert [label for label, _ in items] == ["显示主窗口", "退出"]
    items[0][1]()
    items[1][1]()
    assert calls == ["show", "quit"]


def test_tray_controller_starts_and_stops_icon() -> None:
    created = []

    def factory(items):
        icon = FakeIcon(items)
        created.append(icon)
        return icon

    tray = TrayController(
        on_show=lambda: None,
        on_quit=lambda: None,
        icon_factory=factory,
    )
    tray.start()
    tray.stop()

    assert created[0].stopped is True
