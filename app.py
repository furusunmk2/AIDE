from flask import Flask, request, abort, jsonify
import random
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import patient 
from dotenv import load_dotenv
try:
    import google.generativeai as genai
    genai_available = True
except ImportError as e:
    print(f"Google Generative AI module not found: {e}")
    genai_available = False


# .env ファイルを読み込む
load_dotenv()

# 環境変数を取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if genai_available and GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        gemini_pro = genai.GenerativeModel("gemini-pro")
        print("Google Generative AI configured successfully.")
    except Exception as e:
        gemini_pro = None
        print(f"Failed to configure Google Generative AI: {e}")
else:
    gemini_pro = None


app = Flask(__name__)

# 環境変数からLINE APIの情報を取得
print(f"LINE_CHANNEL_ACCESS_TOKEN: {LINE_CHANNEL_ACCESS_TOKEN}")
print(f"LINE_CHANNEL_SECRET: {LINE_CHANNEL_SECRET}")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("環境変数 'LINE_CHANNEL_ACCESS_TOKEN' または 'LINE_CHANNEL_SECRET' が設定されていません")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    # X-Line-Signatureヘッダーを取得
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        abort(400, "X-Line-Signatureヘッダーが見つかりません")

    # リクエストボディを取得
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400, "不正な署名です")

    return 'OK'

# LINEメッセージイベントの処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    patient_num = event.message.text.strip()  # ユーザーの入力を取得
    response_text = ""

    if patient_num == "きずな":
        response_text = generate_patient_response(range(4))
    elif patient_num == "つなぐ":
        response_text = generate_patient_response(range(4, 8))
    elif patient_num == "all":
        response_text = generate_patient_response(range(8))
    else:
        matched = False
        for i in range(8):
            if patient.patient[i].startswith(patient_num):
                response_text = generate_patient_response([i])
                matched = True
                break
        if not matched:
            response_text = "該当するデータが見つかりません。"

    # ユーザーに返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_text)
    )

def generate_patient_response(indices):
    """
    指定されたインデックスの患者情報を生成して出力する関数
    """
    response_data = []
    for k in indices:
        patient_info = {"name": patient.patient[k], "data": []}
        prompt = f"""以下の文章をもとに看護記録を生成してください。
条件が３点あります。
- "【】"で囲まれた文は変更しないでください。
- その他の文は文意は変更せずに文章を変更してください。
- 200文字程度ごとに誤字を作ってください。

元の文章:
{patient.patient_data[k]}

生成した文章:
"""
        try:
            # Google Generative AIで応答を生成
            response = gemini_pro.generate_content(f"{prompt}")
            if response and response.candidates:
                # 最初の候補のテキスト部分を取得
                response_text = response.candidates[0]['content']
                patient_info["data"].append(response_text)
            else:
                patient_info["data"].append("AIからの応答が生成されませんでした。")
        except Exception as e:
            print(f"Error generating AI response for patient {k}: {e}")
            patient_info["data"].append(f"AI応答の生成中にエラーが発生しました: {str(e)}")
        
        # レスポンスデータに患者情報を追加
        response_data.append(f"{patient_info['name']}:\n{''.join(patient_info['data'])}")

    # 全患者の記録を結合して返す
    return "\n\n".join(response_data)



    
    

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
