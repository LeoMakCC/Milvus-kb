from knowledgeqa.folder_dialog import split_multiselect


def test_split_multiselect_single_path() -> None:
    assert split_multiselect("D:\\docs\\a.md") == ["D:\\docs\\a.md"]


def test_split_multiselect_multiple_paths() -> None:
    raw = "D:\\docs\x00a.md\x00b.pdf\x00\x00"

    assert split_multiselect(raw) == [
        "D:\\docs\\a.md",
        "D:\\docs\\b.pdf",
    ]


def test_split_multiselect_empty_result() -> None:
    assert split_multiselect("") == []
