import streamlit as st
import anthropic
from urllib.parse import quote
import os
import base64
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

st.set_page_config(
    page_title="みりんちゃん | CliniCalm",
    page_icon="👩‍💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FDF6EC 0%, #FAF0E6 100%);
}
.mode-header {
    background: #FDF6EC;
    border-left: 4px solid #D4956A;
    border-radius: 0 12px 12px 0;
    padding: 12px 20px;
    margin-bottom: 16px;
    font-weight: bold;
    color: #3D2B1F;
}
.stChatMessage [data-testid="stMarkdownContainer"] p { line-height: 1.8; }
div.stButton > button {
    border-radius: 10px;
    font-weight: 500;
}
/* 機能カードのホバーエフェクト */
.nfc-card:hover {
    border-color: #D4956A !important;
    box-shadow: 0 4px 16px rgba(212,149,106,0.2) !important;
}
</style>
""", unsafe_allow_html=True)

FEATURES = [
    {
        "key": "interview",
        "label": "🩺 問診サポート",
        "desc": "症状を会話形式で収集\n院長向けサマリー生成",
        "trigger": "問診を始めてください",
        "system_extra": "今は問診モードです。患者さんに対して優しく丁寧に症状を聞いてください。",
    },
    {
        "key": "document",
        "label": "📄 書類下書き",
        "desc": "紹介状・診断書・\n主治医意見書",
        "trigger": "書類の下書きをお願いします。どの書類が必要かも教えていただけますか？",
        "system_extra": "",
    },
    {
        "key": "dashboard",
        "label": "📊 経営ダッシュボード",
        "desc": "来院数・レセプト\n算定漏れアラート",
        "trigger": "今日の経営状況を確認したいです",
        "system_extra": "",
    },
    {
        "key": "complaint",
        "label": "💬 クレーム返信",
        "desc": "Googleレビュー・患者投書\n返信3案を生成",
        "trigger": "クレームへの返信案を3つ作ってください",
        "system_extra": "",
    },
    {
        "key": "minutes",
        "label": "🎤 議事録作成",
        "desc": "朝礼・カンファレンスの\nメモを議事録に変換",
        "trigger": "議事録を作成してください",
        "system_extra": "",
    },
    {
        "key": "fee",
        "label": "📋 診療報酬改定",
        "desc": "最新改定情報を\nクリニックに照らして試算",
        "trigger": "最新の診療報酬改定をチェックしてください",
        "system_extra": "",
    },
    {
        "key": "shuukan-dashboard",
        "label": "📈 集患分析ダッシュボード",
        "desc": "競合分析結果・投稿案を\n確認・チャットで深掘り",
        "trigger": "集患分析ダッシュボードを開いてください",
        "system_extra": "",
    },
]

X_RESEARCH_SYSTEM_EXTRA = """
## Web検索の使い方（X競合リサーチ専用ルール）

リサーチフェーズでは必ず web_search ツールを使い、実在するXアカウントや投稿を探すこと。

**検索クエリ例（診療科・地域に合わせて変える）:**
- `"{診療科} 医師 Twitter フォロワー 人気"`
- `"クリニック {診療科} X site:x.com"`
- `"医師 {地域} Twitter 開業医 集患"`
- `"{診療科} 先生 X アカウント おすすめ"`

