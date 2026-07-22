import streamlit as st
import os
from openai import OpenAI  # OpenAI互換ライブラリの利用
from PIL import Image
import io
import time
import base64

# --- 1. 画面初期設定 ---
st.set_page_config(page_title="econavi-neo", layout="wide")

# --- メイン画面の表示 ---
st.title("Econavi - neo")
st.caption("事業系廃棄物分別ナビ ※写真と文字から簡単に調べられます。")

# --- 使用する Llama ビジョンモデルの設定 ---
# ※Groqを利用する場合は "llama-3.2-11b-vision-preview" などを指定
VISION_MODEL = "llama-3.2-11b-vision-preview"

# --- 2. サイドバー設定 ---
st.sidebar.header(" 地域設定")
prefecture = st.sidebar.text_input("都道府県を入力してください", value="千葉県")
city = st.sidebar.text_input("市区町村を入力してください", value="市原市")

# キャラクター設定用のプルダウン
st.sidebar.header(" 案内役設定")
char_choice = st.sidebar.selectbox(
    "解説を頼む案内役を選んでください",
    ["女性", "男性", "煉獄杏寿郎"]
)

# キャラクターのプロンプト指示
char_instructions = ""
if char_choice == "女性":
    char_instructions = "明るい女性アナウンサーのテレビ口調。「とっておきの情報なの」「〜わぁ！」「〜もの！」「〜ですね！」を文頭や文末に自然に使い、明るくエスコートします。"
elif char_choice == "男性":
    char_instructions = "元気な男性キャスターの口調。「ビックリです！」「これは凄い！」「なるほどですね！」を使い、臨場感のある生中継風に解説します。"
elif char_choice == "煉獄杏寿郎":
    char_instructions = "鬼滅の刃の煉獄杏寿郎の熱い口調。「〜だ！」「うむ！」「心を燃やせ！」「実に見事な分別だ！」を使い、すべての文末に「！」をつけます。"

# --- 3. OpenAI 互換 API クライアント初期化 ---
if "LLAMA_API_KEY" in st.secrets:
    api_key = st.secrets["LLAMA_API_KEY"]
else:
    api_key = os.getenv("LLAMA_API_KEY", "")

# ご利用のプロバイダに合わせてBASE URLを設定（例: Groqの場合は https://groq.com）
base_url = os.getenv("LLAMA_API_BASE_URL", "https://groq.com")

if not api_key:
    st.warning("Llama 用の API キーが設定されていません。")
    st.stop()

# OpenAI互換クライアントとしてインスタンス生成
client = OpenAI(api_key=api_key, base_url=base_url)

# --- 4. 画像圧縮＆Base64エンコード用関数 ---
def compress_image_to_base64(uploaded_file, max_size=(300, 300), quality=50):
    image = Image.open(uploaded_file)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    image.thumbnail(max_size)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    # 互換APIの仕様に合わせてBase64文字列に変換
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

# --- 5. メイン機能：ファイルアップロード & 文字入力 ---
uploaded_file = st.file_uploader("廃棄物の画像をアップロードしてください", type=["jpg", "jpeg", "png"])
if uploaded_file is not None:
    st.image(uploaded_file, caption="アップロードされた画像", width=300)

text_query = st.text_input("廃棄物の名前や状態を文字で入力してください", placeholder="例：割れた蛍光灯、使い切ったスプレー缶")

# 入力チェック
is_input_provided = (uploaded_file is not None) or (text_query.strip() != "")

# 【状態管理】冷却期間
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

is_button_disabled = not is_input_provided or is_cooling_down

