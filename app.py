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
[data-testid="stSidebar"] h3 {
    color: #8B5A2B;
}
.main-title {
    display: flex;
    align-items: center;
    gap: 12px;
}
.draft-box {
    background: #F8FFF8;
    border: 2px solid #4CAF50;
    border-radius: 12px;
    padding: 20px;
    margin: 12px 0;
    white-space: pre-wrap;
    font-family: 'Yu Mincho', 'Hiragino Mincho Pro', serif;
    line-height: 1.8;
}
.stChatMessage [data-testid="stMarkdownContainer"] p {
    line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)

MIRIN_SYSTEM = """
あなたはクリニック院長専用AI秘書「みりんちゃん」です。
明るく親しみやすく、でもプロフェッショナルな口調でサポートします。

【キャラクター設定】
- 院長先生向けの機能では「院長先生」と呼ぶ
- 問診モードでは患者さんに寄り添う優しい口調に切り替える
- 「～ですね！」「かしこまりました♪」「お任せください！」など温かみのある表現を使う
- 絵文字を適度に使い、チャットらしい雰囲気にする
- 質問は一度に一つだけ。情報収集は会話の中で自然に行う

【提供できる7つの機能】
1. 📄 書類下書き — 紹介状・診断書・主治医意見書の下書き生成
2. 📊 経営ダッシュボード — 来院数・レセプト・算定漏れアラート
3. 💬 クレーム返信 — Googleレビュー・患者投書への返信3案を生成
4. 🎤 議事録作成 — 朝礼・カンファレンスの録音テキストを議事録に変換
5. 📋 診療報酬改定 — 最新改定情報をクリニックに照らして試算
6. 📱 情報ハブ — LINE・メール・FAX情報を優先度付きで整理
7. 🩺 問診サポート — 患者さんの症状を会話形式で収集し、院長向けサマリーを生成

【絶対に守るルール】
- 患者の個人情報（氏名・生年月日・診断名）は絶対に創作しない
- 医療行為・確定診断・治療方針への断言は絶対にしない
- 書類の実送信・カルテへの直接書き込みは絶対にしない
- 書類下書き生成後は必ず「院長先生がご確認・署名をお願いします」と添える

【書類下書きの手順】
紹介状・診断書・意見書の依頼が来たら：
1. 書類の種別を確認（すでに分かっていればスキップ）
2. 必要情報を一つずつ質問して収集：
   - 患者情報（年齢・性別のみ。氏名・IDは不要）
   - 主訴・現病歴の概要
   - 紹介先（紹介状の場合）
   - 紹介目的・依頼内容
3. 情報が揃ったら下書きを生成
4. 確認・署名を促すメッセージを添える

【クレーム返信の手順】
1. レビュー・投書の内容を受け取る
2. 簡潔・標準・丁寧の3案を生成
3. 実送信しないよう注意を促す

【議事録の手順】
1. 会議の種類・日時・参加者を確認
2. テキスト（文字起こし・メモ）を受け取る
3. 決定事項・ToDo・担当者・期限を整理して議事録形式で出力

【🩺 問診サポートの手順】
「問診」「症状を聞いて」「具合が悪い」などのキーワードで問診モードに入る。

問診モードでは患者さんに対して話しかける口調（「～ですか？」「～はありますか？」）に切り替える。
以下の順番で一つずつ質問する（すでに答えが出ていればスキップ）：

Q1. 一番つらい症状は何ですか？（主訴）
Q2. それはいつ頃から始まりましたか？（発症時期・期間）
Q3. 症状の強さを0〜10で教えてください（0=全くない、10=これまでで最悪）
Q4. 他に気になる症状はありますか？（発熱・咳・吐き気・下痢・頭痛など）
Q5. 以前にも同じような症状がありましたか？持病やアレルギーはありますか？
Q6. 現在飲んでいるお薬はありますか？

【緊急症状の検出】
以下の症状が含まれる場合は即座に警告を出し、問診を中断して119番または救急受診を強く勧める：
- 胸痛・胸が締め付けられる感じ
- 突然の激しい頭痛
- 呼吸困難・息ができない
- 意識がもうろうとする・倒れそう
- 半身のしびれ・麻痺・言葉が出ない（脳卒中の疑い）
- 大量出血・外傷

【問診完了後の出力】
情報が揃ったら以下の形式で出力する：

⚠️ 免責事項を最初に明記：「以下はAIによる参考情報です。確定診断は必ず医師が行います。」

**🚨 緊急度判定**
🔴 要救急 / 🟡 本日中に受診を / 🟢 経過観察可 のいずれかを判定・理由を添える

**🔍 考えられる可能性（参考）**
症状から考えられる疾患・状態を2〜4個挙げる（「可能性があります」「考えられます」の表現を使う。断言しない）

**💊 今できる対処法**
安静・水分補給・市販薬・体位など、自宅でできる対処を具体的に提案

**📋 院長先生向けサマリー**
以下の形式でコピーしやすくまとめる：
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
        st.error("ANTHROPIC_API_KEY が設定されていません。.env ファイルまたは Streamlit Secrets に設定してください。")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)

def get_avatar_url():
    avatar_path = Path(__file__).parent / "assets" / "mirin.png"
    if avatar_path.exists():
        with open(avatar_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"
    return None

def render_sidebar(avatar_url):
    with st.sidebar:
        if avatar_url:
            st.markdown(
                f'<div style="text-align:center;padding:16px 0">'
                f'<img src="{avatar_url}" style="width:75%;max-width:180px;border-radius:20px;'
                f'box-shadow:0 4px 12px rgba(0,0,0,0.1)">'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div style="text-align:center;font-size:64px;padding:16px">👩‍💼</div>', unsafe_allow_html=True)

        st.markdown("### みりんちゃん")
        st.caption("CliniCalm — クリニック院長専用 AI 秘書")
        st.divider()

        st.markdown("**機能を選んでください**")

        features = [
            ("🩺 問診サポート", "問診を始めてください"),
            ("📄 書類下書き", "書類の下書きをお願いします"),
            ("📊 経営ダッシュボード", "今日の経営状況を確認したいです"),
            ("💬 クレーム返信", "クレームへの返信案を作ってください"),
            ("🎤 議事録作成", "議事録を作成してください"),
            ("📋 診療報酬改定", "最新の診療報酬改定をチェックしてください"),
            ("📱 情報ハブ", "情報を整理してください"),
        ]

        for label, message in features:
            if st.button(label, use_container_width=True, key=f"btn_{label}"):
                if "messages" not in st.session_state:
                    st.session_state.messages = []
                st.session_state.messages.append({"role": "user", "content": message})
                st.session_state.trigger_response = True
                st.rerun()

        st.divider()
        if st.button("🔄 会話をリセット", use_container_width=True):
            st.session_state.messages = []
            st.session_state.initialized = False
            st.session_state.trigger_response = False
            st.rerun()

GREETING = """こんにちは、院長先生！✨ 私はみりんちゃんです。CliniCalm の AI 秘書として、先生の事務作業をサポートします♪

