import streamlit as st
import anthropic
import os
import base64
from pathlib import Path
from dotenv import load_dotenv

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
.feature-card {
    background: white;
    border: 1.5px solid #E8D5B7;
    border-radius: 16px;
    padding: 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    height: 140px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
}
.feature-card:hover {
    border-color: #D4956A;
    box-shadow: 0 4px 16px rgba(212,149,106,0.2);
}
.feature-icon { font-size: 2rem; }
.feature-title { font-size: 0.95rem; font-weight: bold; color: #3D2B1F; }
.feature-desc { font-size: 0.75rem; color: #888; line-height: 1.4; }
.home-header {
    background: linear-gradient(135deg, #D4956A 0%, #E8B48A 100%);
    border-radius: 16px;
    padding: 24px 32px;
    color: white;
    margin-bottom: 24px;
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
        "key": "infohub",
        "label": "📱 情報ハブ",
        "desc": "LINE・メール・FAXを\n優先度付きで整理",
        "trigger": "情報を整理してください。内容を貼り付けてもらえますか？",
        "system_extra": "",
    },
    {
        "key": "x-research",
        "label": "🐦 X競合リサーチ",
        "desc": "競合クリニック分析\n投稿テンプレート10選生成",
        "trigger": "X競合リサーチを始めてください。",
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
    col_img, col_text = st.columns([1, 6])
    with col_img:
        if avatar_url:
            st.image(avatar_url, width=80)
    with col_text:
        st.markdown("## みりんちゃん")
        st.caption("CliniCalm — クリニック院長専用 AI 秘書")

    st.markdown("""
    <div class="home-header">
        <div style="font-size:1.1rem;font-weight:bold">こんにちは、院長先生！✨</div>
        <div style="margin-top:6px;opacity:0.9">今日もお疲れ様です。何をお手伝いしましょうか？<br>下のボタンから機能を選んでください。</div>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(3)
    for i, f in enumerate(FEATURES):
        with cols[i % 3]:
            if st.button(
                f"{f['label']}\n\n{f['desc']}",
                use_container_width=True,
                key=f"home_{f['key']}",
                help=f['desc'],
            ):
                start_feature(f)
                st.rerun()

def render_chat(client, avatar_url):
    mode_key = st.session_state.mode
    feature = next((f for f in FEATURES if f["key"] == mode_key), None)
    label = feature["label"] if feature else ""

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
    else:
        render_chat(client, avatar_url)

if __name__ == "__main__":
    main()
