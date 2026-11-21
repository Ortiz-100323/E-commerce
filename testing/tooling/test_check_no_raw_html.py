from pathlib import Path
from types import ModuleType

import pytest


@pytest.mark.parametrize(
    "source",
    [
        "<div dangerouslySetInnerHTML={{ __html: text }} />",
        "element.innerHTML = text",
        "element.outerHTML = text",
        "element.insertAdjacentHTML('beforeend', text)",
        "document.write(text)",
        "document.writeln(text)",
        "range.createContextualFragment(text)",
    ],
)
def test_every_way_of_injecting_raw_html_is_found(no_raw_html: ModuleType, source: str) -> None:
    findings = no_raw_html.find_raw_html(f"const a = 1\n{source}\n")
    assert [finding.line for finding in findings] == [2]


@pytest.mark.parametrize(
    "source",
    [
        "<p>{text}</p>",
        "element.textContent = text",
        "const innerHTMLish = 1",
        "const label = 'Write a review'",
    ],
)
def test_safe_code_is_not_reported(no_raw_html: ModuleType, source: str) -> None:
    assert no_raw_html.find_raw_html(source) == []


def test_scan_checks_ts_and_tsx_files_and_skips_vendor_directories(
    no_raw_html: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "Safe.tsx").write_text("export const A = () => <p>{x}</p>\n", encoding="utf-8")
    (tmp_path / "Unsafe.tsx").write_text("<div dangerouslySetInnerHTML={x} />\n", encoding="utf-8")
    (tmp_path / "dom.ts").write_text("node.innerHTML = x\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("innerHTML is banned\n", encoding="utf-8")
    vendor = tmp_path / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "index.ts").write_text("node.innerHTML = x\n", encoding="utf-8")

    findings = no_raw_html.scan([tmp_path])

    assert sorted(finding.path.name for finding in findings) == ["Unsafe.tsx", "dom.ts"]


def test_main_exit_code_reflects_findings(no_raw_html: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "Safe.tsx").write_text("export const A = 1\n", encoding="utf-8")
    assert no_raw_html.main([str(tmp_path)]) == 0
    (tmp_path / "Unsafe.tsx").write_text("node.outerHTML = x\n", encoding="utf-8")
    assert no_raw_html.main([str(tmp_path)]) == 1
