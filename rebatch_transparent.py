"""
重新對 raw/ 資料夾的原圖去背，覆寫 output_stickers/ 的主圖與縮圖（透明底 PNG）。
用法: python rebatch_transparent.py [--output output_stickers]
"""

import io
import argparse
import re
from pathlib import Path

from PIL import Image
from rembg import remove

LINE_MAIN_SIZE = (370, 320)
LINE_KEY_SIZE  = (96, 74)


def remove_background(img: Image.Image) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = remove(buf.getvalue())
    return Image.open(io.BytesIO(result)).convert("RGBA")


def fit_to_canvas(img: Image.Image, size: tuple) -> Image.Image:
    cw, ch = size
    img = img.copy().convert("RGBA")
    img.thumbnail((int(cw * 0.92), int(ch * 0.92)), Image.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (cw - img.width) // 2
    y = (ch - img.height) // 2
    canvas.paste(img, (x, y), mask=img.split()[3])
    return canvas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output_stickers")
    args = parser.parse_args()

    output_dir = Path(args.output)
    raw_dir = output_dir / "raw"

    raw_files = sorted(raw_dir.glob("*.png"))
    if not raw_files:
        print(f"❌ 找不到 raw 圖片: {raw_dir}")
        return

    print(f"找到 {len(raw_files)} 張圖，開始批次去背...\n")

    for raw_path in raw_files:
        stem = raw_path.stem  # e.g. "01_躺平放假"
        print(f"[處理] {stem}")

        img = Image.open(raw_path).convert("RGBA")
        nobg = remove_background(img)

        # 主圖
        main_img = fit_to_canvas(nobg, LINE_MAIN_SIZE)
        main_path = output_dir / f"{stem}.png"
        main_img.save(main_path, "PNG", optimize=True)
        print(f"  → 主圖: {main_path.name}  ({main_path.stat().st_size / 1024:.1f} KB)")

        # 縮圖
        key_img = fit_to_canvas(nobg, LINE_KEY_SIZE)
        key_path = output_dir / f"{stem}_key.png"
        key_img.save(key_path, "PNG", optimize=True)
        print(f"  → 縮圖: {key_path.name}  ({key_path.stat().st_size / 1024:.1f} KB)")

    print(f"\n✅ 全部完成！共處理 {len(raw_files)} 張。")


if __name__ == "__main__":
    main()
