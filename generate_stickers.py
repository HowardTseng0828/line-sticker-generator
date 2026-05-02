"""
LINE 貼圖生成器 v3
流程：
  1. gpt-5.4（視覺）分析參考照片 → 取得狗狗精確外觀描述
  2. gpt-image-2 帶入描述 + 各情境 pose → 生成貼圖圖片
  3. rembg 去背
  4. Pillow 調整至 LINE 規格輸出

使用 Banana API (api.banana2556.com)，相容 OpenAI SDK
"""

import os
import sys
import base64
import io
import argparse
from pathlib import Path

import requests
from PIL import Image
from rembg import remove
from openai import OpenAI

# ─── 設定 ──────────────────────────────────────────────────────
API_KEY      = os.environ.get("BANANA_API_KEY", "your-api-key-here")
BASE_URL     = "https://api.banana2556.com/v1"
VISION_MODEL = "gpt-5.4"
IMAGE_MODEL  = "gpt-image-2"

LINE_MAIN_SIZE = (370, 320)
LINE_KEY_SIZE  = (96, 74)

# ─── 貼圖情境 ───────────────────────────────────────────────────
# 共用前綴：所有情境都要半身特寫
_HALF_BODY = (
    "HALF-BODY PORTRAIT, head and upper body only, cropped at the chest. "
    "Face is large and fills most of the frame. NO legs, NO lower body visible. "
    "Both front paws visible near face or chest. "
)