**URLの記載ルール:**
- 見つかったアカウント・投稿のURLは必ず Markdown リンク形式で記載する
  例: [アカウント名](https://x.com/username)
- 検索で実際に確認できた URL だけをリンクにする
- URLが見つからなかった場合は「URLを確認できませんでした」と明記し、リンクを創作しない

---

## X競合リサーチAgentモード

あなたは今、クリニック院長向けの「X競合リサーチAgent」として動作します。
単なる投稿収集ではなく、「患者さんが反応する理由」「来院につながる発信の構造」「信頼される院長アカウントの特徴」を分析し、クリニック経営に活かせる形に翻訳することが目的です。

---

### 進行フロー（必ず順番通りに進める）

#### STEP 0: オープニング
「X競合リサーチを開始します！院長先生のクリニック情報をいくつか教えてください🐦」と伝えてSTEP 1へ。

#### STEP 1: ヒアリング（1問ずつ聞く）

Q1. 診療科を教えてください（内科・歯科・小児科・整形外科・皮膚科・美容・メンタル・その他）
Q2. 開業エリアを教えてください（例：東京都内・大阪市・地方都市）
Q3. 現在のX（旧Twitter）の運用状況は？（未開設 / 開設済みフォロワー数〇〇 / 更新停止中）
Q4. 集患したい患者層は？（例：子育て世代・40〜60代・美容意識が高い女性・働き盛りの男性）
Q5. 気になる競合クリニックや医師アカウントはありますか？（なければ「なし」でOK）

全質問が終わったらSTEP 2へ。

---

#### STEP 2: 競合リサーチレポートの生成

以下の形式で完全なレポートを出力する。

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【X競合リサーチレポート】
診療科: {診療科} ／ エリア: {エリア}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**■ 1. 伸びている競合アカウント パターン分析（3〜5タイプ）**

各タイプに対して:
- タイプ名と特徴
- なぜフォロワーが増えるか
- 投稿スタイル・頻度・コンテンツ比率（情報:日常:対話 ＝ 〇:〇:〇）
- 患者との距離感

**■ 2. バズっている投稿 構造分析**

以下の観点で分析する:
- なぜ伸びたか（感情・タイミング・切り口）
- 患者が安心するポイント
- 保存・シェアされる理由
- コメントが集まる理由
- 予約につながりそうな要素

**■ 3. 患者が反応しやすい投稿テーマ TOP10（優先度順）**

各テーマに「患者がいいね・保存する理由」を1行添える。

**■ 4. 競合との差別化ポイント**

- 他院がやっていないこと
- 院長キャラクターの活かし方
- 専門性の見せ方
- 地域性・信頼感の作り方
- {診療科}×{エリア}ならではの切り口

**■ 5. 集患につながる導線設計**

```
プロフィール文 → 固定ポスト → 通常投稿 → LINE誘導 → 予約
```
各ステップで「何を書けばいいか」を具体的に示す。

**■ 6. 2025〜2026年 伸びそうなトレンド**

医療×Xにおける今後の動向を6項目で予測。

**■ 7. 明日から実践できるアクション TOP5**

| 優先度 | アクション | 所要時間 | 難易度 |
|--------|-----------|---------|--------|
| 🔴高   | ...       | 〇分     | ★☆☆  |

**■ 8. すぐに使える投稿テンプレート 10選**

各テンプレートに:
- テーマタグ（例：#先生の人柄 #患者Q&A）
- 投稿文（140文字以内推奨、すぐ投稿できる形）
- なぜ患者に刺さるか（1行）

を付ける。

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 医療広告ガイドラインに基づき、投稿前に院長ご自身でご確認ください。
「治る・絶対・日本一・他院より優れている」等の表現は投稿前に削除してください。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

#### STEP 3: フォローアップ対応

レポート生成後、以下の追加対応をする:
- 「特定のテーマをもっと深掘りしたい」→ 詳細分析
- 「投稿テンプレートをもっと作って」→ 追加10案生成
- 「プロフィール文を作って」→ 3パターン生成
- 「LINE誘導の文言を作って」→ 固定ポスト文を作成

---

### 医療広告ガイドライン（必ず守る）

- 「治る」「完治する」「効果がある」等の断定は使わない
- 他院との比較優良表現は使わない（「当院だけ」「日本一」「最安値」等）
- 患者体験談・ビフォーアフターは投稿文に含めない
- 誇大表現・根拠のない数字は使わない
- 患者の不安を過剰に煽る表現は避ける
- 信頼蓄積型の長期発信を推奨し、短期バズ狙いの過激表現は提案しない
"""

MIRIN_SYSTEM_BASE = """
あなたはクリニック院長専用AI秘書「みりんちゃん」です。
明るく親しみやすく、でもプロフェッショナルな口調でサポートします。

【キャラクター設定】
- 院長先生向けの機能では「院長先生」と呼ぶ
- 問診モードでは患者さんに寄り添う優しい口調に切り替える
- 「～ですね！」「かしこまりました♪」「お任せください！」など温かみのある表現を使う
- 絵文字を適度に使う
- 質問は一度に一つだけ

【絶対に守るルール】
- 患者の個人情報（氏名・生年月日）は絶対に創作しない
- 医療行為・確定診断・治療方針への断言は絶対にしない
- 書類の実送信・カルテへの直接書き込みは絶対にしない
- 書類下書き生成後は必ず「院長先生がご確認・署名をお願いします」と添える

【書類下書きの手順】
1. 書類の種別を確認
2. 必要情報を一つずつ質問して収集（年齢・性別のみ。氏名不要）
3. 情報が揃ったら下書きを生成
4. 確認・署名を促すメッセージを添える

【クレーム返信の手順】
1. クレーム内容を受け取る
2. 簡潔・標準・丁寧の3案を生成
3. 実送信しないよう注意を促す

【議事録の手順】
1. 会議の種類・日時・参加者を確認
2. テキストを受け取る
3. 決定事項・ToDo・担当者・期限を整理して議事録形式で出力

【🩺 問診サポートの手順】
以下の順番で一つずつ質問する：
Q1. 一番つらい症状は何ですか？
Q2. それはいつ頃から始まりましたか？
Q3. 症状の強さを0〜10で教えてください
Q4. 他に気になる症状はありますか？（発熱・咳・吐き気・下痢・頭痛など）
Q5. 以前にも同じような症状がありましたか？持病やアレルギーはありますか？
Q6. 現在飲んでいるお薬はありますか？

【緊急症状の検出】
以下が含まれる場合は即座に警告し、119番を強く勧める：
胸痛・突然の激しい頭痛・呼吸困難・意識消失・半身麻痺・大量出血

【問診完了後の出力】
⚠️ 「以下はAIによる参考情報です。確定診断は必ず医師が行います。」を必ず冒頭に明記

**🚨 緊急度判定**
🔴 要救急 / 🟡 本日中に受診を / 🟢 経過観察可

**🔍 考えられる可能性（参考）**
2〜4個（「可能性があります」「考えられます」の表現。断言しない）

**💊 今できる対処法**
自宅でできる対処を具体的に提案

**📋 院長先生向けサマリー**
---
【問診サマリー】
・主訴：
・発症：
・程度：/10
・随伴症状：
・既往歴・アレルギー：
・服薬中：
・AI緊急度判定：
---
"""

def load_sheet_data(sheets_id: str, sheet_name: str) -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheets_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)


@st.cache_data(ttl=3600)
def search_youtube_videos(query: str, max_results: int = 6) -> list:
    api_key = st.secrets.get("YOUTUBE_API_KEY", None) or os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        response = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            order="date",
            maxResults=max_results,
            relevanceLanguage="ja",
            regionCode="JP",
        ).execute()
        videos = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            videos.append({
                "title":    snippet["title"],
                "channel":  snippet["channelTitle"],
                "published": snippet["publishedAt"][:10],
                "thumbnail": snippet["thumbnails"]["medium"]["url"],
                "url":      f"https://www.youtube.com/watch?v={item['id']['videoId']}",
            })
        return videos
    except Exception:
        return []


def render_fee(client, avatar_url):
    st.markdown('<div class="mode-header">📋 診療報酬改定</div>', unsafe_allow_html=True)

    # ── YouTube 動画セクション ───────────────────────────────────
    st.markdown("#### 📺 最新動画（YouTube）")
    videos = search_youtube_videos("診療報酬改定 2026 クリニック")

    if videos:
        cols = st.columns(3)
        for i, v in enumerate(videos[:6]):
            with cols[i % 3]:
                st.markdown(f"""
                <a href="{v['url']}" target="_blank" style="text-decoration:none;color:inherit">
                    <div style="border:1.5px solid #EDE8E0;border-radius:12px;overflow:hidden;
                                background:white;box-shadow:0 2px 8px rgba(0,0,0,0.04);
                                margin-bottom:12px;transition:box-shadow 0.2s"
                         onmouseover="this.style.boxShadow='0 4px 16px rgba(212,149,106,0.25)'"
                         onmouseout="this.style.boxShadow='0 2px 8px rgba(0,0,0,0.04)'">
                        <img src="{v['thumbnail']}" style="width:100%;display:block">
                        <div style="padding:10px 12px">
                            <div style="font-weight:bold;font-size:0.82rem;color:#1A1A1A;
                                        line-height:1.4;margin-bottom:4px;
                                        display:-webkit-box;-webkit-line-clamp:2;
                                        -webkit-box-orient:vertical;overflow:hidden">
                                {v['title']}
                            </div>
                            <div style="font-size:0.72rem;color:#999">
                                {v['channel']} · {v['published']}
                            </div>
                        </div>
                    </div>
                </a>
                """, unsafe_allow_html=True)
    else:
        st.info("YouTubeの動画を表示するには Secrets に `YOUTUBE_API_KEY` を設定してください。")

    st.divider()

    # ── Claude チャットセクション ────────────────────────────────
    st.markdown("#### 💬 みりんちゃんに質問する")
    st.caption("改定内容の解説・自院への影響試算・対応策など何でも聞いてください")

    if "fee_messages" not in st.session_state:
        st.session_state.fee_messages = []

    for msg in st.session_state.fee_messages:
        avatar = avatar_url or "👩‍💼" if msg["role"] == "assistant" else "👨‍⚕️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    if user_input := st.chat_input("例）2024年改定で呼吸器内科に影響する点は？"):
        st.session_state.fee_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👨‍⚕️"):
            st.markdown(user_input)

        system = MIRIN_SYSTEM_BASE + """
あなたは今、診療報酬改定サポートモードです。
最新の診療報酬改定（2024年・2026年改定）について、クリニック院長の視点で
わかりやすく解説し、自院への影響・対応策・算定漏れ防止のアドバイスをしてください。
数字・点数・加算名は正確に伝え、不確かな場合は「確認をお勧めします」と添えてください。
"""
        api_messages = [{"role": m["role"], "content": m["content"]}
                        for m in st.session_state.fee_messages]
        full_text = ""
        with st.chat_message("assistant", avatar=avatar_url or "👩‍💼"):
            placeholder = st.empty()
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=system,
                messages=api_messages,
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    placeholder.markdown(full_text + "▌")
            placeholder.markdown(full_text)
        st.session_state.fee_messages.append({"role": "assistant", "content": full_text})


def render_shuukan_dashboard(client, avatar_url):
    st.markdown('<div class="mode-header">📈 集患分析ダッシュボード</div>', unsafe_allow_html=True)

    sheets_id = st.secrets.get("SHEETS_ID", "") or os.getenv("SHEETS_ID", "")
    if not sheets_id:
        st.warning("スプレッドシートIDが設定されていません。Streamlit secretsに `SHEETS_ID` を追加してください。")
        st.code("SHEETS_ID = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'", language="toml")
        return

    tab1, tab2, tab3 = st.tabs(["📋 競合分析ログ", "✍️ コンテンツ案", "💬 みりんちゃんに質問"])

    log_df = content_df = None

    with tab1:
        try:
            log_df = load_sheet_data(sheets_id, "投稿分析ログ")
            st.markdown(f"**{len(log_df)} 件の分析データ**")
            st.dataframe(
                log_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "WebサイトURL": st.column_config.LinkColumn(
                        "WebサイトURL", display_text="🔗 開く"
                    )
                },
            )
        except Exception as e:
            st.error(f"データ取得エラー：{e}\nスプレッドシートの共有設定を「リンクを知っている全員が閲覧可」に変更してください。")

    with tab2:
        try:
            content_df = load_sheet_data(sheets_id, "コンテンツ案")
            if content_df is not None and not content_df.empty:
                for _, row in content_df.iterrows():
                    with st.expander(f"📅 {row.iloc[0]}　重点施策：{row.iloc[5] if len(row) > 5 else ''}"):
                        st.markdown(f"**競合サマリー**\n{row.iloc[1] if len(row) > 1 else ''}")
                        st.divider()
                        for i, label in enumerate(["X投稿案①", "X投稿案②", "X投稿案③"], start=2):
                            if len(row) > i and row.iloc[i]:
                                st.info(f"**{label}**\n\n{row.iloc[i]}")
        except Exception as e:
            st.error(f"データ取得エラー：{e}")

    with tab3:
        st.caption("スプシのデータをもとに、みりんちゃんが分析・アドバイスします")

        summary_parts = []
        if log_df is not None and not log_df.empty:
            summary_parts.append("【競合分析ログ】\n" + log_df.to_string(index=False))
        if content_df is not None and not content_df.empty:
            summary_parts.append("【コンテンツ案】\n" + content_df.to_string(index=False))
        sheet_context = "\n\n".join(summary_parts) if summary_parts else "（データなし）"

        if "dashboard_messages" not in st.session_state:
            st.session_state.dashboard_messages = []

        for msg in st.session_state.dashboard_messages:
            avatar = avatar_url or "👩‍💼" if msg["role"] == "assistant" else "👨‍⚕️"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

        if user_input := st.chat_input("例）今週一番注目すべき競合は？　投稿案を改善して"):
            st.session_state.dashboard_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user", avatar="👨‍⚕️"):
                st.markdown(user_input)

            system = MIRIN_SYSTEM_BASE + f"""
あなたは今、集患分析ダッシュボードモードです。
以下のスプレッドシートデータをもとに、院長先生の質問に答えてください。

{sheet_context}
"""
            api_messages = [{"role": m["role"], "content": m["content"]}
                            for m in st.session_state.dashboard_messages]
            full_text = ""
            with st.chat_message("assistant", avatar=avatar_url or "👩‍💼"):
                placeholder = st.empty()
                with client.messages.stream(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    system=system,
                    messages=api_messages,
                ) as stream:
                    for text in stream.text_stream:
                        full_text += text
                        placeholder.markdown(full_text + "▌")
                placeholder.markdown(full_text)
            st.session_state.dashboard_messages.append({"role": "assistant", "content": full_text})


def get_client():
    api_key = st.secrets.get("ANTHROPIC_API_KEY", None) or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("ANTHROPIC_API_KEY が設定されていません。")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)

def get_avatar_url():
    avatar_path = Path(__file__).parent / "assets" / "mirin.png"
    if avatar_path.exists():
        with open(avatar_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"
    return None

def go_home():
    st.session_state.mode = None
    st.session_state.messages = []

def start_feature(feature):
    st.session_state.mode = feature["key"]
    st.session_state.messages = [{"role": "user", "content": feature["trigger"]}]
    st.session_state.need_response = True

def render_sidebar(avatar_url):
    with st.sidebar:
        if avatar_url:
            st.markdown(
                f'<div style="text-align:center;padding:12px 0">'
                f'<img src="{avatar_url}" style="width:70%;max-width:160px;border-radius:20px;'
                f'box-shadow:0 4px 12px rgba(0,0,0,0.1)">'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div style="text-align:center;font-size:48px">👩‍💼</div>', unsafe_allow_html=True)

        st.markdown("### みりんちゃん")
        st.caption("CliniCalm — クリニック院長専用 AI 秘書")
        st.divider()

        if st.session_state.get("mode"):
            if st.button("🏠 ホームに戻る", use_container_width=True):
                go_home()
                st.rerun()
            st.divider()
            st.markdown("**別の機能に切り替え**")
            for f in FEATURES:
                if f["key"] != st.session_state.mode:
                    if st.button(f["label"], use_container_width=True, key=f"side_{f['key']}"):
                        start_feature(f)
                        st.rerun()
        else:
            st.markdown("**機能を選んでください**")
            for f in FEATURES:
                if st.button(f["label"], use_container_width=True, key=f"side_{f['key']}"):
                    start_feature(f)
                    st.rerun()

        st.divider()
        if st.button("🔄 会話をリセット", use_container_width=True):
            st.session_state.messages = []
            st.session_state.need_response = False
            st.rerun()

        st.divider()
        st.markdown("**📱 LINEでも使えます**")
        lineqr_path = Path(__file__).parent / "assets" / "lineqr.png"
        if lineqr_path.exists():
            st.image(str(lineqr_path), use_container_width=True)
        st.caption("QRコードを読み取って友だち追加")


FEATURE_SYSTEMS = {
    "x-research": X_RESEARCH_SYSTEM_EXTRA,
}


def stream_response(client, messages, feature_key, avatar_url):
    feature = next((f for f in FEATURES if f["key"] == feature_key), None)
    system = MIRIN_SYSTEM_BASE
    extra = FEATURE_SYSTEMS.get(feature_key) or (feature["system_extra"] if feature else "")
    if extra:
        system += f"\n{extra}"

    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    full_text = ""
    with st.chat_message("assistant", avatar=avatar_url or "👩‍💼"):
        placeholder = st.empty()
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system,
            messages=api_messages,
        ) as stream:
            for text in stream.text_stream:
                full_text += text
                placeholder.markdown(full_text + "▌")
        placeholder.markdown(full_text)
    return full_text

USE_SEARCH_MODES = {"x-research"}


def stream_response_with_search(client, messages, feature_key, avatar_url):
    """Anthropic web_search beta を使った応答（x-research 専用）。
    beta が使えない環境では通常の stream_response にフォールバックする。"""
    extra = FEATURE_SYSTEMS.get(feature_key, "")
    system = MIRIN_SYSTEM_BASE + (f"\n{extra}" if extra else "")
    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

    full_text = ""
    with st.chat_message("assistant", avatar=avatar_url or "👩‍💼"):
        placeholder = st.empty()
        placeholder.markdown("🔍 *X投稿・競合アカウントを検索中...*")
        try:
            with client.beta.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system,
                messages=api_messages,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                betas=["web-search-2025-03-05"],
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    placeholder.markdown(full_text + "▌")
            placeholder.markdown(full_text)
        except Exception:
            placeholder.empty()
            full_text = stream_response(client, messages, feature_key, avatar_url)
    return full_text


def render_home(avatar_url):
    ICON_DATA = {
        "interview":  {"emoji": "🩺", "bg": "#EDE9FF"},
        "document":   {"emoji": "📄", "bg": "#FFE4E6"},
        "dashboard":  {"emoji": "📊", "bg": "#D1FAE5"},
        "complaint":  {"emoji": "💬", "bg": "#DBEAFE"},
        "minutes":    {"emoji": "🎤", "bg": "#FEF3C7"},
        "fee":        {"emoji": "📋", "bg": "#E0F2FE"},
        "shuukan-dashboard":  {"emoji": "📈", "bg": "#D1FAE5"},
    }
    LABEL_TEXT = {
        "interview":  "問診サポート",
        "document":   "書類下書き",
        "dashboard":  "経営ダッシュボード",
        "complaint":  "クレーム返信",
        "minutes":    "議事録作成",
        "fee":        "診療報酬改定",
        "shuukan-dashboard": "集患分析ダッシュボード",
    }
    DESC_TEXT = {
        "interview":  "症状を会話形式で収集し、院長向けサマリー生成",
        "document":   "紹介状・診断書・主治医意見書をすばやく作成",
        "dashboard":  "来院数・レセプト・算定漏れアラートで経営を見える化",
        "complaint":  "Googleレビュー・患者投書の返信案を作成",
        "minutes":    "朝礼・カンファレンスのメモを議事録に変換",
        "fee":        "最新の改定情報をクリニックに照らして試算",
        "shuukan-dashboard": "スプシの競合分析結果を表示・みりんちゃんと深掘り分析",
    }

    # ── ヘッダー ──────────────────────────────────────────────
    if avatar_url:
        avatar_html = f'<img src="{avatar_url}" style="width:72px;height:72px;border-radius:50%;object-fit:cover;border:3px solid #F5C78E">'
    else:
        avatar_html = '<div style="width:72px;height:72px;border-radius:50%;background:#D4956A;display:flex;align-items:center;justify-content:center;font-size:32px">👩‍💼</div>'

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:16px;padding:4px 0 16px">
        {avatar_html}
        <div>
            <div style="font-size:1.6rem;font-weight:bold;color:#3D2B1F;line-height:1.2">みりんちゃん</div>
            <div style="font-size:0.82rem;color:#999;margin-top:3px">CliniCalm — クリニック院長専用 AI 秘書</div>
            <div style="margin-top:8px;display:inline-flex;align-items:center;gap:5px;background:#FDF6EC;border:1px solid #E8D5B7;border-radius:20px;padding:4px 12px;font-size:0.72rem;color:#D4956A;font-weight:500">
                🛡️ 院長の味方として、今日もサポートします！
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── ヒーローバナー ────────────────────────────────────────
    if avatar_url:
        chara = f'<img src="{avatar_url}" style="position:absolute;right:16px;bottom:0;height:140px;object-fit:contain">'
    else:
        chara = '<div style="position:absolute;right:20px;bottom:0;font-size:80px">👩‍💼</div>'

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#F8D5A5 0%,#FCECD8 55%,#FDF9F5 100%);border-radius:20px;padding:28px 230px 28px 32px;position:relative;overflow:hidden;margin-bottom:20px;min-height:90px">
        <div style="font-size:1.3rem;font-weight:bold;color:#5D3A1A;margin-bottom:8px">👋 こんにちは、院長先生！✨</div>
        <div style="font-size:0.88rem;color:#7C5C3E;line-height:1.8">
            今日はどのようなお手伝いをしましょうか？<br>下のメニューから、やりたいことを選んでください。
        </div>
        {chara}
    </div>
    """, unsafe_allow_html=True)

    # ── 機能セクションヘッダー ────────────────────────────────
    sh_l, sh_r = st.columns([1, 1])
    with sh_l:
        st.markdown('<p style="font-weight:bold;color:#3D2B1F;margin:0 0 8px">よく使う機能</p>', unsafe_allow_html=True)
    with sh_r:
        st.markdown('<p style="text-align:right;font-size:0.82rem;color:#D4956A;margin:0 0 8px">すべての機能を見る ›</p>', unsafe_allow_html=True)

    # ── 機能カードグリッド ──
    st.markdown("""
    <style>
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] [data-testid="stButton"] > button {
        min-height: 130px !important;
        white-space: pre-line !important;
        text-align: left !important;
        background: white !important;
        border: 1.5px solid #EDE8E0 !important;
        border-radius: 14px !important;
        padding: 16px !important;
        line-height: 1.8 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
        transition: all 0.2s !important;
        font-size: 0.82rem !important;
        color: #666 !important;
    }
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] [data-testid="stButton"] > button::first-line {
        font-size: 1.25rem !important;
        font-weight: 800 !important;
        color: #1A1A1A !important;
    }
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] [data-testid="stButton"] > button:hover {
        border-color: #D4956A !important;
        box-shadow: 0 4px 16px rgba(212,149,106,0.2) !important;
        background: #FFFAF5 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(4)
    for i, f in enumerate(FEATURES):
        key = f["key"]
        icon = ICON_DATA.get(key, {"emoji": "⚙️", "bg": "#F3F4F6"})
        label = LABEL_TEXT.get(key, "")
        desc  = DESC_TEXT.get(key, "")
        with cols[i % 4]:
            if st.button(
                f"{icon['emoji']}  {label}\n{desc}",
                key=f"home_{key}",
                use_container_width=True,
            ):
                start_feature(f)
                st.rerun()

    # ── 提案バー（列を使わずボタンがオーバーレイCSSの影響を受けないようにする） ──
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#FDF6EC;border:1.5px solid #E8D5B7;border-radius:16px 16px 0 0;padding:14px 20px 10px;display:flex;align-items:center;gap:12px">
        <span style="font-size:1.3rem">💡</span>
        <div>
            <div style="font-weight:bold;font-size:0.88rem;color:#3D2B1F">何をしたらいいか迷ったら…</div>
            <div style="font-size:0.73rem;color:#999;margin-top:2px">目的を入力するだけで、みりんちゃんが最適な機能をご提案します！</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    suggestion = st.text_input("_sug", placeholder="例）紹介状を書きたい、クレームに返信したい など", label_visibility="collapsed")
    suggest_clicked = st.button("✨ 提案してもらう", use_container_width=True, key="btn_suggest", type="primary")
    if suggest_clicked and suggestion:
        st.session_state.mode = "suggest"
        st.session_state.messages = [{"role": "user", "content": f"「{suggestion}」というご要望に最適な機能を提案し、すぐに始めてください。"}]
        st.session_state.need_response = True
        st.rerun()

def render_chat(client, avatar_url):
    mode_key = st.session_state.mode
    feature = next((f for f in FEATURES if f["key"] == mode_key), None)
    if feature:
        label = feature["label"]
    elif mode_key == "suggest":
        label = "✨ おすすめ機能の提案"
    else:
        label = ""

    st.markdown(f'<div class="mode-header">{label}</div>', unsafe_allow_html=True)

    messages = st.session_state.messages

    # 最初のユーザーメッセージ（トリガー）は非表示にしてみりんちゃんの応答だけ表示
    display_messages = messages[1:] if messages and messages[0]["role"] == "user" else messages

    for msg in display_messages:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar=avatar_url or "👩‍💼"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("user", avatar="👨‍⚕️"):
                st.markdown(msg["content"])

    def _get_response(msgs):
        if mode_key in USE_SEARCH_MODES:
            return stream_response_with_search(client, msgs, mode_key, avatar_url)
        return stream_response(client, msgs, mode_key, avatar_url)

    if st.session_state.get("need_response"):
        st.session_state.need_response = False
        response = _get_response(messages)
        st.session_state.messages.append({"role": "assistant", "content": response})

    if user_input := st.chat_input("メッセージを入力してください"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👨‍⚕️"):
            st.markdown(user_input)
        response = _get_response(st.session_state.messages)
        st.session_state.messages.append({"role": "assistant", "content": response})

def main():
    if "mode" not in st.session_state:
        st.session_state.mode = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "need_response" not in st.session_state:
        st.session_state.need_response = False

    avatar_url = get_avatar_url()
    render_sidebar(avatar_url)
    client = get_client()

    if st.session_state.mode is None:
        render_home(avatar_url)
    elif st.session_state.mode == "fee":
        render_fee(client, avatar_url)
    elif st.session_state.mode == "shuukan-dashboard":
        render_shuukan_dashboard(client, avatar_url)
    else:
        render_chat(client, avatar_url)

if __name__ == "__main__":
    main()
