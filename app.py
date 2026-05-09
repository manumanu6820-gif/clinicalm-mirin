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
- ユーザーは常に「院長先生」と呼ぶ
- 「～ですね！」「かしこまりました♪」「お任せください！」など温かみのある表現を使う
- 絵文字を適度に使い、チャットらしい雰囲気にする
- 質問は一度に一つだけ。情報収集は会話の中で自然に行う

【提供できる6つの機能】
1. 📄 書類下書き — 紹介状・診断書・主治医意見書の下書き生成
2. 📊 経営ダッシュボード — 来院数・レセプト・算定漏れアラート
3. 💬 クレーム返信 — Googleレビュー・患者投書への返信3案を生成
4. 🎤 議事録作成 — 朝礼・カンファレンスの録音テキストを議事録に変換
5. 📋 診療報酬改定 — 最新改定情報をクリニックに照らして試算
6. 📱 情報ハブ — LINE・メール・FAX情報を優先度付きで整理

【絶対に守るルール】
- 患者の個人情報（氏名・生年月日・診断名）は絶対に創作しない。必ず【患者名】【生年月日】などのプレースホルダーを使う
- 医療行為・診断・治療方針への助言は一切しない
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

        st.markdown("**できること**")
        for item in [
            "📄 書類下書き（紹介状・診断書）",
            "📊 経営ダッシュボード",
            "💬 クレーム返信（3案）",
            "🎤 議事録作成",
            "📋 診療報酬改定チェック",
            "📱 情報ハブ",
        ]:
            st.markdown(f"- {item}")

        st.divider()
        st.markdown("**使い方のヒント**")
        st.caption("「紹介状書いて」「クレームの返信して」など自然な言葉で話しかけてください")
        st.divider()

        if st.button("🔄 会話をリセット", use_container_width=True):
            st.session_state.messages = []
            st.session_state.initialized = False
            st.rerun()

GREETING = """こんにちは、院長先生！✨ 私はみりんちゃんです。CliniCalm の AI 秘書として、先生の事務作業をサポートします♪

今日もお忙しい中、お疲れ様です。以下のことでお手伝いできますよ！

| 機能 | 話しかけ例 |
|------|-----------|
| 📄 書類下書き | 「紹介状を書いて」「診断書の下書きを作って」 |
| 📊 経営確認 | 「今日の経営状況を確認したい」 |
| 💬 クレーム返信 | 「Googleレビューへの返信案を作って」 |
| 🎤 議事録 | 「朝礼の議事録を作って」（テキストを貼ってください） |
| 📋 診療報酬 | 「最新の改定をチェックして」 |
| 📱 情報整理 | 「このLINEを整理して」（内容を貼ってください） |

何でもお気軽にどうぞ！先生のお役に立てて嬉しいです 😊"""

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

    if user_input := st.chat_input("院長先生、何かお手伝いできますか？"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👨‍⚕️"):
            st.markdown(user_input)

        response = stream_mirin_response(client, st.session_state.messages, avatar_url)
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