STICKER_SCENARIOS = [
    {
        "id": 1,
        "label": "躺平放假",
        "pose_prompt": (
            _HALF_BODY +
            "Leaning back lazily with both paws drooped in front, "
            "tiny cute cartoon sunglasses perched on nose, "
            "eyes half-closed in smug bliss, slight smirk. "
            "One paw holding a cartoon cocktail glass 🍹. "
            "Utterly unbothered, 'do not disturb' vibe."
        ),
    },
    {
        "id": 2,
        "label": "求摸肚",
        "pose_prompt": (
            _HALF_BODY +
            "Both paws raised up cutely in front of chest, "
            "enormous glittering pleading puppy eyes, "
            "rosy pink blushing cheeks, mouth slightly open showing tiny tongue. "
            "Cartoon pink hearts 💕 floating around the head, sparkling stars ✨."
        ),
    },
    {
        "id": 3,
        "label": "我投降了",
        "pose_prompt": (
            _HALF_BODY +
            "Both paws raised high in total surrender, "
            "utterly dead-inside exhausted stare, heavy drooping eyelids, "
            "tongue flopping sideways out of mouth. "
            "Cartoon white flag 🏳️ in one raised paw. "
            "Cartoon sweat drops 💦 all around. Completely done with everything."
        ),
    },
    {
        "id": 4,
        "label": "憤怒超燃",
        "pose_prompt": (
            _HALF_BODY +
            "Intense rage face: furrowed angry brows, wide blazing eyes, "
            "teeth bared in a fierce scowl, cheeks puffed out. "
            "Cartoon fire flames 🔥 erupting around the head. "
            "Red cartoon anger vein 💢 on forehead. Maximum fury energy."
        ),
    },
    {
        "id": 5,
        "label": "星期五快樂",
        "pose_prompt": (
            _HALF_BODY +
            "Massive open-mouthed grin showing teeth, eyes curved into happy crescents, "
            "one paw pumping a cartoon beer mug 🍺 high in the air, "
            "other paw doing a thumbs up 👍. "
            "Colorful cartoon confetti 🎉 and stars ⭐ bursting all around. "
            "Peak Friday happiness energy."
        ),
    },
    {
        "id": 6,
        "label": "求求你了",
        "pose_prompt": (
            _HALF_BODY +
            "Both paws pressed tightly together right in front of face in prayer, "
            "enormous watery teary eyes with visible cartoon tear drops rolling down cheeks, "
            "trembling lower lip, rosy blushing cheeks. "
            "Cartoon sparkle tears 💧. Desperately begging expression."
        ),
    },
    {
        "id": 7,
        "label": "躺贏",
        "pose_prompt": (
            _HALF_BODY +
            "Leaning back with one paw behind head in a smug relaxed pose, "
            "squinting smug half-closed eyes with a self-satisfied smirk, "
            "other paw making a casual finger-gun or OK gesture. "
            "Small shiny cartoon gold trophy 🏆 next to it. "
            "Gold sparkles ✨ and stars ⭐. Insufferably smug winner energy."
        ),
    },
    {
        "id": 8,
        "label": "疑惑發問",
        "pose_prompt": (
            _HALF_BODY +
            "Head dramatically tilted far to one side, "
            "one paw raised with index finger pointing up as if asking 'excuse me?', "
            "wide confused squinting eyes, one eyebrow raised skeptically. "
            "Large cartoon question marks ❓ floating above. "
            "Cartoon thought bubble 💭 nearby. Completely baffled meme face."
        ),
    },

    # ── 新增迷因情境 ──────────────────────────────────────────
    {
        "id": 9,
        "label": "Sigma無情",
        "pose_prompt": (
            _HALF_BODY +
            "Ultra-serious stoic alpha expression: chin slightly raised, "
            "half-lidded eyes staring straight ahead with zero emotion, "
            "completely deadpan face. Black cartoon sunglasses slowly sliding down nose. "
            "Dramatic dark vignette aura behind the head. "
            "Small bold text floating: 'SIGMA'. Gigachad no-nonsense energy."
        ),
    },
    {
        "id": 10,
        "label": "NPC當機",
        "pose_prompt": (
            _HALF_BODY +
            "Completely glazed-over blank stare, pupils as tiny dots, "
            "mouth hanging open in a dumb vacant expression. "
            "Cartoon loading spinner ⏳ above head. "
            "Cartoon Windows error popup 💻 floating next to face. "
            "Freeze-frame NPC brain stopped working meme face."
        ),
    },
    {
        "id": 11,
        "label": "電量0%",
        "pose_prompt": (
            _HALF_BODY +
            "Completely exhausted, barely staying upright, "
            "eyes drooping to almost fully closed, head slumping forward heavily, "
            "tongue hanging out limply, dark eye bags. "
            "Large cartoon battery icon 🔋 showing 0% red with the word DEAD. "
            "Cartoon ZZZ 💤 floating beside. Absolute depletion."
        ),
    },
    {
        "id": 12,
        "label": "Delulu自信",
        "pose_prompt": (
            _HALF_BODY +
            "Dreamy confident smile, eyes forming sparkly heart shapes 💕, "
            "rosy blushing cheeks, head tilted slightly with one paw on chin. "
            "Cartoon rose-colored glasses floating near eyes. "
            "Pink cartoon clouds ☁️ and rainbow 🌈 behind head. "
            "Stars ✨ and hearts 💖 everywhere. Delusional but thriving energy."
        ),
    },
    {
        "id": 13,
        "label": "暗中觀察",
        "pose_prompt": (
            _HALF_BODY +
            "Peeking upward with just the eyes and top of head visible above frame, "
            "eyes extremely wide and suspicious, darting sideways. "
            "One paw raised making binoculars gesture 🔍. "
            "Cartoon FBI hat on top of head. Dramatic dark shadow covering lower face. "
            "Cartoon eyes 👀 and spotlight beam on face. Total sus energy."
        ),
    },
    {
        "id": 14,
        "label": "主角光環",
        "pose_prompt": (
            _HALF_BODY +
            "Dramatic main-character pose: chin up, confident gleaming smile with sparkle ✨ on tooth, "
            "one paw pointing finger-guns at viewer 👈, "
            "eyes glowing with determination and confidence. "
            "Cartoon golden spotlight beam shining down from above. "
            "Dramatic wind blowing fur dramatically. Crown 👑 floating above head. "
            "Hero movie poster energy."
        ),
    },
    {
        "id": 15,
        "label": "這沒事的",
        "pose_prompt": (
            _HALF_BODY +
            "Calm serene smile expression despite obvious chaos, "
            "holding a cartoon coffee cup ☕ casually, "
            "completely unbothered pleasant expression. "
            "Cartoon fire flames 🔥 raging in the background behind the head. "
            "Speech bubble saying 'This is fine.' "
            "Dog sipping coffee surrounded by cartoon disaster. Classic 'This is fine' meme."
        ),
    },
    {
        "id": 16,
        "label": "腦霧星人",
        "pose_prompt": (
            _HALF_BODY +
            "Chaotic scrambled brain expression: spinning spiral eyes 🌀, "
            "completely unhinged goofy grin showing teeth, "
            "one paw raised pointing at absolutely nothing, "
            "fur sticking out in random spikes. "
            "Random cartoon emojis and symbols exploding from head: "
            "💫⭐🌀❗🍌🐸 scattered everywhere. "
            "Total brainrot chaos goblin energy."
        ),
    },

    # ── 新增迷因情境 2 ─────────────────────────────────────────
    {
        "id": 17,
        "label": "媽我上電視了",
        "pose_prompt": (
            _HALF_BODY +
            "Pointing both paws excitedly at the viewer as if being filmed, "
            "huge shocked open mouth grin, eyes wide and sparkling with disbelief, "
            "extremely excited expression. "
            "Cartoon camera 📹 and spotlight 🎬 pointing at face. "
            "Cartoon clapperboard and star ⭐ nearby. 'I'm famous' main character moment."
        ),
    },
    {
        "id": 18,
        "label": "老子不幹了",
        "pose_prompt": (
            _HALF_BODY +
            "Dramatically removing cartoon tie or lanyard with one paw and throwing it away, "
            "rebellious grin with one eye squinting, other eye wide with liberation energy. "
            "Cartoon briefcase 💼 being flung away in the background. "
            "Confetti 🎉 explosion. Giant cartoon exit door emoji nearby. "
            "'I QUIT' energy. Freedom face."
        ),
    },
    {
        "id": 19,
        "label": "咖啡續命",
        "pose_prompt": (
            _HALF_BODY +
            "Both paws tightly gripping an oversized cartoon coffee cup ☕, "
            "eyes half-open desperately staring into the coffee, "
            "dark circles under eyes, completely dead inside but clinging to life. "
            "Cartoon steam rising from cup forming a heart ❤️. "
            "Small cartoon IV drip stand next to the coffee cup. "
            "Monday morning survival mode face."
        ),
    },
    {
        "id": 20,
        "label": "已讀不回",
        "pose_prompt": (
            _HALF_BODY +
            "Looking sideways with extreme deliberate avoidance, one paw covering mouth, "
            "guilty side-eye expression with a tiny smirk, "
            "pretending not to notice. "
            "Cartoon smartphone 📱 showing blue read-tick floating next to face. "
            "Cartoon tumbleweed rolling by. 'I definitely saw it' guilty face."
        ),
    },
    {
        "id": 21,
        "label": "選我選我",
        "pose_prompt": (
            _HALF_BODY +
            "Both paws shooting straight up desperately like raising hands in class, "
            "eyes wide and eager, huge pleading smile showing all teeth, "
            "practically vibrating with desperation. "
            "Cartoon hand-raise emoji ✋ floating up. "
            "Bright cartoon spotlight beam ✨ targeting the head. "
            "Over-eager 'pick me' energy."
        ),
    },
    {
        "id": 22,
        "label": "收到收到",
        "pose_prompt": (
            _HALF_BODY +
            "Military-straight posture, one paw raised in sharp salute, "
            "completely serious and professional expression with narrowed focused eyes, "
            "other paw holding a tiny cartoon notepad 📋 and pen. "
            "Small cartoon checkmark ✅ floating nearby. "
            "Corporate serious yes-sir compliance face. Oddly formal for a dog."
        ),
    },
    {
        "id": 23,
        "label": "今晚我最美",
        "pose_prompt": (
            _HALF_BODY +
            "Glamorous dramatic pose: chin tilted up elegantly, eyes half-lidded with confidence, "
            "one paw delicately touching face like a model, "
            "tiny cartoon lipstick 💄 smudge on cheek. "
            "Cartoon glitter sparkles ✨ and diamonds 💎 surrounding head. "
            "Cartoon mirror reflecting a stunning version. "
            "Peak self-confidence glam energy."
        ),
    },
    {
        "id": 24,
        "label": "開會中勿擾",
        "pose_prompt": (
            _HALF_BODY +
            "Wearing tiny cartoon glasses and holding up a large cartoon 'DO NOT DISTURB' sign 🚫, "
            "extremely serious furrowed brow concentration face, "
            "pointing at the sign with one paw authoritatively. "
            "Cartoon laptop 💻 open in front. "
            "Cartoon fake busy-work stacks of papers floating around. "
            "Actually napping with eyes open energy."
        ),
    },
    {
        "id": 25,
        "label": "發大財",
        "pose_prompt": (
            _HALF_BODY +
            "Eyes replaced with cartoon dollar signs 💰, huge greedy grin showing all teeth, "
            "both paws rubbing together excitedly in scheming motion. "
            "Cartoon gold coins 🪙 and money bills 💵 raining down from above. "
            "Small cartoon slot machine 🎰 jackpot symbol nearby. "
            "Maximum wealth manifestation greed face."
        ),
    },
    {
        "id": 26,
        "label": "別看我",
        "pose_prompt": (
            _HALF_BODY +
            "Both paws covering face but eyes peeking through the gap between paws, "
            "extremely flustered blushing cheeks visible around paws, "
            "shy embarrassed energy. "
            "Cartoon sweat drops 💦 and rosy blush marks on cheeks. "
            "Small cartoon hiding emoji 🙈 nearby. "
            "Cute shy cover-face meme energy."
        ),
    },
    {
        "id": 27,
        "label": "報告完畢",
        "pose_prompt": (
            _HALF_BODY +
            "Standing at military attention, both paws stiffly at sides, "
            "extremely stiff serious expression with dead serious unblinking eyes, "
            "chin up like a soldier reporting to commander. "
            "Cartoon pointer stick in one paw pointing at a floating presentation chart 📊. "
            "Cartoon badge 🏅 on chest. Absurdly professional dog giving a TED talk."
        ),
    },
    {
        "id": 28,
        "label": "我可以我可以",
        "pose_prompt": (
            _HALF_BODY +
            "Confident flex pose with both paws making double thumbs-up 👍👍, "
            "enormous over-the-top confident grin with gleaming sparkle on tooth ✨, "
            "eyes blazing with overconfident can-do energy. "
            "Cartoon muscle flex 💪 icons floating around. "
            "Cartoon motivational poster lightning bolt ⚡ behind head. "
            "'I got this' but clearly has absolutely no idea what is happening energy."
        ),
    },

    # ── 新增迷因情境 3 ─────────────────────────────────────────
    {
        "id": 29,
        "label": "哭哭嗚嗚",
        "pose_prompt": (
            _HALF_BODY +
            "Dramatic ugly cry face: mouth wide open in a D-shape wail, "
            "eyes screwed tightly shut, eyebrows arched up in grief, "
            "multiple cartoon tear streams 😭 gushing down both cheeks. "
            "Cartoon snot bubble from nose. Trembling lower lip. "
            "Cartoon rain cloud 🌧️ above head. Peak ugly cry no-dignity meme face."
        ),
    },
    {
        "id": 30,
        "label": "算了算了",
        "pose_prompt": (
            _HALF_BODY +
            "Both paws raised up in resignation, eyes closed in peaceful acceptance, "
            "small defeated smile like nothing matters anymore. "
            "Cartoon white flag 🏳️ floating beside. "
            "Cartoon dust and tumbleweeds drifting by. "
            "Aura of complete 'I give up everything is fine' zen acceptance energy."
        ),
    },
    {
        "id": 31,
        "label": "閃開專業的來",
        "pose_prompt": (
            _HALF_BODY +
            "Striding forward confidently, one paw extended out to push things aside, "
            "other paw on hip, extremely smug half-lidded expert eyes, "
            "knowing smirk. Cartoon sunglasses 😎 flipping down onto nose. "
            "Cartoon 'EXPERT' badge 🏅 shining on chest. "
            "Cartoon people parting out of the way in background. "
            "Overconfident pro has arrived energy."
        ),
    },
    {
        "id": 32,
        "label": "對對對你說得對",
        "pose_prompt": (
            _HALF_BODY +
            "Nodding with an extremely unconvinced fake agreement face: "
            "forced smile, eyes clearly rolling internally, one paw making sarcastic thumbs up 👍. "
            "Other paw holding cartoon checkmark but looking very skeptical. "
            "Small cartoon thought bubble 💭 with '...no.' inside. "
            "Passive aggressive 'sure whatever you say' energy."
        ),
    },
    {
        "id": 33,
        "label": "好耶衝啊",
        "pose_prompt": (
            _HALF_BODY +
            "Explosive excitement: both paws thrown up in the air, "
            "eyes wide and blazing with hype, mouth open in a massive ecstatic yell, "
            "fur blown back from sheer energy. "
            "Cartoon lightning bolts ⚡ and fire 🔥 exploding outward. "
            "Cartoon fist pumping 👊 symbols. "
            "Cartoon crowd cheering in background. MAXIMUM HYPE ENERGY."
        ),
    },
    {
        "id": 34,
        "label": "懷疑人生",
        "pose_prompt": (
            _HALF_BODY +
            "Deeply philosophical vacant stare into the void, "
            "chin resting on one paw, eyes distant and existential, "
            "mouth slightly open like contemplating the meaninglessness of existence. "
            "Cartoon universe 🌌 and tiny planet Earth 🌍 floating above head. "
            "Cartoon existential question mark '...why?' floating. "
            "Profound melancholy but cute."
        ),
    },
    {
        "id": 35,
        "label": "這波穩了",
        "pose_prompt": (
            _HALF_BODY +
            "Leaning back with arms crossed and an insufferably smug grin, "
            "eyes half-closed in confident satisfaction, "
            "one paw doing a chef's kiss gesture 🤌. "
            "Cartoon checkmark ✅ and trophy 🏆 floating beside. "
            "Small crown 👑 tilted on head. "
            "Radiating 'I called it, everything is proceeding as planned' energy."
        ),
    },
    {
        "id": 36,
        "label": "不是吧不是吧",
        "pose_prompt": (
            _HALF_BODY +
            "Jaw dropped in complete disbelief, eyes bulging comically wide, "
            "both paws raised to sides of face in shock Home Alone style 🙀, "
            "fur standing on end. "
            "Cartoon lightning bolt of shock ⚡ behind head. "
            "Large cartoon exclamation marks ‼️ exploding everywhere. "
            "Cartoon anime-style shock lines radiating outward. Peak disbelief face."
        ),
    },
    {
        "id": 37,
        "label": "給我衝",
        "pose_prompt": (
            _HALF_BODY +
            "Furious battle charge expression: teeth bared in a battle cry yell, "
            "eyes burning with fierce determination, one paw pointing dramatically forward, "
            "fur charged with electric energy. "
            "Cartoon battle flag 🚩 waving behind head. "
            "Cartoon speed lines and dust cloud 💨 showing forward momentum. "
            "Cartoon anime battle aura 🔥 surrounding the body. CHARGE!"
        ),
    },
    {
        "id": 38,
        "label": "我要的不多",
        "pose_prompt": (
            _HALF_BODY +
            "Innocent angelic expression with wide sweet eyes and soft smile, "
            "both paws pressed together sweetly, "
            "tiny cartoon halo 😇 floating above head. "
            "But one paw holding a very long cartoon scroll 📜 unrolling with a huge list. "
            "Cartoon angel wings on back. "
            "'I'm so low maintenance' face while clearly being extremely demanding."
        ),
    },
    {
        "id": 39,
        "label": "被全世界拋棄",
        "pose_prompt": (
            _HALF_BODY +
            "Dramatically sad abandoned expression: single large cartoon tear rolling down cheek, "
            "lip trembling, eyes looking up like a sad anime character, "
            "one paw over heart. "
            "Cartoon spotlight on face with darkness all around. "
            "Cartoon violin 🎻 tiny and playing in background. "
            "Slow motion sad confetti falling. Main character suffering arc energy."
        ),
    },
    {
        "id": 40,
        "label": "本大爺來了",
        "pose_prompt": (
            _HALF_BODY +
            "Grand dramatic entrance pose: chin raised imperiously, "
            "one paw on hip and other arm extended outward royally, "
            "eyes half-lidded with noble authority and slight condescension. "
            "Cartoon golden crown 👑 sitting firmly on head. "
            "Cartoon rose petals 🌹 falling dramatically around. "
            "Cartoon royal cape 🎭 suggested behind shoulders. "
            "Insufferable nobility has arrived energy."
        ),
    },

    # ── 新增迷因情境 4 ─────────────────────────────────────────
    {
        "id": 41,
        "label": "摸魚中",
        "pose_prompt": (
            _HALF_BODY +
            "Sneakily slacking off: holding a tiny cartoon fishing rod 🎣 over a cartoon phone screen, "
            "one eye open checking surroundings suspiciously, other eye lazily drooping. "
            "Cartoon fish 🐟 hanging from the line symbolizing 'doing nothing'. "
            "Cartoon work papers untouched in background. "
            "Maximum stealth slacker at work energy."
        ),
    },
    {
        "id": 42,
        "label": "老闆來了",
        "pose_prompt": (
            _HALF_BODY +
            "Sudden panic alert: eyes blown wide in terror, sitting bolt upright, "
            "quickly hiding phone behind back with one paw, "
            "other paw hastily grabbing cartoon work papers 📄, "
            "sweating profusely with cartoon sweat beads 💦 flying everywhere. "
            "Cartoon boss shadow looming from the side. "
            "'Caught slacking' extreme panic face."
        ),
    },
    {
        "id": 43,
        "label": "吃瓜群眾",
        "pose_prompt": (
            _HALF_BODY +
            "Munching enthusiastically on a large cartoon watermelon slice 🍉, "
            "eyes wide and sparkling with nosy interest, leaning forward eagerly, "
            "juice dripping from chin. "
            "Cartoon popcorn 🍿 also nearby. "
            "Gossip drama floating in background as cartoon speech bubbles. "
            "'I am just here to watch the drama unfold' spectator energy."
        ),
    },
    {
        "id": 44,
        "label": "我全都要",
        "pose_prompt": (
            _HALF_BODY +
            "Both paws extended forward greedily trying to grab everything at once, "
            "enormous wide eyes burning with desire, huge open grin. "
            "Cartoon food 🍕, money 💰, trophy 🏆, heart ❤️ all floating within reach. "
            "Cartoon shopping cart 🛒 overflowing beside. "
            "Absolute maximum wanting-everything goblin mode energy."
        ),
    },
    {
        "id": 45,
        "label": "裝死中",
        "pose_prompt": (
            _HALF_BODY +
            "Playing dead dramatically: head flopped to one side, tongue hanging out completely, "
            "eyes showing only whites rolled back, utterly limp. "
            "Cartoon 'X X' eyes crossed out. "
            "Cartoon halo 😇 drifting above head. "
            "Small cartoon flies 🪰 circling the head. "
            "Peak avoidance playing-dead meme face."
        ),
    },
    {
        "id": 46,
        "label": "好想回家",
        "pose_prompt": (
            _HALF_BODY +
            "Chin resting heavily on both paws propped on invisible surface, "
            "eyes gazing longingly into the distance with deep yearning, "
            "small sad smile. "
            "Cartoon house 🏠 with a glowing warm window floating in a thought bubble 💭. "
            "Cartoon clock 🕐 moving slowly in background. "
            "'I just want to go home' thousand-yard stare energy."
        ),
    },
    {
        "id": 47,
        "label": "社恐發作",
        "pose_prompt": (
            _HALF_BODY +
            "Hunched slightly, both paws raised defensively in front of chest, "
            "wide frightened eyes darting sideways, cold sweat pouring down. "
            "Cartoon crowd silhouettes 👥 pressing in from both sides. "
            "Cartoon red alarm siren 🚨 above head. "
            "Cartoon escape route arrow pointing away. "
            "'Too many people, initiating shutdown' social anxiety meltdown face."
        ),
    },
    {
        "id": 48,
        "label": "破防了",
        "pose_prompt": (
            _HALF_BODY +
            "Emotional breakdown face: eyebrows crumpled upward, eyes welling with enormous glossy tears, "
            "lower lip jutting out in the biggest wobble, "
            "one paw pressed over heart dramatically. "
            "Cartoon cracked shield 🛡️ with cracks radiating outward. "
            "Cartoon piano keys 🎹 suggesting dramatic sad music. "
            "Completely emotionally compromised face."
        ),
    },
    {
        "id": 49,
        "label": "剛起床",
        "pose_prompt": (
            _HALF_BODY +
            "Freshly woken up chaos: fur completely disheveled sticking up in every direction, "
            "eyes half-glued shut with sleep, confused blank stare, "
            "one paw holding a cartoon pillow 🛏️ still. "
            "Cartoon ZZZ 💤 still floating. Dark under-eye circles. "
            "Cartoon alarm clock ⏰ smashed beside. "
            "True morning goblin just-woke-up disaster face."
        ),
    },
    {
        "id": 50,
        "label": "窮到只剩快樂",
        "pose_prompt": (
            _HALF_BODY +
            "Huge carefree grin despite obvious poverty: empty cartoon wallet turned upside down 👛 with cobwebs, "
            "sparkling happy eyes, one paw giving thumbs up 👍, "
            "completely unbothered by being broke. "
            "Cartoon single coin 🪙 floating sadly nearby. "
            "Cartoon rainbow 🌈 above head. "
            "'Zero money, maximum happiness' energy."
        ),
    },
    {
        "id": 51,
        "label": "別催我",
        "pose_prompt": (
            _HALF_BODY +
            "One paw held up in a 'stop' gesture firmly toward viewer, "
            "furrowed impatient brows, irritated sideways glare, "
            "other paw pointing at cartoon wristwatch ⌚. "
            "Cartoon speed lines stopped cold. "
            "Cartoon 'WAIT' sign 🛑 beside. "
            "Highly annoyed 'I'm working at my own pace' energy."
        ),
    },
    {
        "id": 52,
        "label": "撐住別倒",
        "pose_prompt": (
            _HALF_BODY +
            "Heroic suffering face: one paw raised in a determined fist despite clearly falling apart, "
            "one eye twitching, cracked tired smile, everything clearly going wrong. "
            "Cartoon cracks all over body like a breaking dam. "
            "Cartoon Band-Aid 🩹 patching the cracks. "
            "Cartoon motivational poster 'KEEP GOING' floating above. "
            "Peak barely-holding-it-together energy."
        ),
    },
    {
        "id": 53,
        "label": "謝謝再聯絡",
        "pose_prompt": (
            _HALF_BODY +
            "Polite but obviously done expression: perfect customer-service smile that doesn't reach the eyes, "
            "one paw waving a formal farewell 👋, "
            "other paw already pointing to the cartoon exit door. "
            "Cartoon door emoji 🚪 wide open. "
            "Cartoon 'NEXT' ticket number floating. "
            "Professionally dismissive 'have a nice day, goodbye forever' face."
        ),
    },
    {
        "id": 54,
        "label": "我在努力了",
        "pose_prompt": (
            _HALF_BODY +
            "Sweating intensely while doing absolutely minimal effort: "
            "one paw barely tapping a cartoon keyboard 💻 with one finger, "
            "tongue sticking out in extreme concentration, "
            "rivers of cartoon sweat 💦 pouring down. "
            "Cartoon tiny progress bar at 1% floating above. "
            "Expression of someone who believes they are working incredibly hard."
        ),
    },
    {
        "id": 55,
        "label": "下班了掰掰",
        "pose_prompt": (
            _HALF_BODY +
            "Explosive exit energy: bolting forward with both paws already reaching for cartoon bag 👜, "
            "ecstatic grin with sparkling eyes, completely transformed from work-mode. "
            "Cartoon clock striking exactly 6pm ⏰. "
            "Cartoon briefcase being thrown behind as they leave. "
            "Cartoon speed lines 💨 showing instant departure. "
            "'Transformed into a completely different being the second work ends' energy."
        ),
    },
    {
        "id": 56,
        "label": "聽說有吃的",
        "pose_prompt": (
            _HALF_BODY +
            "Ears perked up at maximum attention, eyes suddenly blazing awake and locked forward, "
            "mouth slightly open with visible drool drip 🤤, "
            "nose twitching with cartoon smell lines 〰️ wafting in. "
            "Cartoon food emoji 🍖🍕🍰 floating in the air toward nose. "
            "Went from 0 to 100 instantaneously upon hearing there is food energy."
        ),
    },
    {
        "id": 57,
        "label": "內心戲超多",
        "pose_prompt": (
            _HALF_BODY +
            "Completely calm neutral face on outside, but enormous cartoon thought bubble 💭 exploding above "
            "filled with a chaotic soap opera scene: cartoon tiny characters arguing, hearts breaking 💔, "
            "explosions 💥, dramatic lighting. "
            "Outside face: blank poker face. Inside thought bubble: full cinematic drama. "
            "Iceberg meme energy — surface calm, total chaos below."
        ),
    },
    {
        "id": 58,
        "label": "早安個屁",
        "pose_prompt": (
            _HALF_BODY +
            "Receiving a 'good morning' with murderous dead eyes: "
            "holding a cartoon coffee ☕ limply, hair completely wrecked, "
            "staring into the void with hollow lifeless eyes, "
            "forced upward corner of mouth that is definitely not a smile. "
            "Cartoon sun 🌅 mocked with a glare. "
            "'Do NOT talk to me before coffee' pure morning hatred energy."
        ),
    },
    {
        "id": 59,
        "label": "被誇獎了",
        "pose_prompt": (
            _HALF_BODY +
            "Overwhelmed with pride and bashfulness: enormous red blushing cheeks, "
            "shy smile trying to hide massive grin, one paw waving dismissively but clearly loving it, "
            "other paw covering blushing cheek. "
            "Cartoon glowing star ⭐ and hearts 💕 raining down. "
            "Cartoon golden laurel wreath 🌟 above head. "
            "'I'm so humble but please compliment me more' face."
        ),
    },
    {
        "id": 60,
        "label": "你說得對但是",
        "pose_prompt": (
            _HALF_BODY +
            "Holding up one paw in 'you make a fair point' gesture, "
            "eyes narrowed and mouth twisted in a 'but actually...' smirk, "
            "other paw already raised ready to drop a huge counterargument. "
            "Cartoon debate podium 🎙️ in front. "
            "Cartoon versus symbol ⚔️ floating. "
            "Cartoon essay scroll 📜 unrolling endlessly from behind. "
            "Debate club champion ready to destroy your argument energy."
        ),
    },

    # ── 新增迷因情境 5 ─────────────────────────────────────────
    {
        "id": 61,
        "label": "語塞",
        "pose_prompt": (
            _HALF_BODY +
            "Utterly speechless stunned expression: mouth slightly open in stunned silence, "
            "glassy wide eyes, one paw pressed over mouth, tiny floating ellipsis '...' above head, "
            "a faint sweat bead. Freeze-frame silence meme energy."
        ),
    },
    {
        "id": 62,
        "label": "超級開掛",
        "pose_prompt": (
            _HALF_BODY +
            "Overpowered 'cheat code' face: smug triumphant grin, eyes glowing with neon aura, "
            "both paws clenched in victory near chest, small pixel-glitch sparkles and a tiny 'CRIT' badge. "
            "Cartoon power-up lightning bolts ⚡. Maximum OP energy."
        ),
    },
    {
        "id": 63,
        "label": "我先走了",
        "pose_prompt": (
            _HALF_BODY +
            "Casual exit pose: turning head back with a cheeky half-smile, one paw raised in a quick wave, "
            "eyes twinkling with mischief, tiny cartoon door 🚪 and speed lines behind. "
            "Nonchalant 'I'm out' main-character exit energy."
        ),
    },
    {
        "id": 64,
        "label": "當機重啟",
        "pose_prompt": (
            _HALF_BODY +
            "System rebooting: glazed spinning eyes with pixelated swirl, small loading spinner ⏳ above head, "
            "faint static glitch overlay, and a tiny message bubble saying 'restarting...'. "
            "Cartoon error dialog 💻 for dramatic comedic effect."
        ),
    },
    {
        "id": 65,
        "label": "吃吃吃",
        "pose_prompt": (
            _HALF_BODY +
            "Ravenous food-hungry face: eyes locked onto food with sparkling hearts, drool at the corner of mouth, "
            "both paws clasped around a giant cartoon bone or steaming bowl 🍲, cartoon steam forming a heart. "
            "Pure 'feed me now' survival energy."
        ),
    },
    {
        "id": 66,
        "label": "高手在民間",
        "pose_prompt": (
            _HALF_BODY +
            "Low-key legendary expert vibe: calm confident half-smile, one paw casually gesturing like 'watch this', "
            "tiny sparkle effects ✨ and a small 'pro tip' sticky note floating nearby. "
            "Mildly smug, quietly unstoppable energy."
        ),
    },
    {
        "id": 67,
        "label": "偷偷告訴你",
        "pose_prompt": (
            _HALF_BODY +
            "Conspiratorial whisper: leaning in slightly with a mischievous grin, one paw covering mouth as if sharing a secret, "
            "eyes narrowed playfully, tiny cartoon whisper lines and a small 'psst' text bubble. "
            "Sneaky gossip-meme energy."
        ),
    },
    {
        "id": 68,
        "label": "別惹我",
        "pose_prompt": (
            _HALF_BODY +
            "Intimidating 'don't mess with me' glare: fierce narrowed eyes, teeth bared in a small snarl, "
            "one paw raised sternly, thundercloud and jagged comic sparks around head, cartoon 'NO' sign nearby. "
            "Absolute don't-test-me energy."
        ),
    },
    {
        "id": 69,
        "label": "可愛爆表",
        "pose_prompt": (
            _HALF_BODY +
            "Overwhelmingly adorable: paws clasped to cheeks, enormous sparkly puppy eyes, rosy blushing cheeks, "
            "tiny hearts and sparkles raining down, a pastel aura and the text 'too cute' in soft script. "
            "Melting everyone with cuteness energy."
        ),
    },
    {
        "id": 70,
        "label": "催促中",
        "pose_prompt": (
            _HALF_BODY +
            "Impatient 'hurry up' look: one paw pointing at an imaginary wristwatch, eyebrows sharply furrowed, "
            "tight-lipped annoyed mouth, small cartoon ticking clock ⏰ and speed lines around the head. "
            "Urgent get-moving energy."
        ),
    },
]


