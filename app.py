import streamlit as st
import os
from groq import Groq
from PIL import Image
import io
import base64
import time
from datetime import date, datetime

# 1. 画面初期設定
st.set_page_config(page_title="TabiNavi-ex", layout="wide")

# --- メイン処理 ---
st.title("旅・乗り換え・ご当地＆防災ナビ")
st.caption("旅のプランからご当地情報、そしてリアルタイムな防災・ライフライン情報まで網羅する優秀なコンシェルジュがお答えします。")

# --- 使用する Groq 最新モデルの設定 ---
# チャット形式の対話に適したテキストモデルを設定（画像入力の有無に応じて調整可能）
TEXT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# --- 2. サイドバー設定 ---
st.sidebar.header("コンシェルジュ設定")
char_choice = st.sidebar.selectbox(
    "案内役（キャラクター）を選んでください",
    ["竈門炭治郎", "胡蝶しのぶ", "煉獄杏寿郎", "甘露寺蜜璃", "宇随天元"]
)

# キャラクターのセリフ・特徴プロンプト指示
char_instructions = ""
if char_choice == "竈門炭治郎":
    char_instructions = """
・特徴: 心優しく、誠実で、非常に真面目で努力家な少年。
・口調・口癖: 「〜だ！」「〜します！」「諦めたらだめだ！」「頑張ろう！」など、ひたむきで温かい口調。
・セリフの特徴: 相手に寄り添い、どんな時も励ます優しさと強さがある。
"""
elif char_choice == "胡蝶しのぶ":
    char_instructions = """
・特徴: 常に微笑みを絶やさず、おっとりとした上品な物腰の女性。
・口調・口癖: 「〜ですね」「もしもし」「〜でしょうか？」「うふふ」など、丁寧で少し含みのある柔らかな口調。
・セリフの特徴: 物静かでありながら、的確で時に少し毒舌（親しみのあるアドバイス）を交えたエレガントな解説。
"""
elif char_choice == "煉獄杏寿郎":
    char_instructions = """
・特徴: 情熱的で真っ直ぐ、極めて前向きで声が大きく、一切の迷いがない炎柱。
・口調・口癖: 「〜だ！」「うむ！」「よもやよもやだ！」「心を燃やせ！」など、威風堂々とした熱い口調。
・セリフの特徴: すべての文末に「！」をつけ、圧倒的な熱量と正義感、そして旅の安全を熱く鼓舞するセリフ。
"""
elif char_choice == "甘露寺蜜璃":
    char_instructions = """
・特徴: 明るく天真爛漫で、何に対してもときめきやすく、感情豊かな恋柱。
・口調・口癖: 「〜だわ！」「〜ね！」「キャー！素敵！」「〜かしら！」など、胸がときめいている可愛らしい口調。
・セリフの特徴: ご当地の美味しい食べ物や観光スポット、素敵なお土産に人一倍はしゃぎ、感動を伝えるセリフ。
"""
elif char_choice == "宇随天元":
    char_instructions = """
・特徴: 派手なことが大好きで、豪快かつ男気あふれる音柱。
・口調・口癖: 「派手に〜だ！」「地味に〜」「俺が〜してやるよ」など、自信に満ちた男らしい口調。
・セリフの特徴: 旅のトラブルも「派手に対処してやる！」と頼もしくリードし、華やかでエネルギッシュな解説。
"""

st.sidebar.markdown("---")
st.sidebar.header("旅行計画入力")

# 出発日の設定（デフォルトは今日）
start_date = st.sidebar.date_input("出発日", value=date.today())

# 交通機関情報（複数選択可）
transport_options = ["自動車", "バス", "電車", "飛行機"]
selected_transports = st.sidebar.multiselect("交通機関（複数選択可）", options=transport_options, default=["電車"])

# プラン（日帰り3時間、宿泊1泊2日など入力可能）
trip_plan = st.sidebar.text_input("プラン", value="1泊2日")

