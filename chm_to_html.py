import argparse
import os
import subprocess
import sys
from pathlib import Path


def find_hh_exe() -> str | None:
    """
    尝试在环境变量 PATH 和系统目录中查找 hh.exe。
    """
    # 1. 直接假设在 PATH 中
    for name in ("hh.exe", "HH.EXE"):
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            candidate = Path(path_dir) / name
            if candidate.is_file():
                return str(candidate)

    # 2. 常见系统目录
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidates = [
        Path(system_root) / "hh.exe",
        Path(system_root) / "system32" / "hh.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    return None


def decompile_chm(chm_path: Path, output_dir: Path) -> int:
    """
    调用 hh.exe 将 chm 解包为 html。
    """
    hh = find_hh_exe()
    if not hh:
        print("未找到 hh.exe，请确认已安装 HTML 帮助查看器，并将其加入 PATH。", file=sys.stderr)
        return 1

    chm_path = chm_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"使用: {hh}")
    print(f"CHM 文件: {chm_path}")
    print(f"输出目录: {output_dir}")

    # hh.exe -decompile 输出目录 chm文件
    cmd = [hh, "-decompile", str(output_dir), str(chm_path)]
    print(f"执行命令: {' '.join(cmd)}")

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
        )
    except OSError as exc:  # noqa: BLE001
        print(f"执行 hh.exe 失败: {exc}", file=sys.stderr)
        return 1

    if proc.stdout:
        try:
            print(proc.stdout.decode("gbk", errors="ignore"))
        except Exception:  # noqa: BLE001
            # 某些系统下 hh.exe 输出可能不是文本，可以忽略
            pass

    if proc.stderr:
        try:
            msg = proc.stderr.decode("gbk", errors="ignore")
        except Exception:  # noqa: BLE001
            msg = str(proc.stderr)
        if msg.strip():
            print(msg, file=sys.stderr)

    if proc.returncode != 0:
        print(f"hh.exe 退出码非 0: {proc.returncode}", file=sys.stderr)
        return proc.returncode

    print("CHM 解包完成。")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用 hh.exe 将 CHM 文件解包为 HTML 目录。",
    )
    parser.add_argument(
        "chm",
        type=str,
        help="要解包的 CHM 文件路径，例如: 设备网络SDK使用手册.chm",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="html",
        help="HTML 输出目录（默认: html）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if os.name != "nt":
        print("当前脚本主要用于 Windows 环境（需要 hh.exe）。", file=sys.stderr)
        return 1

    args = parse_args(argv or sys.argv[1:])

    chm_path = Path(args.chm)
    if not chm_path.is_file():
        print(f"未找到 CHM 文件: {chm_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output)
    return decompile_chm(chm_path, output_dir)


if __name__ == "__main__":
    raise SystemExit(main())


