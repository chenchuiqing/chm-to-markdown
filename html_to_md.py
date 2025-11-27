import argparse
import os
import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify as md


DEFAULT_HTML_ROOT = Path("html")


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


def process_file(src_path: Path, html_root: Path, md_root: Path) -> None:
    rel = src_path.relative_to(html_root)
    dst_path = md_root / rel.with_suffix(".md")

    # 确保输出目录存在
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"转换: {rel}")
    html_text = detect_and_read(src_path)
    md_text = html_to_markdown(html_text)
    dst_path.write_text(md_text, encoding="utf-8")


def collect_html_files(root: Path, subdir: Path | None = None) -> list[Path]:
    """
    收集需要转换的 HTML 文件列表。

    - root: HTML 根目录（例如 chm_to_html 的输出目录）
    - subdir: 可选子目录（相对 root 的相对路径），仅转换该子目录下的文件
    """
    base = root
    if subdir is not None:
        base = (root / subdir).resolve()

    if not base.exists():
        print(f"未找到目录: {base}", file=sys.stderr)
        return []

    html_files: list[Path] = []
    for r, _dirs, files in os.walk(base):
        for name in files:
            if name.lower().endswith(".html"):
                html_files.append(Path(r) / name)

    return html_files


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "将 CHM 解包后的 HTML 批量转换为 Markdown。\n"
            "示例：uv run python html_to_md.py --root html\n"
            "      uv run python html_to_md.py --root out_html --subdir 结构体\n"
            "      uv run python html_to_md.py --root out_html --out-root out_md"
        )
    )
    parser.add_argument(
        "--root",
        type=str,
        default=str(DEFAULT_HTML_ROOT),
        help="HTML 根目录（默认为 html，与 chm_to_html.py 输出目录一致）",
    )
    parser.add_argument(
        "--subdir",
        type=str,
        default=None,
        help="只转换指定子目录（相对 root 的路径，例如: 结构体 或 00新手指南）",
    )
    parser.add_argument(
        "--out-root",
        type=str,
        default=None,
        help="Markdown 输出根目录（默认与 HTML 根目录相同，例如: md 或 out_md）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    html_root = Path(args.root).resolve()
    md_root = Path(args.out_root).resolve() if getattr(args, "out_root", None) else html_root
    subdir = Path(args.subdir) if args.subdir else None

    if not html_root.exists():
        print(f"未找到 HTML 根目录: {html_root}", file=sys.stderr)
        return 1

    html_files = collect_html_files(html_root, subdir)

    if not html_files:
        if subdir is not None:
            print(f"未在 {html_root / subdir} 下找到任何 .html 文件。")
        else:
            print(f"未在 {html_root} 下找到任何 .html 文件。")
        return 0

    for path in sorted(html_files):
        try:
            process_file(path, html_root, md_root)
        except Exception as e:  # noqa: BLE001
            print(f"处理失败: {path}: {e}", file=sys.stderr)

    print("全部处理完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