# ボタン押下時の処理
if st.button("この廃棄物を判別する", type="primary", disabled=is_button_disabled):
    with st.spinner("データを解析中..."):
        try:
            # システムプロンプトの設定
            system_prompt = f"""あなたは、{prefecture}{city}の事業系廃棄物（事業系一般廃棄物・産業廃棄物）の分別に精通した専門コンシェルジュです。
ユーザーが入力した廃棄物について、{prefecture}{city}の公式ルールと法令に厳格に則り、以下の 4 つの見出しに沿って「最後まで絶対に省略せず」書ききってください。

【超重要：キャラクター設定】
以下の設定になりきり、各見出しの直後には必ず 1 行、キャラクターらしいセリフや挨拶を入れてから箇条書きを始めてください。
キャラクター：{char_choice}
設定：{char_instructions}

【処理条件】
1. 業者の名前や行政の電話番号などの具体的な「連絡先」は、いかなる場合も絶対に表示しないでください。
2. 判断に迷う表現や回収を促す文脈では、必ず「判断に迷う場合：環境安全担当部署に相談して下さい。」と一言一句違わずに表示してください。
3. 法的区分（産業廃棄物か事業系一般廃棄物か）を明快に整理して解説してください。

【出力フォーマット（厳守）】
以下の見出しを必ずすべて含めて出力してください。
【対象物】
（キャラクターのセリフ 1 行）
・（廃棄物の名前や状態についての箇条書き）
【分別方法】
（キャラクターのセリフ 1 行）
・（法律上の区分や、割れ物である場合の安全な排出・分別手順の箇条書き）
【自治体の受入可否】
（キャラクターのセリフ 1 行）
・（自治体の福増クリーンセンター等で受入が可能か、あるいは産業廃棄物として業者委託が必要かの箇条書き）
【保管方法】
（キャラクターのセリフ 1 行）
・（収集を待つ間、社内で安全に保管（キケン表示など）するための手順の箇条書き）"""

            # ユーザーメッセージの構築
            user_content = []
            
            # 画像がある場合はBase64形式のURLデータとしてペイロードに追加
            if uploaded_file is not None:
                base64_image = compress_image_to_base64(uploaded_file)
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
            
            # テキスト指示の追加
            user_text = f"対象物: {text_query.strip()}\n"
            user_text += f"質問: {prefecture}{city}におけるこの廃棄物の正しい法的分別（事業系一般廃棄物か産業廃棄物か）と安全な処理方法を、指定フォーマットの 4 つの見出しすべてを使って最後まで省略せずに答えてください。"
            user_content.append({
                "type": "text",
                "text": user_text
            })

            # OpenAI互換チャットリクエストの実行
            response = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.2,
            )
            
            # 結果の表示
            result_text = response.choices[0].message.content
            if result_text:
                st.success("解析が完了しました。")
                st.markdown(result_text)
            else:
                st.error("API から応答がありませんでした。再度お試しください。")
                
        except Exception as e:
            st.session_state.error_time = time.time()
            st.error(f"エラーが発生しました: {e}")
            st.info("API 負荷防止のため、30 秒間ロックされます。")
            st.rerun()

st.divider()
st.markdown("### 問い合わせ先")
st.warning("""**下記内容については、必ず、環境安全担当部署にご相談下さい。** 
* 回収業者、産業廃棄物業者への委託
* 行政窓口への連絡、特殊な廃棄物処理
* その他、社内規程に関する問い合わせ""")
st.warning("""**【重要】情報漏洩防止のための確認お願い**
* 写真には、法人名、設備、製品名、個人情報、社外秘など、秘密情報が写り込んでいないことを、送信前に必ずご確認ください。
* テキスト入力欄についても、上記同様に、秘密情報が入力されていないことを、送信前に必ずご確認ください。""")
st.warning("""**ご利用時の注意点** 
* ご利用に伴うインターネット回線代や通信料等の通信費につきましては、原則として全額自己負担となります。
* モバイル Wi-Fi 等の通信環境がご利用可能な場合は、Wi-Fi 通信環境でのご利用を推奨します。
* 画像アップロードを伴う 1 回の実行に消費するパケット消費＝約 100KB〜200KB(0.0001GB〜0.0002GB) ※参考値""")
