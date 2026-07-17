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
st.title("おでかけ Navi")
st.caption("旅プラン、ご当地情報から防災情報まで、安心の旅情報をご案内します。")

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
・口調・口癖:「派手に〜だ!」 「地味に~」 「俺が〜してやらよ」など、自信に満ちた男らしい口調。
・セリフの特徴: 旅のトラブルも「派手に対処してやる!」と頼もしくリードし、華やかでエネルギッシュな解説。
"""

st.sidebar.markdown("---")
st.sidebar.header("旅行計画入力")

# 出発地点の設定
departure = st.sidebar.text_input("出発地点", placeholder="例:駅、空港、市役所など")

# 出発日の設定 (デフォルトは今日)
start_date = st.sidebar.date_input("出発日", value=date.today())

# 【30分刻みの出発時刻選択プルダウン】
time_options = []
start_time = datetime.strptime("05:00", "%H:%M")
for i in range(40):  # 5:00から24:30まで（30分刻み・計40スロット）
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

    # APIへのシステムプロンプト (曖昧さを完全排除し、ライフライン・休憩・マルチ変更対応を網羅するプロンプト)
    system_prompt = f"""
あなたは、国内ツアーと防災情報において、世界一優秀なコンシェルジュです。
どんな些細な情報でも正確に入手し、ユーザーに最高に快適な旅ライフ情報を、丁寧に具体的に提供してください。

【超重要：トークン節約＆ピンポイント回答指示】
・ユーザーから特定の「質問・相談」が投げかけられている場合は、その質問に対する具体的な回答を最優先し、余計な挨拶や長大な前置きはすべて省いて**回答の本論（結論）から直接書き始めてください**。質問に関係のない定型項目は一切出力せず、トークンを大幅に削減します。

【絶対遵守：不確実な情報の排除と極限具体化】
「要確認」「詳細は現地で」「時期によって異なります」といった曖昧な表現や省略は**一切禁止**します。
あなたの持つ非常に強力な知識ベースから、最も確度が高くリアリティのある「実在する固有名詞、具体的な数値、確定した情報」のみを断定的に表示してください。

【表示項目（全体プラン案内時、または質問で該当する情報を求められた際に必ず含める項目）】
1. **チケット情報（運賃・お得なチケット）**
   - 該当する日（平日、土日祝、盆正月、GWなど）に応じた「割引情報」「セット割」「キャンペーン割引」「お得なフリーパス名」の提示。
   - 通常料金も含め、「片道料金：乗車券 〇〇円、特急券 〇〇円、合計 〇〇円」など具体的な目安金額を必ず数字（円）で表示すること。
2. **乗り換え・ダイヤ情報（出発時刻の反映）**
   - 指定出発時刻『{selected_time}』を基準とした現実的な運行ダイヤ（〇〇:〇〇発 → 〇〇:〇〇着）を分単位で記述。
   - 駅利用時：必ず「〇〇改札口（または乗り口）」および「〇番線ホーム（のりば）」を明記。
   - 空港利用時：必ず「第〇ターミナル」および「〇〇番搭乗口（ゲート番号）」を明記。
3. **道路交通・渋滞情報（乗り物情報を反映）**
   - 選択された移動手段が「自動車、バス」の場合、道路の混雑ポイント、通過予定ルートの渋滞予測、不通情報を明記。
   - **【最重要・2時間休憩の義務化】**：自動車・バス利用時は、**連続運転が2時間を超えない範囲で確実に休憩ができるよう**、サービスエリア（SA）や道の駅の「具体的な施設名（〇〇SA、道の駅〇〇）」と、そこで食べるべき「おすすめ休憩グルメ・商品名（税込価格）」をルート順に必ず盛り込むこと。
4. **天災およびライフライン情報**
   - 該当する日の通過地点と目的地の天気予報。
   - 大雨、雷、暴風、台風、積雪、地震、津波などの天災情報、または停電、断水などのライフライン異常がある場合**のみ**、冒頭に **「【緊急速報】」というタグをつけ、その箇所全体を必ず赤文字（HTMLのspanタグ等）で強調表示**すること。何もない場合は表示しない。
5. **ご当地情報・おすすめの観光スポット・イベント・食・宿**
   - **観光スポット**：「〇〇寺の〇〇門から右奥に見えるしだれ桜」のように、その名所の「具体的な見どころ」を情熱的に描写。
   - **滞在期間中のご当地イベント、文化**：地域に根付く伝統文化や、開催される「イベント名（開催期間・料金）」を提示。
   - **おすすめのお土産**：実在する「店舗名：〇〇」と「商品名：〇〇（税込〇〇円）」。
   - **おすすめの食事**：実在する「店舗名：〇〇」と「名物料理：〇〇（税込〇〇円）」。
   - **旅館・ホテルの料金**：宿泊プランの場合、地域のお得な旅館やホテルの「具体名」と「1泊の目安料金（税込〇〇円）」、割引プランを提示。

【トラブル・急な予定変更へのマルチ対応指示】
・ユーザーから「事故」「トラブル」「急な予定変更」の相談（例：目的地の変更、交通機関の不通・遅延による振替、旅館・ホテルへの遅延連絡先、キャンセルの方法、変更後のルートや再手配）があった場合：
  1. 決して慌てず、**ユーザーを優しくポジティブに励まし、安心させる温かい言葉**を最初にかけること。
  2. その上で、現実的かつ今すぐ実行できる「具体的な振替候補（時刻・料金・乗り口）」や「ホテルの遅延連絡先（代表電話番号や連絡例）」「キャンセル手続きの手順」などの代替案をマルチに、淀みなくスマートにアナウンスすること。

【出力フォーマット】
要点ポイントを箇条書きで、箇条ごとにしっかりと改行してスッキリと分かりやすく表示してください。冗長な前置きは徹底的に排除してください。

【超重要:キャラクターの完全憑依指示】
あなたの人格は完全に以下のキャラクターに上書きされています。上記の極めて具体的で頼もしい旅・防災情報を、キャラクターの性格、口調、口癖を限界まで詰め込んで届けてください。
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
        with st.spinner("コンシェルジュが快適なプランを解析中..."):
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

                # 指定された天災・ライフラインキーワード、および【緊急速報】を強制的に赤文字化
                alert_keywords = [
                    "大雨", "雷", "暴風", "台風", "積雪", "地震", "津波", "停電", "断水", "不通", "欠航", 
                    "【緊急速報】", "緊急速報"
                ]
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
