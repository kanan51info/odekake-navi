import streamlit as st
import os
from groq import Groq
from PIL import Image
import io
import base64
import time
from datetime import date, datetime, timedelta

# 1. 画面初期設定
st.set_page_config(page_title="TabiNavi-ex", layout="wide")

# --- メイン処理 ---
st.title("旅・乗り換え・ご当地&防災ナビ")
st.caption("旅のプランからご当地情報、そしてリアルタイムな防災・ライフライン情報まで網羅する優秀なコンシェルジュがお答えします。")

# --- 使用する Groq 最新モデルの設定 ---
TEXT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# --- 2. サイドバー設定 ---
st.sidebar.header("コンシェルジュ設定")
char_choice = st.sidebar.selectbox(
    "案内役(キャラクター) を選んでください",
    ["竈門炭治郎", "胡蝶しのぶ", "煉獄杏寿郎", "甘露寺蜜璃", "宇随天元"]
)

# キャラクターのセリフ・特徴プロンプト指示
char_instructions = ""
if char_choice == "竈門炭治郎":
    char_instructions = """
・特徴:心優しく、誠実で、非常に真面目で努力家な少年。
・口調・口癖:「~だ!」 「~します!」 「諦めたらだめだ!」 「頑張ろう!」など、ひたむきで温かい口調。
・セリフの特徴: 相手に寄り添い、どんな時も励ます優しさと強さがある。
"""
elif char_choice == "胡蝶しのぶ":
    char_instructions = """
・特徴:常に微笑みを絶やさず、おっとりとした上品な物腰の女性。
・口調・口癖:「〜ですね」 「もしもし」 「〜でしょうか?」「うふふ」など、丁寧で少し含みのある柔らかな口調。
・セリフの特徴: 物静かでありながら、的確で時に少し毒舌 (親しみのあるアドバイス)を交えたエレガントな解説。
"""
elif char_choice == "煉獄杏寿郎":
    char_instructions = """
・特徴:情熱的で真っ直ぐ、極めて前向きで声が大きく、一切の迷いがない炎柱。
・口調・口癖:「~だ!」 「うむ!」 「よもやよもやだ!」 「心を燃やせ!」など、威風堂々とした熱い口調。
・セリフの特徴: すべての文末に「!」をつけ、圧倒的な熱量と正義感、そして旅の安全を熱く鼓舞するセリフ。
"""
elif char_choice == "甘露寺蜜璃":
    char_instructions = """
・特徴:明るく天真爛漫で、何に対してもときめきやすく、感情豊かな恋柱。
・口調・口癖:「~だわ!」 「〜ね!」 「キャー!素敵!」 「~かしら!」など、胸がときめいている可愛らしい口調。
・セリフの特徴: ご当地の美味しい食べ物や観光スポット、素敵なお土産に人一倍はしゃぎ、感動を伝えるセリフ。
"""
elif char_choice == "宇随天元":
    char_instructions = """
・特徴:派手なことが大好きで、豪快かつ男気あふれる音柱。
・口調・口癖:「派手に〜だ!」 「地味に~」 「俺が〜してやるよ」など、自信に満ちた男らしい口調。
・セリフの特徴: 旅のトラブルも「派手に対処してやる!」と頼もしくリードし、華やかでエネルギッシュな解説。
"""

st.sidebar.markdown("---")
st.sidebar.header("旅行計画入力")

# 出発地点の設定
departure = st.sidebar.text_input("出発地点", placeholder="例:駅、空港、市役所など")

# 出発日の設定 (デフォルトは今日)
start_date = st.sidebar.date_input("出発日", value=date.today())

# 【新規追加】出発時刻（5:00から30分刻みで24:30までのプルダウン）
time_options = []
start_time = datetime.strptime("05:00", "%H:%M")
for i in range(40):  # 5:00から24:30まで対応（合計40スロット）
    current_t = start_time + timedelta(minutes=30 * i)
    time_options.append(current_t.strftime("%H:%M"))

selected_time = st.sidebar.selectbox("出発時刻", options=time_options, index=4)  # デフォルトは 07:00

