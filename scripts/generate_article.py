#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DAYSBalloon 宮古島 自動ブログ記事生成スクリプト（SEO/AIO強化版）
- Anthropic API で SEO 記事を 1 本生成（本文 + 記事専用FAQ を同時生成）
- blog/<slug>.html を出力 / blog/index.json を更新 / sitemap.xml を再生成
- blog/index.html の記事一覧を静的HTMLでも書き出す（JSを実行しないAIクローラー向け）
- 記事ごとに BlogPosting + BreadcrumbList + FAQPage の構造化データを付与
- 関連記事・サービス・LINE相談への内部リンクを自動挿入
- 同じタイトルの記事は二度と作らない（テーマ一覧を使い切ったら新テーマをAPIに考えさせる）
環境変数: ANTHROPIC_API_KEY が必須
"""
import os
import re
import json
import html as htmllib
import datetime
import urllib.request

SITE = "https://daysballoon-miyakojima.com"
BRAND = "DAYSBalloon 宮古島"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG_DIR = os.path.join(ROOT, "blog")
INDEX_JSON = os.path.join(BLOG_DIR, "index.json")
BLOG_INDEX_HTML = os.path.join(BLOG_DIR, "index.html")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
MODEL = "claude-haiku-4-5-20251001"
LINE_URL = "https://lin.ee/QJ74oFl"
OG_IMAGE = SITE + "/photo_019.jpg"

# テーマ定義: title / category / keywords(狙う検索語) / spots(本文に入れる実在の固有名詞)
# ※ 1テーマ=1記事。公開済みのタイトルは自動でスキップされる。
TOPICS = [
    {"title": "宮古島の与那覇前浜ビーチでサプライズ｜夕日とバルーンの演出アイデア",
     "category": "ビーチ演出", "keywords": ["宮古島 サプライズ", "与那覇前浜ビーチ サプライズ"],
     "spots": ["与那覇前浜ビーチ", "来間大橋"]},
    {"title": "宮古島の砂山ビーチで叶えるプロポーズ｜時間帯と準備のポイント",
     "category": "プロポーズ", "keywords": ["宮古島 プロポーズ", "砂山ビーチ プロポーズ"],
     "spots": ["砂山ビーチ"]},
    {"title": "宮古島・伊良部大橋を望むサプライズ演出｜ドライブ旅行の記念日に",
     "category": "記念日", "keywords": ["宮古島 記念日 サプライズ", "伊良部大橋"],
     "spots": ["伊良部大橋", "伊良部島"]},
    {"title": "宮古島・東平安名崎でのプロポーズ｜絶景の岬で想いを伝える方法",
     "category": "プロポーズ", "keywords": ["宮古島 プロポーズ スポット", "東平安名崎"],
     "spots": ["東平安名崎"]},
    {"title": "宮古島のリゾートホテルで誕生日サプライズ｜チェックイン前装飾の進め方",
     "category": "ホテルサプライズ", "keywords": ["宮古島 誕生日サプライズ", "宮古島 ホテル 誕生日"],
     "spots": ["シギラビーチ"]},
    {"title": "宮古島のオーシャンビュー客室で記念日サプライズ｜装飾の相談ガイド",
     "category": "ホテルサプライズ", "keywords": ["宮古島 ホテル サプライズ", "宮古島 オーシャンビュー 記念日"],
     "spots": ["与那覇前浜ビーチ"]},
    {"title": "宮古島のヴィラ・コテージでのサプライズ｜バルーン装飾を頼む前に知ること",
     "category": "ホテルサプライズ", "keywords": ["宮古島 ホテル サプライズ", "宮古島 ヴィラ サプライズ"],
     "spots": ["伊良部大橋"]},
    {"title": "宮古島の誕生日サプライズ完全ガイド｜旅行中に祝う段取りと演出",
     "category": "誕生日", "keywords": ["宮古島 誕生日サプライズ", "宮古島 誕生日"],
     "spots": ["与那覇前浜ビーチ", "シギラビーチ"]},
    {"title": "宮古島で彼女の誕生日を祝うサプライズ｜男性からの相談で多い質問",
     "category": "誕生日", "keywords": ["宮古島 彼女 誕生日", "宮古島 誕生日サプライズ"],
     "spots": ["与那覇前浜ビーチ", "砂山ビーチ"]},
    {"title": "宮古島で彼氏・夫の誕生日を祝うサプライズ｜大人っぽいバルーン装飾",
     "category": "誕生日", "keywords": ["宮古島 彼氏 誕生日", "宮古島 誕生日サプライズ"],
     "spots": ["伊良部大橋", "イムギャーマリンガーデン"]},
    {"title": "宮古島で子どもの誕生日を祝うバルーン装飾｜家族旅行の思い出づくり",
     "category": "誕生日", "keywords": ["宮古島 子ども 誕生日", "宮古島 家族旅行 サプライズ"],
     "spots": ["シギラビーチ", "パイナガマビーチ"]},
    {"title": "宮古島の新婚旅行（ハネムーン）サプライズ｜客室を彩るバルーン演出",
     "category": "記念日", "keywords": ["宮古島 新婚旅行 サプライズ", "宮古島 ハネムーン"],
     "spots": ["渡口の浜", "伊良部島"]},
    {"title": "宮古島で還暦・長寿のお祝い｜家族旅行で喜ばれるバルーン装飾",
     "category": "お祝い", "keywords": ["宮古島 還暦祝い", "宮古島 家族旅行 お祝い"],
     "spots": ["シギラビーチ", "イムギャーマリンガーデン"]},
    {"title": "宮古島の女子旅を盛り上げるバルーンデコレーション｜写真映えのコツ",
     "category": "女子旅", "keywords": ["宮古島 女子旅", "宮古島 女子旅 サプライズ"],
     "spots": ["与那覇前浜ビーチ", "17END"]},
    {"title": "宮古島の卒業旅行でサプライズ｜友人グループで楽しむバルーン演出",
     "category": "友人サプライズ", "keywords": ["宮古島 卒業旅行", "宮古島 サプライズ 友達"],
     "spots": ["砂山ビーチ", "パイナガマビーチ"]},
    {"title": "宮古島のプロポーズにおすすめの時間帯｜サンセットと星空の選び方",
     "category": "プロポーズ", "keywords": ["宮古島 プロポーズ", "宮古島 サンセット プロポーズ"],
     "spots": ["与那覇前浜ビーチ", "西平安名崎"]},
    {"title": "宮古島の星空の下でのプロポーズ｜夜のバルーン・ライト演出",
     "category": "プロポーズ", "keywords": ["宮古島 星空 プロポーズ", "宮古島 夜 サプライズ"],
     "spots": ["東平安名崎", "来間島"]},
    {"title": "宮古島プロポーズの準備スケジュール｜1か月前から当日までのチェックリスト",
     "category": "プロポーズ", "keywords": ["宮古島 プロポーズ 準備", "宮古島 プロポーズ"],
     "spots": ["砂山ビーチ", "与那覇前浜ビーチ"]},
    {"title": "宮古島プロポーズの言葉とタイミング｜バルーン演出に合わせる流れ",
     "category": "プロポーズ", "keywords": ["宮古島 プロポーズ タイミング", "宮古島 プロポーズ 演出"],
     "spots": ["イムギャーマリンガーデン", "伊良部大橋"]},
    {"title": "宮古島で雨の日でもできるサプライズ｜室内バルーン装飾という選択",
     "category": "サプライズのコツ", "keywords": ["宮古島 雨 サプライズ", "宮古島 サプライズ"],
     "spots": ["シギラビーチ", "イムギャーマリンガーデン"]},
    {"title": "宮古島の台風シーズンにサプライズを計画するときの注意点",
     "category": "サプライズのコツ", "keywords": ["宮古島 台風 旅行 サプライズ", "宮古島 サプライズ"],
     "spots": ["宮古空港", "下地島空港"]},
    {"title": "宮古島の夏（7〜9月）のサプライズ｜暑さと日差しに強いバルーン演出",
     "category": "季節の演出", "keywords": ["宮古島 夏 サプライズ", "宮古島 バルーン装飾"],
     "spots": ["与那覇前浜ビーチ", "新城海岸"]},
    {"title": "宮古島の冬（12〜2月）のサプライズ｜オフシーズン旅行を特別にする演出",
     "category": "季節の演出", "keywords": ["宮古島 冬 旅行 サプライズ", "宮古島 記念日"],
     "spots": ["東平安名崎", "シギラビーチ"]},
    {"title": "宮古島のクリスマスサプライズ｜リゾートで過ごす二人のためのバルーン装飾",
     "category": "季節の演出", "keywords": ["宮古島 クリスマス サプライズ", "宮古島 クリスマス"],
     "spots": ["シギラビーチ", "伊良部大橋"]},
    {"title": "宮古島のバレンタイン・ホワイトデーのサプライズ演出アイデア",
     "category": "季節の演出", "keywords": ["宮古島 バレンタイン サプライズ", "宮古島 ホワイトデー"],
     "spots": ["与那覇前浜ビーチ", "イムギャーマリンガーデン"]},
    {"title": "宮古島ブルーに映えるバルーンの色選び｜海と空に合う配色ガイド",
     "category": "装飾アイデア", "keywords": ["宮古島 バルーン装飾", "宮古ブルー バルーン"],
     "spots": ["与那覇前浜ビーチ", "17END"]},
    {"title": "宮古島の数字バルーン・文字バルーン活用術｜年齢と記念日を伝える装飾",
     "category": "装飾アイデア", "keywords": ["宮古島 数字バルーン", "宮古島 バルーン"],
     "spots": ["シギラビーチ", "与那覇前浜ビーチ"]},
    {"title": "宮古島の屋外でバルーンを使うときの風・暑さ対策",
     "category": "装飾アイデア", "keywords": ["宮古島 バルーン 屋外", "宮古島 ビーチ バルーン"],
     "spots": ["砂山ビーチ", "渡口の浜"]},
    {"title": "宮古島のホテルにバルーンは持ち込める？事前確認しておきたいポイント",
     "category": "サプライズのコツ", "keywords": ["宮古島 ホテル バルーン 持ち込み", "宮古島 ホテル サプライズ"],
     "spots": ["伊良部大橋", "イムギャーマリンガーデン"]},
    {"title": "宮古島サプライズを直前に頼みたいとき｜当日・前日の相談で確認すること",
     "category": "サプライズのコツ", "keywords": ["宮古島 サプライズ 当日", "宮古島 サプライズ 直前"],
     "spots": ["宮古空港", "平良市街地"]},
    {"title": "宮古島の伊良部島・下地島でのサプライズ｜17ENDと渡口の浜の楽しみ方",
     "category": "ビーチ演出", "keywords": ["伊良部島 サプライズ", "下地島 17END"],
     "spots": ["17END", "渡口の浜", "伊良部大橋"]},
    {"title": "宮古島・来間島と池間島で過ごす記念日｜橋を渡る旅のサプライズ",
     "category": "記念日", "keywords": ["宮古島 記念日", "来間島 池間島 記念日"],
     "spots": ["来間大橋", "池間大橋"]},
    {"title": "宮古島のリゾートウェディング ウェルカムスペースをバルーンで彩る方法",
     "category": "ウェディング", "keywords": ["宮古島 リゾートウェディング 装飾", "宮古島 ウェルカムスペース"],
     "spots": ["シギラビーチ", "与那覇前浜ビーチ"]},
    {"title": "宮古島の結婚式二次会・アフターパーティーのバルーン装飾",
     "category": "ウェディング", "keywords": ["宮古島 結婚式 二次会", "宮古島 ウェディング装飾"],
     "spots": ["平良市街地", "シギラビーチ"]},
    {"title": "宮古島でのジェンダーリビール｜旅先で楽しむ性別発表バルーン",
     "category": "お祝い", "keywords": ["宮古島 ジェンダーリビール", "宮古島 マタニティ旅行"],
     "spots": ["与那覇前浜ビーチ", "伊良部大橋"]},
    {"title": "宮古島の店舗オープン・周年イベントを盛り上げるバルーン装飾",
     "category": "店舗・イベント", "keywords": ["宮古島 店舗装飾 バルーン", "宮古島 オープン 装飾"],
     "spots": ["平良市街地", "西里通り"]},
    {"title": "宮古島の社員旅行・インセンティブ旅行でのサプライズ演出",
     "category": "店舗・イベント", "keywords": ["宮古島 社員旅行 サプライズ", "宮古島 団体 装飾"],
     "spots": ["シギラビーチ", "イムギャーマリンガーデン"]},
    {"title": "宮古島サプライズのよくある失敗と対策｜プロが見てきた注意点",
     "category": "サプライズのコツ", "keywords": ["宮古島 サプライズ 失敗", "宮古島 サプライズ"],
     "spots": ["与那覇前浜ビーチ"]},
    {"title": "宮古島サプライズの写真・動画をきれいに残すコツ",
     "category": "フォト演出", "keywords": ["宮古島 サプライズ 写真", "宮古島 フォト"],
     "spots": ["砂山ビーチ", "東平安名崎"]},
    {"title": "宮古島でレストランディナー中にサプライズするときの段取り",
     "category": "サプライズのコツ", "keywords": ["宮古島 レストラン サプライズ", "宮古島 ディナー 記念日"],
     "spots": ["平良市街地", "シギラビーチ"]},
]

SERVICE_LINKS = [
    ("ホテルサプライズ装飾", SITE + "/#service"),
    ("プロポーズ演出", SITE + "/#service"),
    ("記念日・誕生日サプライズ", SITE + "/#service"),
    ("よくあるご質問", SITE + "/#faq"),
]

# 事実確認できない内容を書かせないための共通ルール
RULES = (
    "【厳守ルール】\n"
    "・具体的な金額、割引率、件数、満足度などの数字は書かない。料金は『内容・規模・会場によって異なるため、LINEで無料見積もり』と案内する\n"
    "・『実際にあった事例』『お客様の声』を創作しない。事例風に書く場合は『たとえば〜という演出が考えられます』のように提案として書く\n"
    "・ホテルや施設との提携・公認・持ち込み可否を断定しない（『施設ごとに条件が異なるため事前確認が必要』と書く）\n"
    "・『バルーン 宮古島』『サプライズ 宮古島』のように単語を空白で並べた不自然な表現は使わず、自然な日本語で書く\n"
    "・特定のホテル名・施設名は書かず『宮古島のリゾートホテル』『リゾートのレストラン』のように表現する\n"
    "・当店が提供するのはバルーン装飾のみ（造花の花びらは用意可）。生花・花束・リングボックスの用意、写真・動画撮影は行っていないので、当店が提供するとは書かない（お客様ご自身で手配・撮影する前提で書く）\n"
    "・石垣島など宮古諸島以外の地名は書かない\n"
)


def esc(s):
    return htmllib.escape(s, quote=True)


def load_posts():
    if os.path.exists(INDEX_JSON):
        try:
            with open(INDEX_JSON, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def norm(t):
    return re.sub(r"[\s｜|・、。！？!?\-—―]+", "", t or "")


def pick_topic(posts):
    """未公開のテーマを上から順に選ぶ。使い切ったら None（APIに新テーマを考えさせる）"""
    used = {norm(p.get("title")) for p in posts}
    for t in TOPICS:
        if norm(t["title"]) not in used:
            return t
    return None


def slugify():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-article"


def api(prompt, max_tokens):
    key = os.environ["ANTHROPIC_API_KEY"]
    body = {"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode("utf-8"))
    text = data["content"][0]["text"].strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text).strip()
    return text


def invent_topic(posts):
    """テーマ一覧を使い切った後、既存と重ならない新テーマをAPIに1つ考えさせる"""
    titles = "\n".join("・" + p.get("title", "") for p in posts[:120])
    prompt = (
        "宮古島のバルーン装飾・サプライズ演出専門店のブログで、まだ書いていない新しい記事テーマを1つ考えてください。\n"
        "宮古島旅行でサプライズ・プロポーズ・誕生日・記念日・ウェディングを計画する人が実際に検索しそうな、具体的な疑問に答えるテーマにします。\n"
        "以下の公開済みタイトルと内容が重ならないこと。\n\n" + titles + "\n\n"
        "出力は次のJSONのみ:\n"
        '{"title": "「宮古島」で始まる32字以内のタイトル", "category": "8字以内のカテゴリ", '
        '"keywords": ["狙う検索語1", "狙う検索語2"], "spots": ["宮古島に実在するビーチや景勝地1", "同2"]}'
    )
    try:
        obj = json.loads(api(prompt, 400))
        if obj.get("title") and norm(obj["title"]) not in {norm(p.get("title")) for p in posts}:
            obj.setdefault("category", "サプライズのコツ")
            obj.setdefault("keywords", ["宮古島 サプライズ"])
            obj.setdefault("spots", ["与那覇前浜ビーチ"])
            return obj
    except Exception:
        pass
    return None


def write_article(topic):
    spots = "・".join(topic["spots"])
    kws = "』『".join(topic["keywords"])
    prompt = (
        "あなたは宮古島のバルーン装飾・サプライズ演出専門店『DAYSBalloon』のブログ編集者です。\n"
        "以下のテーマで、検索ユーザーの疑問に具体的に答える記事を日本語で書いてください。\n\n"
        "【テーマ】" + topic["title"] + "\n"
        "【狙う検索語】『" + kws + "』を見出しか本文に自然に含める\n"
        "【触れる固有名詞】" + spots + "（宮古島の実在スポット。少なくとも1つは本文に入れる）\n"
        "【構成】最初の<p>で結論（質問への答え）を100字以内で言い切る → 理由・手順・注意点をh2ごとに整理 → 最後にLINE相談を促す一文\n"
        + RULES + "\n"
        "出力は次のJSON形式のみ（前後に説明やコードブロック記号は不要）:\n"
        "{\n"
        '  "body": "記事本文のHTML。h2,h3,p,ul,ol,liのみ使用。1300〜1800字。h1やタイトルの繰り返しは入れない",\n'
        '  "faq": [\n'
        '    {"q": "このテーマに関する具体的な質問1（宮古島を含める）", "a": "80〜150字の回答"},\n'
        '    {"q": "質問2", "a": "回答2"},\n'
        '    {"q": "質問3", "a": "回答3"}\n'
        "  ]\n"
        "}\n"
    )
    text = api(prompt, 4500)
    try:
        obj = json.loads(text)
        content = obj.get("body", "").strip()
        faq = [f for f in obj.get("faq", []) if f.get("q") and f.get("a")][:3]
    except Exception:
        content = text
        faq = []
    # 安全弁: 他エリアの地名が混入していたら宮古島に置換
    for bad in ["石垣島", "八重山", "川平湾"]:
        content = content.replace(bad, "宮古島")
    return content, faq


def related_links(posts, current_slug, category=None, n=4):
    others = [p for p in posts if p.get("slug") != current_slug]
    same = [p for p in others if category and p.get("category") == category]
    rest = [p for p in others if p not in same]
    items = (same + rest)[:n]
    if not items:
        return ""
    li = "".join(
        '<li><a href="/blog/' + p["slug"] + '.html">' + esc(p["title"]) + "</a></li>" for p in items
    )
    return '<section class="related"><h2>関連記事</h2><ul>' + li + "</ul></section>\n"


def service_links_html():
    li = "".join('<li><a href="' + u + '">' + t + "</a></li>" for t, u in SERVICE_LINKS)
    return '<section class="services"><h2>' + BRAND + "のサービス</h2><ul>" + li + "</ul></section>\n"


def faq_html(faq):
    if not faq:
        return ""
    items = "".join(
        "<details><summary>" + esc(f["q"]) + "</summary><p>" + esc(f["a"]) + "</p></details>" for f in faq
    )
    return '<section class="faq"><h2>この記事に関するよくある質問</h2>' + items + "</section>\n"


def cta_html():
    return (
        '<section class="cta">'
        "<p>宮古島でのバルーン装飾・サプライズ演出は、DAYSBalloonにお任せください。ご相談・お見積もりは無料です。</p>"
        '<a class="cta-btn" href="' + LINE_URL + '" target="_blank" rel="noopener">LINEで無料相談する</a>'
        '<p class="cta-sub">お電話：<a href="tel:09082929414">090-8292-9414</a>（10:00〜19:00）</p>'
        "</section>\n"
    )


def render_article(topic, title, desc, slug, date, content, faq, posts, modified=None):
    url = SITE + "/blog/" + slug + ".html"
    modified = modified or date
    category = topic.get("category", "サプライズのコツ")
    head = (
        '<!DOCTYPE html>\n<html lang="ja">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "<title>" + esc(title) + "｜" + BRAND + "</title>\n"
        '<meta name="description" content="' + esc(desc) + '">\n'
        '<link rel="canonical" href="' + url + '">\n'
        '<meta name="robots" content="index, follow, max-image-preview:large">\n'
        '<meta property="og:title" content="' + esc(title) + '">\n'
        '<meta property="og:description" content="' + esc(desc) + '">\n'
        '<meta property="og:type" content="article">\n'
        '<meta property="og:url" content="' + url + '">\n'
        '<meta property="og:image" content="' + OG_IMAGE + '">\n'
        '<meta property="og:site_name" content="' + BRAND + '">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        '<link rel="icon" href="/favicon.ico" sizes="any">\n'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png">\n'
        '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600&family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">\n'
    )
    org = {"@type": "Organization", "name": BRAND, "url": SITE + "/"}
    ld_post = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": desc,
        "datePublished": date,
        "dateModified": modified,
        "image": OG_IMAGE,
        "inLanguage": "ja",
        "keywords": ", ".join(topic.get("keywords", [])),
        "articleSection": category,
        "author": org,
        "publisher": org,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    }
    ld_bread = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ホーム", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "ブログ", "item": SITE + "/blog/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": url},
        ],
    }
    ld = (
        '<script type="application/ld+json">' + json.dumps(ld_post, ensure_ascii=False) + "</script>\n"
        '<script type="application/ld+json">' + json.dumps(ld_bread, ensure_ascii=False) + "</script>\n"
    )
    if faq:
        ld_faq = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                for f in faq
            ],
        }
        ld += '<script type="application/ld+json">' + json.dumps(ld_faq, ensure_ascii=False) + "</script>\n"

    style = (
        "<style>\n"
        "*{margin:0;padding:0;box-sizing:border-box}\n"
        'body{font-family:"Noto Sans JP",sans-serif;background:#F5F0EA;color:#1A1A1A;line-height:1.9}\n'
        "a{color:#A88947}\n"
        ".wrap{max-width:760px;margin:0 auto;padding:0 24px}\n"
        ".site-header{padding:28px 0;border-bottom:1px solid rgba(168,137,71,.25)}\n"
        '.logo{font-family:"Cormorant Garamond",serif;font-size:1.6rem;text-decoration:none;color:#1A1A1A}\n'
        ".logo span{color:#A88947;font-style:italic}\n"
        ".crumb{font-size:.78rem;color:#888;padding:18px 0 0}\n"
        ".crumb a{color:#888;text-decoration:none}\n"
        "article{padding:32px 0 24px}\n"
        ".meta{font-size:.78rem;color:#A88947;letter-spacing:1px;margin-bottom:14px}\n"
        "article h1{font-size:1.7rem;font-weight:500;line-height:1.5;margin-bottom:28px}\n"
        "article h2,.faq h2,.related h2,.services h2{font-size:1.25rem;font-weight:500;margin:34px 0 14px;border-left:3px solid #A88947;padding-left:12px}\n"
        "article h3{font-size:1.05rem;margin:24px 0 10px}\n"
        "article p{margin-bottom:16px}\n"
        "article ul,article ol,.related ul,.services ul{margin:0 0 16px 1.4em}\n"
        ".faq details{background:#fff;border:1px solid rgba(168,137,71,.25);border-radius:8px;padding:14px 18px;margin-bottom:10px}\n"
        ".faq summary{cursor:pointer;font-weight:500}\n"
        ".faq details p{margin:10px 0 0;font-size:.92rem;color:#444}\n"
        ".cta{background:#fff;border:1px solid rgba(168,137,71,.35);border-radius:10px;padding:26px 22px;margin:36px 0;text-align:center}\n"
        ".cta p{margin-bottom:16px}\n"
        ".cta-btn{display:inline-block;background:#06C755;color:#fff;padding:14px 32px;border-radius:999px;text-decoration:none;font-weight:500}\n"
        ".cta .cta-sub{margin:14px 0 0;font-size:.85rem;color:#666}\n"
        ".back{padding:0 0 80px}\n"
        ".back a{display:inline-block;border:1px solid #A88947;color:#A88947;padding:12px 28px;border-radius:999px;text-decoration:none;font-size:.85rem}\n"
        ".site-footer{border-top:1px solid rgba(168,137,71,.25);padding:32px 0;text-align:center;font-size:.78rem;color:#888}\n"
        "</style>\n</head>\n<body>\n"
    )
    upd = "" if modified == date else "（更新 " + modified + "）"
    bodyhtml = (
        '<header class="site-header"><div class="wrap"><a href="/" class="logo">DAYS<span>Balloon</span></a></div></header>\n'
        '<main class="wrap">\n'
        '<nav class="crumb"><a href="/">ホーム</a> › <a href="/blog/">ブログ</a> › ' + esc(category) + "</nav>\n"
        "<article>\n"
        '<div class="meta">' + esc(category) + "｜" + date + upd + "</div>\n"
        "<h1>" + esc(title) + "</h1>\n" + content + "\n</article>\n"
        + faq_html(faq)
        + cta_html()
        + related_links(posts, slug, category)
        + service_links_html()
        + '<div class="back"><a href="/blog/">← 記事一覧へ戻る</a></div>\n</main>\n'
        '<footer class="site-footer"><div class="wrap">© ' + BRAND + " — Miyakojima Balloon Decoration &amp; Surprise</div></footer>\n"
        "</body>\n</html>\n"
    )
    return head + ld + style + bodyhtml


def build_sitemap(posts):
    today = datetime.date.today().strftime("%Y-%m-%d")
    urls = [
        "<url><loc>" + SITE + "/</loc><lastmod>" + today + "</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>",
        "<url><loc>" + SITE + "/blog/</loc><lastmod>" + today + "</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>",
    ]
    for p in posts:
        urls.append("<url><loc>" + SITE + "/blog/" + p["slug"] + ".html</loc><lastmod>" + p.get("modified", p["date"]) + "</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"
    with open(SITEMAP, "w", encoding="utf-8") as f:
        f.write(xml)


def build_blog_index(posts):
    """blog/index.html の <!--POSTS:START--> 〜 <!--POSTS:END--> を静的な記事一覧で置き換える"""
    if not os.path.exists(BLOG_INDEX_HTML):
        return
    with open(BLOG_INDEX_HTML, encoding="utf-8") as f:
        page = f.read()
    if "<!--POSTS:START-->" not in page:
        return
    cards = "\n".join(
        '<a class="post-card" href="/blog/' + p["slug"] + '.html"><div class="body">'
        '<div class="meta"><span class="cat">' + esc(p.get("category", "")) + "</span><span>" + p.get("date", "") + "</span></div>"
        "<h2>" + esc(p.get("title", "")) + "</h2><p>" + esc(p.get("description", "")) + "</p></div></a>"
        for p in posts
    )
    page = re.sub(r"<!--POSTS:START-->.*?<!--POSTS:END-->",
                  lambda m: "<!--POSTS:START-->\n" + cards + "\n<!--POSTS:END-->", page, flags=re.S)
    with open(BLOG_INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(page)


def make_desc(content):
    m = re.search(r"<p>(.*?)</p>", content, re.S)
    desc = re.sub(r"<[^>]+>", "", m.group(1)) if m else "宮古島のバルーン装飾・サプライズ演出の情報をお届けします。"
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc[:118]


def main():
    os.makedirs(BLOG_DIR, exist_ok=True)
    posts = load_posts()
    topic = pick_topic(posts) or invent_topic(posts)
    if not topic:
        print("No new topic available. Skipped.")
        return
    title = topic["title"]
    content, faq = write_article(topic)
    desc = make_desc(content)
    date = datetime.date.today().strftime("%Y-%m-%d")
    slug = slugify()
    page = render_article(topic, title, desc, slug, date, content, faq, posts)
    with open(os.path.join(BLOG_DIR, slug + ".html"), "w", encoding="utf-8") as f:
        f.write(page)
    posts = [p for p in posts if p.get("slug") != slug]
    posts.insert(0, {"date": date, "slug": slug, "category": topic.get("category", ""), "title": title, "description": desc})
    with open(INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    build_sitemap(posts)
    build_blog_index(posts)
    print("Generated:", slug, "|", title, "| FAQ:", len(faq))


if __name__ == "__main__":
    main()