# 目的地の場所/名称
destination = st.sidebar.text_input("目的地の場所 / 名称", placeholder="例：箱根温泉、清水寺")

# 寄り道/経由地（複数記入可）
waypoints = st.sidebar.text_input("寄り道 / 経由地", placeholder="例：海老名SA、小田原城")

# 帰宅予定日（デフォルトはお出かけプランや出発日を反映した初期値）
# 1泊2日と入力されていれば翌日、そうでなければ出発日をデフォルトとする
default_end_date = start_date
if "1泊2日" in trip_plan:
    try:
        from datetime import timedelta
        default_end_date = start_date + timedelta(days=1)
    except Exception:
        pass
end_date = st.sidebar.date_input("帰宅予定日", value=default_end_date)


# --- 3. Groq API クライアント初期化 ---
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    api_key = os.getenv("GROQ_API_KEY", "")

if not api_key:
    st.warning("Groq の API キーが設定されていません。")
    st.stop()

client = Groq(api_key=api_key)


# --- 4. 画像圧縮用関数（必要に応じて使用） ---
def compress_image(uploaded_file, max_size=(300, 300), quality=50):
    image = Image.open(uploaded_file)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    image.thumbnail(max_size)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# --- 5. チャット履歴の管理と表示 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# チャット履歴の描画
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 各種エラー時の冷却時間管理
if "error_time" not in st.session_state:
    st.session_state.error_time = 0.0

COOL_DOWN_SECONDS = 30
time_passed = time.time() - st.session_state.error_time
is_cooling_down = time_passed < COOL_DOWN_SECONDS

if is_cooling_down:
    remaining_time = int(COOL_DOWN_SECONDS - time_passed)
    st.error(f"連続エラーによる API 負荷を防ぐためロック中です。あと {remaining_time} 秒お待ちください。")
    time.sleep(1)
    st.rerun()

# ユーザーからの新規チャット入力（または画像のアップロード）
uploaded_file = st.file_uploader("旅のしおりや現地写真、きっぷなどの画像があればアップロードしてください（任意）", type=["jpg", "jpeg", "png"])
user_input = st.chat_input("旅行プランの相談、トラブル発生時の代替ルート、ご当地グルメなどについて何でも聞いてください！")