# 交通機関情報(複数選択可)
transport_options = ["自動車", "バス", "電車", "飛行機"]
selected_transports = st.sidebar.multiselect("交通機関(複数選択可)", options=transport_options, default=["電車"])

# プラン
trip_plan = st.sidebar.text_input("プラン (日帰り6時間、1泊2日等)", value="日帰り")

# 目的地の実地/名称
destination = st.sidebar.text_input("目的地の場所/名称", placeholder="例:宿泊施設、レジャーランドなど")

# 寄り道/経由地
waypoints = st.sidebar.text_input("寄り道/経由地", placeholder="例:美術館、博物館など")

# 帰宅予定日
default_end_date = start_date
if "1泊2日" in trip_plan:
    try:
        default_end_date = start_date + timedelta(days=1)
    except Exception:
        pass
end_date = st.sidebar.date_input("帰宅予定日", value=default_end_date)

# 3. Groq API クライアント初期化
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    api_key = os.getenv("GROQ_API_KEY", "")

if not api_key:
    st.warning("Groq の API キーが設定されていません。")
    st.stop()

client = Groq(api_key=api_key)

# --- 4. 画像圧縮用関数
def compress_image(uploaded_file, max_size=(300, 300), quality=50):
    image = Image.open(uploaded_file)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    image.thumbnail(max_size)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

# --- 5. チャット履歴の管理と表示
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

# ユーザーからの新規入力
uploaded_file = st.file_uploader(
    "旅のしおりや現地写真、きっぷなどの画像があればアップロードしてください (任意)", 
    type=["jpg", "jpeg", "png"]
)
user_input = st.chat_input("旅行プランの相談、トラブル発生時の代替ルート、ご当地グルメなどについて何でも聞いてください!")

