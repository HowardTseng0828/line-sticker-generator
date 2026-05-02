"""
去背 + 調整至 LINE 規格
用法: python process_image.py <input_image> [--output <output_folder>]
"""

import sys
import argparse
from pathlib import Path
from io import BytesIO

from PIL import Image
from rembg import remove

LINE_MAIN_SIZE = (370, 320)
LINE_KEY_SIZE  = (96,  74)


def remove_background(img: Image.Image) -> Image.Image:
    buf = BytesIO()
    img.save(buf, format="PNG")
    result_bytes = remove(buf.getvalue())
    return Image.open(BytesIO(result_bytes)).convert("RGBA")


def resize_to_line_spec(img: Image.Image, size: tuple) -> Image.Image:
    img_copy = img.copy().convert("RGBA")
    img_copy.thumbnail(size, Image.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    offset = ((size[0] - img_copy.width) // 2, (size[1] - img_copy.height) // 2)
    canvas.paste(img_copy, offset, mask=img_copy.split()[3])
    return canvas


def main():
    parser = argparse.ArgumentParser(description="去背 + LINE 規格調整")
    parser.add_argument("input", help="輸入圖片路徑")
    parser.add_argument("--output", default="output_stickers", help="輸出資料夾")
    parser.add_argument("--name", default=None, help="輸出檔名前綴（預設使用輸入檔名）")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 找不到圖片: {input_path}")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = args.name or input_path.stem

    print(f"=== 處理圖片: {input_path} ===")

    img = Image.open(input_path).convert("RGBA")
    print("→ 去除背景...")
    nobg = remove_background(img)

    # 主圖
    main_img = resize_to_line_spec(nobg, LINE_MAIN_SIZE)
    main_path = output_dir / f"{name}.png"
    main_img.save(main_path, "PNG", optimize=True)
    print(f"→ 主圖 (370×320): {main_path}  ({main_path.stat().st_size / 1024:.1f} KB)")

    # 縮圖
    key_img = resize_to_line_spec(nobg, LINE_KEY_SIZE)
    key_path = output_dir / f"{name}_key.png"
    key_img.save(key_path, "PNG", optimize=True)
    print(f"→ 縮圖 (96×74):   {key_path}  ({key_path.stat().st_size / 1024:.1f} KB)")

    print(f"\n✅ 完成！輸出至 {output_dir.resolve()}")


if __name__ == "__main__":
    main()
