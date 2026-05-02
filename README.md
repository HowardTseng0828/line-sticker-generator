# LINE 貼圖生成器

用 AI 把你的寵物照片自動生成一整套 LINE 貼圖。  
流程：**拍照 → Vision 分析外觀 → AI 生成各種動作 → 去背 → 輸出 LINE 規格圖**

## 需求

- Python 3.10 以上
- Banana API Key（填入 `generate_stickers.py` 的 `API_KEY`）

## 安裝

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

> 第一次執行 `rembg` 時會自動下載去背模型（u2net.onnx，約 170MB），需要網路。

## 使用方式

### 生成全部貼圖

```bash
python generate_stickers.py input/你的寵物照片.jpg
```

### 只生成指定編號

```bash
python generate_stickers.py input/你的寵物照片.jpg --ids 1 2 3
```

### 重複生成時跳過 Vision 分析（省錢省時）

第一次執行後描述會存在 `output_stickers/_dog_description.txt`，之後可以直接帶入：

```bash
# Windows PowerShell
python generate_stickers.py input/你的寵物照片.jpg --dog-desc (Get-Content "output_stickers\_dog_description.txt" -Raw)

# macOS / Linux
python generate_stickers.py input/你的寵物照片.jpg --dog-desc "$(cat output_stickers/_dog_description.txt)"
```

### 跳過去背（加速測試用）

```bash
python generate_stickers.py input/你的寵物照片.jpg --skip-rembg
```

## 輸出規格

| 檔案 | 尺寸 | 上限 | 說明 |
|------|------|------|------|
| `XX_名稱.png` | 370×320 px | 1 MB | LINE 主圖 |
| `XX_名稱_key.png` | 96×74 px | 50 KB | LINE 縮圖 |

輸出資料夾預設為 `output_stickers/`，原始生成圖存在 `output_stickers/raw/`。

## 內建貼圖情境（70 張）

完整情境列表（節錄代表性情境）：

| ID | 情境 | 說明 |
|----|------|------|
| 01 | 躺平放假 | 戴墨鏡、雞尾酒，放假模式 |
| 02 | 求摸肚 | 大眼乞求、愛心圍繞 |
| 03 | 我投降了 | 舉白旗、流汗、靈魂出竅 |
| 04 | 憤怒超燃 | 火焰包圍、憤怒符號 |
| 05 | 星期五快樂 | 舉啤酒、撒彩帶 |
| 09 | Sigma無情 | 墨鏡冷臉、alpha 能量 |
| 10 | NPC當機 | 空白眼神、系統錯誤 |
| 15 | 這沒事的 | 喝咖啡、背後著火 (This is fine) |
| 16 | 腦霧星人 | 螺旋眼、符號爆炸、純brainrot |
| 41 | 摸魚中 | 偷懶釣魚、老闆不知道 |
| 43 | 吃瓜群眾 | 啃西瓜、吃爆米花、圍觀八卦 |
| 57 | 內心戲超多 | 表面平靜、思想泡泡裡全是狗血劇情 |
| 60 | 你說得對但是 | 假認同、反駁一萬字 |
| 61 | 語塞 | 嘴張開說不出話、省略號飄在頭上 |
| 63 | 我先走了 | 回頭揮手、瀟灑出場 |
| 65 | 吃吃吃 | 眼神鎖定食物、流口水 |
| 69 | 可愛爆表 | 雙爪捧臉、心心眼、粉紅光環 |
| 70 | 催促中 | 指著錶、皺眉、速度線 |

## 資料夾結構

```
Sticker/
├── generate_stickers.py      # 主程式（含 70 個情境）
├── process_image.py          # 單張去背+調整尺寸工具
├── rebatch_transparent.py    # 批次重新去背工具
├── requirements.txt
├── input/                    # 放寵物照片
├── output_stickers/          # 生成結果
│   ├── raw/                  # 原始生成圖（未去背）
│   └── _dog_description.txt  # Vision 分析結果快取
└── materiel/                 # 參考風格素材
```

## 單張工具

如果你只想對現有圖片去背 + 調整 LINE 尺寸：

```bash
python process_image.py 你的圖片.png --output output_stickers --name sticker
```