def analyze_dog(client: OpenAI, image_path: Path) -> str:
    """用 gpt-5.4 視覺分析狗狗外觀，回傳詳細英文描述。"""
    print(f"→ 分析參考照片外觀（{VISION_MODEL}）...")
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((512, 512))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()

    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": (
                    "Describe this dog in extreme detail for use as a consistent character in image generation. "
                    "Include: breed, fur colors and patterns, face features, eye color, nose, ear shape, body proportions, "
                    "any unique markings. Be precise and specific. Output in English, max 5 sentences."
                )}
            ]
        }],
        max_tokens=400,
    )
    description = resp.choices[0].message.content.strip()
    print(f"   描述取得：{description[:80]}...")
    return description


def generate_sticker_image(client: OpenAI, dog_description: str, pose_prompt: str) -> bytes:
    """組合 dog_description + pose_prompt，呼叫 gpt-image-2 生成圖片。"""
    full_prompt = (
        f"{dog_description} "
        f"{pose_prompt} "
        "IMPORTANT: pure white background only, absolutely no scenery, no floor, no other animals, no text. "
        "Realistic photo-style dog face with cartoon/emoji props overlaid. "
        "Highly expressive exaggerated face. "
        "LINE sticker style, close-up composition, clean white background, high quality PNG."
    )

    resp = client.images.generate(
        model=IMAGE_MODEL,
        prompt=full_prompt,
        n=1,
        size="1024x1024",
    )
    return base64.b64decode(resp.data[0].b64_json)