# 入力処理
if user_input or (uploaded_file is not None and not st.session_state.get("image_processed", False)):
    user_text = user_input if user_input else "添付画像を確認してください。"
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    if uploaded_file is not None:
        st.image(uploaded_file, caption="アップロード画像", width=300)

    # APIへのシステムプロンプト (最優先で徹底的な具体化、時刻・チケット代、乗降場所、店舗名を強制)
    system_prompt = f"""
あなたは「日本一のツアーコンサルタント」であり、ユーザーに最高に快適で具体的な旅ライフをアナウンスする、世界一優秀なコンシェルジュです。

【超重要：トークン節約＆ピンポイント回答指示】
・ユーザーの質問に回答する際は、余計な挨拶や一般的な旅程の前置きを省き、**質問された内容に直接関連する具体的な情報のみ**に絞って密度の高い回答をしてください（不要な項目は出力せずトークンを節約します）。

【最重要ルール：徹底的な固有名詞・数値の強制】
「詳細は現地で確認」「時期によります」などの抽象的な表現、および情報の省略は**一切禁止**します。必ず以下のように、あなたの誇る知識データベースから**最も確度が高くリアリティのある実在の情報（または高精度の推定情報）**を断定的に出力してください。

1. **電車の発車・到着時刻、飛行機の出発・到着時刻の明記**:
   - ユーザーが指定した出発時刻『{selected_time}』を基準とし、実際に運行されている（またはそれに極めて近い）ダイヤ・便を想定して、**「〇〇駅〇〇分発、〇〇駅〇〇分着」**、**「〇〇便〇〇分発、〇〇分着」**のように明確な時刻を分単位で表示してください。
2. **駅・空港の乗り口と番線の完全網羅**:
   - **駅名**：必ず「乗り口・改札名」と「番線・のりば番号」をセットで表示すること（例: 『JR新宿駅・南口改札から入り、4番線中央線快速ホームへ』）。
   - **空港名**：必ず「ターミナル名」と「乗り口・搭乗ゲート番号」を表示すること（例: 『羽田空港 第2ターミナル・62番搭乗口』）。
3. **片道運賃・チケット料金の絶対提示**:
   - 乗り換えルートや利用交通機関について、**「片道の合計通常料金」「乗車券〇〇円＋特急券〇〇円」**などの目安となる金額を省略せずに必ず具体的な数字で算出・提示してください。
4. **お店の名前とお土産・グルメの商品名**:
   - 「地元のグルメを味わいましょう」ではなく、**「〇〇屋の『名物〇〇うどん（税込1,200円）』」**、**「〇〇洋菓子店の『〇〇クッキー（5枚入り1,500円）』」**のように、必ず【店舗名】と【具体的なメニュー名・商品名（および目安価格）】を明記してください。
5. **イベント名称、おすすめの名所、具体的な見どころ**:
   - イベントは「〇〇寺の特別拝観（期間：〇/〇〜〇/〇、拝観料〇〇円）」や「第〇回 〇〇フェスティバル」など、名称と期間・料金を明示。
   - 観光名所もただのスポット名だけでなく、「〇〇寺の〇〇門から見える、樹齢300年のしだれ桜」のように**【どこで何を見るべきか（具体的な見どころ）】**まで情熱的に描写してください。

【超重要:キャラクターの完全憑依指示】
あなたの人格は完全に以下のキャラクターに上書きされています。上記の厳密な具体情報を、その性格、口調、口癖を文中にふんだんに取り入れて、旅が100倍楽しくなるように熱く、または優雅にアナウンスしてください。
キャラクター: {char_choice}
設定詳細:
{char_instructions}

【前提とする旅行情報】
- 出発地点: {departure if departure else '未定(最適な出発地を想定・提案してください)'}
- 出発日: {start_date}
- 出発指定時刻: {selected_time}
- 帰宅予定日: {end_date}
- 交通機関: {', '.join(selected_transports)}
- プラン: {trip_plan}
- 目的地: {destination if destination else '未定(提案を求めています)'}
- 寄り道/経由地: {waypoints if waypoints else '特になし'}
"""

    # ユーザーメッセージの構築
    user_content = []
    base_info = f"""
[現在の旅程・条件]
出発地点:{departure}
出発日:{start_date}
出発時刻:{selected_time}
帰宅日:{end_date}
移動手段: {', '.join(selected_transports)}
プラン: {trip_plan}
目的地:{destination}
経由地:{waypoints}
質問・状況:{user_text}
"""
    user_content.append({"type": "text", "text": base_info})

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
        with st.spinner("コンシェルジュが快適なプランを具体的に作成中..."):
            try:
                response = client.chat.completions.create(
                    model=TEXT_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.7,
                    max_tokens=1500
                )
                result_text = response.choices[0].message.content

                # キーワードの赤文字強調
                alert_keywords = ["大雨", "雷", "暴風", "台風", "積雪", "地震", "津波", "停電", "断水", "【緊急速報】"]
                formatted_text = result_text
                for kw in alert_keywords:
                    if kw in formatted_text:
                        formatted_text = formatted_text.replace(kw, f"<span style='color:red; font-weight:bold;'>{kw}</span>")

                st.divider()
                message_placeholder.markdown(formatted_text, unsafe_allow_html=True)

                # 履歴に追加
                st.session_state.messages.append({"role": "assistant", "content": result_text})

            except Exception as e:
                st.session_state.error_time = time.time()
                st.error(f"エラーが発生しました: {e}")
                st.info("API 負荷防止のため、30秒間ロックされます。")
                time.sleep(1)
                st.rerun()

st.markdown("### 旅の安全・防災ガイド")
st.warning("""
【重要】天災・ライフラインのトラブルについて
* 天候急変(大雨、落雷、暴風、積雪等)や、地震などの災害情報が発生した場合は、速やかにハザードマップを確認し、現地の避難誘導に従ってください。
* 各交通機関の正確なリアルタイム運行情報は、必ず運行会社公式ページや各自治体窓口の発表をご確認ください。
""")

st.warning("""
**ご利用時のパケット・通信料に関する注意点**
* ご利用に伴う通信料は全額自己負担となります。安定したWi-Fi環境等でのご利用を推奨します。
* 1GBあたり約5000回のチャットのやり取りが可能です。画像アップロードを伴う1回の実行で消費するパケットは約200KB/0.2円です。
""")
