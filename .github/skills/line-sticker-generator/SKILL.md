---
name: line-sticker-generator
description: "Generate LINE stickers by analyzing a user-provided image and producing stickers in the same style as the materiel folder: realistic photographic subject (e.g. real cat photo) cleanly cut out on white/transparent background, with cartoon or emoji-style props overlaid to create a fun meme-like expression. Use when user says: 生成貼圖, 幫我做貼圖, generate sticker, LINE sticker, create sticker, 貼圖風格, sticker style, 類似materiel風格."
argument-hint: "提供一張圖片，並描述想要的情緒/動作/道具（例如：生氣、開心、疑惑、拿玫瑰）"
---

# LINE Sticker Generator

## 風格說明（Style Reference）

本 Skill 的目標風格來自 `materiel/` 資料夾，特徵如下：

| 要素 | 說明 |
|------|------|
| **主體** | 真實照片品質的動物或角色（非插畫、非卡通） |
| **背景** | 純白色或透明，主體完全去背，無場景 |
| **道具** | 卡通/emoji 風格的道具疊加於寫實主體上（如武器、花、運動用品、特效） |
| **構圖** | 主體 + 道具，方形構圖，簡潔 |
| **情緒** | 主體表情與道具搭配創造 meme 幽默感 |
| **尺寸** | LINE 貼圖標準：370×320px（主圖）、96×74px（縮圖） |

### 風格範例對照

- 貓咪拿紅色球棒 → 霸氣/警告  
- 貓咪全身火焰特效 → 憤怒/超燃  
- 貓咪手持玫瑰 → 浪漫/撩人  
- 貓咪舉紅牌吹哨 → 裁判/不行  
- 貓咪問號聳肩 → 疑惑/無奈  
- 貓咪頭頂燈泡 → 靈感/想到了  
- 貓咪粉色蝴蝶結祈求眼神 → 撒嬌/拜託  

---

## 使用時機

- 使用者提供一張圖片，想要生成類似 materiel 風格的 LINE 貼圖
- 使用者想要為特定角色（貓、狗、人物等）製作一組表情貼圖
- 使用者想要生成單張或多張情境貼圖

---

## 操作流程（Procedure）

### Step 1：分析輸入圖片

使用 `view_image` 工具檢視使用者提供的圖片，識別：
- 主體類型（貓、狗、人、卡通角色等）
- 主體毛色/膚色/主要視覺特徵
- 主體當前表情與姿勢

### Step 2：確認情緒與道具

若使用者未指定，根據主體表情推薦 2–3 個道具方向，例如：

| 情緒 | 建議道具 |
|------|---------|
| 生氣/霸氣 | 火焰特效、球棒、紅牌 |
| 開心/得意 | 燈泡、拇指讚、獎牌 |
| 浪漫/撩人 | 玫瑰、愛心特效 |
| 疑惑/無奈 | 問號、聳肩姿勢 |
| 撒嬌/拜託 | 祈禱手勢、淚眼、粉色蝴蝶結 |
| 帥氣/酷 | 墨鏡、武士刀、光劍 |

### Step 3：組合圖像生成 Prompt

使用以下 Prompt 模板，套入 Step 1–2 的資訊後，呼叫 **Pollinations.ai**（免費，無需 API Key）：

**執行指令：**
```powershell
# 生成全部貼圖
python generate_stickers.py input/your_pet.jpg

# 只生成指定 ID
python generate_stickers.py input/your_pet.jpg --ids 1 3 5

# 只做去背+調整（已有圖片時）
python process_image.py "圖片.png" --name sticker_01
```

**英文 Prompt 模板：**
```
A high-quality realistic photographic [SUBJECT, e.g. "cream and orange tabby cat"] on a pure white background, cleanly cut out with no scenery or background objects.
The subject is [POSE/EXPRESSION, e.g. "looking directly at camera with a smug expression"],
[PROP DESCRIPTION, e.g. "holding a red rose delicately in one raised paw"].
The prop is rendered in a cartoon/emoji style layered on top of the realistic photo, creating a fun internet meme sticker effect.
Square composition, approximately 370x320 pixels, LINE sticker style.
No text. White or transparent background. High resolution, clean edges.
```

**中文風格描述模板（供翻譯參考）：**
```
[主體描述]，純白背景，完全去背無場景。
主體正在[姿勢/表情]，同時[道具互動描述]。
道具為卡通/emoji 風格疊加於寫實主體上，呈現 meme 貼圖幽默感。
方形構圖，LINE 貼圖尺寸 370×320px，無文字，白色或透明背景。
```

### Step 4：輸出與後製建議

1. 生成後確認圖片符合風格（寫實主體 + 卡通道具 + 白底）
2. 若背景不乾淨，建議使用：
   - [remove.bg](https://www.remove.bg/) 線上去背
   - Photoshop / GIMP 手動去背
   - Python `rembg` 套件自動去背
3. 調整至 LINE 規格：
   - 主圖：370×320px，PNG，< 1MB
   - 縮圖：96×74px，PNG

---

## LINE 貼圖官方規格

| 類型 | 尺寸 | 格式 | 上限 |
|------|------|------|------|
| 主圖（Main image） | 370×320 px | PNG（透明底佳） | 1 MB |
| 縮圖（Key image） | 96×74 px | PNG | 50 KB |
| 主題圖（Tab image on/off） | 96×74 px | PNG | 50 KB |
| 一套貼圖數量 | 8 / 16 / 24 / 32 | — | — |

---

## 參考素材位置

風格參考圖位於 `materiel/` 資料夾（工作區根目錄），直接以 `view_image` 讀取任意一張即可快速對齊風格：

```
materiel/812359177.png  → 拿棍棒，霸氣
materiel/812359179.png  → 火焰特效，憤怒
materiel/812359180.png  → 祈求眼神，撒嬌
materiel/812359185.png  → 玫瑰，浪漫
materiel/812359195.png  → 紅牌，裁判
materiel/812359203.png  → 問號，疑惑
materiel/812359210.png  → 燈泡，靈感
```

在生成前，建議先 `view_image` 上述 1–2 張，確保 prompt 描述精確對齊風格。