def remove_background(img: Image.Image) -> Image.Image:
    """rembg 去背，回傳透明底 RGBA。"""
    print("  → 去背...")
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


def process_sticker(
    client: OpenAI,
    dog_description: str,
    scenario: dict,
    output_dir: Path,
    skip_rembg: bool = False,
) -> None:
    sid   = scenario["id"]
    label = scenario["label"]
    print(f"\n[{sid:02d}] {label}")

    # 1. 生成圖片
    print("  → 生成圖片（gpt-image-2）...")
    raw_bytes = generate_sticker_image(client, dog_description, scenario["pose_prompt"])

    # 儲存原始圖
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    raw_path = raw_dir / f"{sid:02d}_{label}.png"
    with open(raw_path, "wb") as f:
        f.write(raw_bytes)

    raw_img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

    # 2. 去背
    if skip_rembg:
        nobg = raw_img
    else:
        nobg = remove_background(raw_img)

    # 3. 主圖（370×320）
    main_img = fit_to_canvas(nobg, LINE_MAIN_SIZE)
    main_path = output_dir / f"{sid:02d}_{label}.png"
    main_img.save(main_path, "PNG", optimize=True)
    print(f"  → 主圖: {main_path.name}  ({main_path.stat().st_size / 1024:.1f} KB)")

    # 4. 縮圖（96×74）
    key_img = fit_to_canvas(nobg, LINE_KEY_SIZE)
    key_path = output_dir / f"{sid:02d}_{label}_key.png"
    key_img.save(key_path, "PNG", optimize=True)
    print(f"  → 縮圖: {key_path.name}  ({key_path.stat().st_size / 1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(
        description="LINE 貼圖生成器 v3（Vision 分析 + AI 重新繪製動作）"
    )
    parser.add_argument("base_image", help="主角照片路徑（例如: input/corgi.jpg）")
    parser.add_argument("--output", default="output_stickers", help="輸出資料夾")
    parser.add_argument("--ids", nargs="*", type=int, help="只生成指定 ID，不填則全部")
    parser.add_argument("--skip-rembg", action="store_true", help="跳過去背步驟")
    parser.add_argument(
        "--dog-desc", default=None,
        help="直接提供外觀描述（跳過 Vision 分析，省 token）"
    )
    args = parser.parse_args()

    base_path = Path(args.base_image)
    if not base_path.exists():
        print(f"❌ 找不到照片: {base_path}")
        sys.exit(1)

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== LINE 貼圖生成器 v3（AI 生成動作）===")
    print(f"主角照片: {base_path.resolve()}")
    print(f"輸出資料夾: {output_dir.resolve()}")

    # Step 1: 取得外觀描述
    if args.dog_desc:
        dog_desc = args.dog_desc
        print(f"→ 使用提供的描述: {dog_desc[:80]}...")
    else:
        dog_desc = analyze_dog(client, base_path)
        # 儲存描述供後續重用
        desc_path = output_dir / "_dog_description.txt"
        desc_path.write_text(dog_desc, encoding="utf-8")
        print(f"→ 描述已儲存: {desc_path}")

    # Step 2: 逐張生成
    scenarios = STICKER_SCENARIOS
    if args.ids:
        scenarios = [s for s in STICKER_SCENARIOS if s["id"] in args.ids]
        if not scenarios:
            print(f"❌ 找不到指定 ID: {args.ids}")
            sys.exit(1)

    print(f"共 {len(scenarios)} 張貼圖待生成")

    for scenario in scenarios:
        try:
            process_sticker(client, dog_desc, scenario, output_dir, skip_rembg=args.skip_rembg)
        except Exception as e:
            print(f"  ❌ 貼圖 {scenario['id']} 失敗: {e}")
            import traceback; traceback.print_exc()

    print(f"\n✅ 完成！輸出至 {output_dir.resolve()}")
    print("   提示：下次可用 --dog-desc \"$(Get-Content output_stickers/_dog_description.txt)\" 跳過分析")


if __name__ == "__main__":
    main()
