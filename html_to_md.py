import os
import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify as md


HTML_ROOT = Path("html")


ENCODING_CANDIDATES = [
    "utf-8",
    "gbk",
    "gb2312",
    "gb18030",
]


def detect_and_read(path: Path) -> str:
    """
    尝试使用多种常见编码读取文件，避免中文乱码。
    读取失败会抛出异常。
    """
    last_error: Exception | None = None
    for enc in ENCODING_CANDIDATES:
        try:
            with path.open("r", encoding=enc, errors="strict") as f:
                return f.read()
        except UnicodeDecodeError as e:
            last_error = e
            continue

    # 最后尝试二进制 + 忽略错误，避免完全失败（极少数情况）
    try:
        data = path.read_bytes()
        return data.decode("utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"无法正确解码文件: {path}") from (last_error or e)


def clean_soup(soup: BeautifulSoup) -> BeautifulSoup:
    """
    删除脚本、样式等无关内容。
    """
    for tag in soup(["script", "style", "noscript", "meta", "link"]):
        tag.decompose()
    return soup


def postprocess_markdown(text: str) -> str:
    """
    对 Markdown 文本做一些清洗，减少乱码和奇怪字符。
    """
    # 替换常见的 &nbsp;
    text = text.replace("\xa0", " ")

    # 删除不可见控制字符（保留常见换行和制表符）
    def _filter_char(ch: str) -> bool:
        code = ord(ch)
        if ch in ("\n", "\r", "\t"):
            return True
        # 可打印 ASCII 或常见的 Unicode 字符
        return code >= 32

    text = "".join(ch for ch in text if _filter_char(ch))

    # 将内部链接中的 .html 后缀改为 .md
    text = text.replace(".html)", ".md)")
    text = text.replace(".html#", ".md#")

    # 合并多余的空行（最多保留两个）
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip() + "\n"


def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    soup = clean_soup(soup)

    body = soup.body or soup
    # 只指定 strip，避免同时指定 strip 和 convert 触发异常
    markdown = md(
        str(body),
        heading_style="ATX",
        strip=["span"],
    )
    return postprocess_markdown(markdown)


def process_file(src_path: Path) -> None:
    rel = src_path.relative_to(HTML_ROOT)
    dst_path = HTML_ROOT / rel.with_suffix(".md")

    # 确保输出目录存在
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"转换: {rel}")
    html_text = detect_and_read(src_path)
    md_text = html_to_markdown(html_text)
    dst_path.write_text(md_text, encoding="utf-8")


def main() -> int:
    if not HTML_ROOT.exists():
        print(f"未找到目录: {HTML_ROOT}", file=sys.stderr)
        return 1

    html_files: list[Path] = []
    for root, _dirs, files in os.walk(HTML_ROOT):
        for name in files:
            if name.lower().endswith(".html"):
                html_files.append(Path(root) / name)

    if not html_files:
        print("未在 html 目录下找到任何 .html 文件。")
        return 0

    for path in sorted(html_files):
        try:
            process_file(path)
        except Exception as e:  # noqa: BLE001
            print(f"处理失败: {path}: {e}", file=sys.stderr)

    print("全部处理完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