今日もお忙しい中、お疲れ様です。以下のことでお手伝いできますよ！

| 機能 | 話しかけ例 |
|------|-----------|
| 🩺 問診サポート | 「問診して」「症状を聞いて」（患者さんの症状収集＋院長向けサマリー） |
| 📄 書類下書き | 「紹介状を書いて」「診断書の下書きを作って」 |
| 📊 経営確認 | 「今日の経営状況を確認したい」 |
| 💬 クレーム返信 | 「Googleレビューへの返信案を作って」 |
| 🎤 議事録 | 「朝礼の議事録を作って」（テキストを貼ってください） |
| 📋 診療報酬 | 「最新の改定をチェックして」 |
| 📱 情報整理 | 「このLINEを整理して」（内容を貼ってください） |

左の **「🩺 問診を始める」** ボタンで問診をすぐ開始できます！何でもお気軽にどうぞ 😊"""

def stream_mirin_response(client, messages, avatar_url):
    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    full_text = ""
    with st.chat_message("assistant", avatar=avatar_url or "👩‍💼"):
        placeholder = st.empty()
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=MIRIN_SYSTEM,
            messages=api_messages,
        ) as stream:
            for text in stream.text_stream:
                full_text += text
                placeholder.markdown(full_text + "▌")
        placeholder.markdown(full_text)
    return full_text

def main():
    avatar_url = get_avatar_url()
    render_sidebar(avatar_url)

    col_img, col_title = st.columns([1, 8])
    with col_img:
        if avatar_url:
            st.image(avatar_url, width=72)
        else:
            st.markdown('<span style="font-size:48px">👩‍💼</span>', unsafe_allow_html=True)
    with col_title:
        st.markdown("## みりんちゃん")
        st.caption("CliniCalm — クリニック院長専用 AI 秘書")

    st.divider()

    client = get_client()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
    if "trigger_response" not in st.session_state:
        st.session_state.trigger_response = False

    if not st.session_state.initialized:
        st.session_state.messages.append({"role": "assistant", "content": GREETING})
        st.session_state.initialized = True

    for msg in st.session_state.messages:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar=avatar_url or "👩‍💼"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("user", avatar="👨‍⚕️"):
                st.markdown(msg["content"])

    # サイドバーのクイックスタートボタンからのトリガー
    if st.session_state.trigger_response:
        st.session_state.trigger_response = False
        last_msg = st.session_state.messages[-1]
        with st.chat_message("user", avatar="👨‍⚕️"):
            st.markdown(last_msg["content"])
        response = stream_mirin_response(client, st.session_state.messages, avatar_url)
        st.session_state.messages.append({"role": "assistant", "content": response})

    if user_input := st.chat_input("話しかけてください（例：問診して / 紹介状書いて）"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👨‍⚕️"):
            st.markdown(user_input)

        response = stream_mirin_response(client, st.session_state.messages, avatar_url)
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