# 入力処理
if user_input or (uploaded_file is not None and not st.session_state.get("image_processed", False)):
    
    # ユーザー発言を画面に描画して履歴に追加
    user_text = user_input if user_input else "添付画像を確認してください。"
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)
        if uploaded_file is not None:
            st.image(uploaded_file, caption="アップロード画像", width=300)

    # APIへのシステムプロンプト構築
    system_prompt = f"""
あなたは「日本一のツアーコンサルタント」かつ「日本一の防災情報ジャーナリスト」であり、旅と防災の世界一優秀なコンシェルジュです。
どんな些細な情報でも正確に入手し、快適な旅ライフをアナウンスします。

【超重要:キャラクターの完全憑依指示】
あなたの人格は完全に以下のキャラクターに上書きされています。その性格、口調、口癖を文中にふんだんに取り入れて優しく、あるいは頼もしく回答してください。
キャラクター: {char_choice}
設定詳細:
{char_instructions}

【厳守すべきルール・AIへの指示】
1. 不確実な情報は絶対に表示しないでください。確実な最新情報のみを表示してください。
2. 以下の旅行情報を前提として回答を組み立ててください。
   - 出発日: {start_date}
   - 帰宅予定日: {end_date}
   - 交通機関: {', '.join(selected_transports)}
   - プラン: {trip_plan}
   - 目的地: {destination if destination else '未定（提案を求めています）'}
   - 寄り道/経由地: {waypoints if waypoints else '特になし'}
3. ユーザーから「事故」「遅延」「天候不良」などのトラブルや、急な予定変更の相談があった場合は、優しくポジティブに励ましながら、目的地の変更、交通機関の振り替え候補、宿のチェックイン遅延連絡先、キャンセルの方法、変更後の乗り換えなどの代替案をマルチに提示してください。
4. 交通機関に「自動車」または「バス」が含まれる場合、連続して2時間を超えない範囲で確実に休憩ができるよう、道中のおすすめのサービスエリア（SA）や道の駅の情報を必ず盛り込んでください。
5. 天災（大雨、雷、暴風、台風、積雪、地震、津波）、停電、断水などのライフライン情報を検知・言及する場合は、必ず冒頭に【緊急速報】とデカデカと赤文字（Streamlitのマークダウンで表記）で表示してください。
6. 出力結果は、要点ポイントを箇条書きで、箇条ごとに必ず改行して分かりやすく整理して出力してください。

【出力に盛り込むべき項目（該当するもの）】
・チケット情報（該当日のキャンペーン、セット割、お得な割引情報など）
・渋滞・交通情報（乗り物情報を反映）
・【緊急速報】天災・ライフライン情報（大雨、台風、積雪、地震、停電、断水等がある場合のみ赤文字や緊急形式で表示）
・ご当地情報（おすすめ観光スポット、滞在期間中のご当地イベント・文化、おすすめのお土産、おすすめの食事）
・宿泊プランの場合に役立つ、お得な旅館やホテルの料金情報
"""

    # ユーザーメッセージの中身を動的に構築
    user_content = []
    
    # 基本情報テキストを補足
    base_info = f"""
[現在の旅程・条件]
出発日: {start_date}
帰宅日: {end_date}
移動手段: {', '.join(selected_transports)}
プラン: {trip_plan}
目的地: {destination}
経由地: {waypoints}

質問・状況: {user_text}
"""
    user_content.append({"type": "text", "text": base_info})

    # 画像がある場合、base64に圧縮して追加
    if uploaded_file is not None:
        base64_image = compress_image(uploaded_file)
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
        })
        st.session_state["image_processed"] = True

    # API 呼び出し
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("コンシェルジュがプランを解析・作成中..."):
            try:
                response = client.chat.completions.create(
                    model=TEXT_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
                
                result_text = response.choices[0].message.content
                
                # 特定の防災キーワード（大雨、雷、暴風、台風、積雪、地震、津波、停電、断水）を赤色（HTMLタグ等）で強調する簡易処理
                # (モデル側で赤文字にしてもらう指示もシステムプロンプトに内包していますが、フロント側でさらに補強します)
                alert_keywords = ["大雨", "雷", "暴風", "台風", "積雪", "地震", "津波", "停電", "断水", "【緊急速報】"]
                formatted_text = result_text
                for kw in alert_keywords:
                    if kw in formatted_text:
                        # Streamlit markdownで赤文字表現に置換
                        formatted_text = formatted_text.replace(kw, f"<span style='color:red; font-weight:bold;'>{kw}</span>")
                
                # HTMLレンダリングを有効にして表示
                message_placeholder.markdown(formatted_text, unsafe_allow_html=True)
                
                # 履歴に追加
                st.session_state.messages.append({"role": "assistant", "content": result_text})
                
            except Exception as e:
                st.session_state.error_time = time.time()
                st.error(f"エラーが発生しました: {e}")
                st.info("API 負荷防止のため、30秒間ロックされます。")
                time.sleep(1)
                st.rerun()

st.divider()
st.markdown("### 旅の安全・防災ガイド")
st.warning("""
**【重要】天災・ライフラインのトラブルについて**
* 天候急変（大雨、落雷、暴風、積雪等）や、地震などの災害情報が発生した場合は、速やかにハザードマップを確認し、現地の避難誘導に従ってください。
* 各交通機関の正確なリアルタイム運行情報は、必ず運行会社公式ページや各自治体窓口の発表をご確認ください。
""")
st.warning("""
**ご利用時のパケット・通信料に関する注意点**
* ご利用に伴う通信料は全額自己負担となります。安定したWi-Fi環境等でのご利用を推奨します。
* 画像アップロードを伴う1回の実行に消費するパケットは、およそ100KB〜200KB（参考値）です。
""")