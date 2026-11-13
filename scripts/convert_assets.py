"""开发工具：ffmpeg webm -> PNG 帧序列转换（不进运行时依赖）。

用法示例：ffmpeg -i input.webm -vf fps=24 frame_%03d.png
"""

from __future__ import annotations


def main() -> int:
    """转换入口（骨架，待实现）。

    :return: 进程退出码。
    """
    raise NotImplementedError("skeleton: convert_assets.main")


if __name__ == "__main__":
    raise SystemExit(main())
