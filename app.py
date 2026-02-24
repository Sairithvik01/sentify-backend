from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import re
import os
import logging

# --- Setup Production Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, template_folder='templates')
CORS(app)

# ==========================================
# 🔒 SECURITY: API KEY CONFIGURATION
# ==========================================
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# ==========================================
# ⚡ PERFORMANCE: PRE-COMPILED REGEX
# ==========================================
# Compiling this once at startup saves CPU cycles during the 1000-comment loop
TOKENIZER_REGEX = re.compile(r'[\s,.!?;:"()]+')

# ==========================================
# 🧠 LARGE MULTILINGUAL SENTIMENT DICTIONARY
# ==========================================
SENTIMENT_DICT = {
    "excited": ["excited","hyped","cant wait","can't wait","fire","lit","awesome","epic","legendary","goated","w","win","sheesh","insane","crazy good","maza aa gaya","badiya","zabardast","josh","mast hai","bahut accha","bahut badhiya","majedar","dhamaal","kirrak","keka","racha","mass","blockbuster","bagundi ra","super ra","chala bagundi","బాగుంది","సూపర్","అద్భుతం","vera level","semma","mass da","super da","அருமை","சூப்பர்","மாஸ்"],
    "happy": ["love","amazing","beautiful","great","fantastic","nice","wonderful","excellent","brilliant","cool","best","favourite","acha","accha","achha","khush","khushi","pyaar","bahut achha","sundar","mast","badhiya","अच्छा","खुश","सुंदर","bagundi","bagundhi","chala bagundi","santosham","happy ga","nachindi","బాగుంది","సంతోషం","నచ్చింది","nandri","romba nalla","nalla iruku","magizhchi","நல்லா இருக்கு","மகிழ்ச்சி"],
    "grateful": ["thank","thanks","thank you","thx","appreciate","grateful","respect","shukriya","dhanyavad","bohot shukriya","nandri","thanks anna","thanks bro","ధన్యవాదాలు","నன்றி"],
    "angry": ["hate","worst","stupid","idiot","trash","useless","disgusting","nonsense","fake","fraud","scam","terrible","bakwaas","ghatiya","bekaar","faltu","bewakoof","bakwas hai","gussa aa raha","बकवास","घटिया","बेकार","waste","daridram","bokka","rod","chee","chala worst","nachaledu","దారిద్రం","చీ","నచ్చలేదు","sollu","mokke","kevalam","kadupu","கேவலம்","மொக்கை"],
    "sad": ["sad","cry","crying","miss","heartbroken","pain","depressed","dukh","dard","dukhi","rona aa gaya","baadha","edupu","badha padutundi","kashtam","paavam","దుఃఖం","బాధ","கஷ்டம்"],
    "confused": ["confused","why","what","how","really","seriously","doubt","kya","kyun","kaise","samajh nahi aya","enti","enduku","ela","ardham kaledu","enna","epdi","puriyala","ఎంటి","ఎందుకు","புரியல"],
    "negative": ["bad","boring","slow","mid","average","problem","issue","bug","glitch","error","hard","lag","problem hai","issue hai","baledu","ledu","problem undi","seri illa","problem iruku","లేదు","இல்லை"]
}

NEGATIONS = ["not","no","never","dont","don't","didn't","isn't","nahi","mat","na","illa","illai","kadhu","ledu","oddu"]

def analyze_text_emotion(text):
    text = text.lower()
    for sentiment, keywords in SENTIMENT_DICT.items():
        for phrase in keywords:
            if " " in phrase and phrase in text:
                return {"emotion": sentiment, "score": 10}

    # Using the pre-compiled regex here
    tokens = TOKENIZER_REGEX.split(text)
    
    scores = {k: 0 for k in SENTIMENT_DICT.keys()}
    scores['positive'] = 0
    is_negated = False
    
    for token in tokens:
        if token in NEGATIONS:
            is_negated = True
            continue
        found = False
        for sentiment, keywords in SENTIMENT_DICT.items():
            if token in keywords:
                if is_negated:
                    if sentiment in ['happy', 'excited', 'grateful']: scores['negative'] += 2
                    else: scores['positive'] += 1
                else: scores[sentiment] += 2
                found = True
                break
        if found: is_negated = False

    max_score = 0
    winner = "neutral"
    priority = ['angry', 'excited', 'sad', 'grateful', 'happy', 'confused', 'negative', 'positive']
    for cat in priority:
        if cat in scores and scores[cat] > max_score:
            max_score = scores[cat]
            winner = cat
            
    return {"emotion": winner, "score": max_score}

# ==========================================
# 🚀 ROUTES
# ==========================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "online"}), 200

@app.route('/analyze/youtube', methods=['POST'])
def analyze_youtube_route():
    data = request.json
    video_url = data.get('url')
    client_page_token = data.get('pageToken')
    
    if not video_url:
        return jsonify({"error": "No URL provided"}), 400
    
    video_id = None
    if "v=" in video_url:
        video_id = video_url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in video_url:
        video_id = video_url.split("youtu.be/")[1].split("?")[0]
        
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400

    if not YOUTUBE_API_KEY:
        logging.error("YouTube API Key is missing!")
        return jsonify({"error": "API Key missing in Backend"}), 500

    logging.info(f"Analyzing video: {video_id} | PageToken: {client_page_token}")

    try:
        comments = []
        next_page_token = client_page_token
        max_total = 1000

        while len(comments) < max_total:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "key": YOUTUBE_API_KEY,
                "maxResults": 100,
                "textFormat": "plainText"
            }

            if next_page_token:
                params["pageToken"] = next_page_token

            res = requests.get("https://www.googleapis.com/youtube/v3/commentThreads", params=params)
            
            # --- Better API Error Handling ---
            if res.status_code != 200:
                error_msg = res.json().get('error', {}).get('message', 'Unknown YouTube API Error')
                logging.error(f"YouTube API Error: {error_msg}")
                
                # Check for specific known errors
                if "comments are disabled" in error_msg.lower():
                    return jsonify({"error": "Comments are disabled for this video."}), 403
                if "quota" in error_msg.lower():
                    return jsonify({"error": "YouTube API Daily Quota Exceeded."}), 429
                    
                return jsonify({"error": error_msg}), res.status_code

            res_json = res.json()
            items = res_json.get("items", [])
            
            for item in items:
                text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(text)

            next_page_token = res_json.get("nextPageToken")
            if not next_page_token:
                break # No more comments available

        # Slice to ensure we don't exceed the max_total if the last page pushed us slightly over
        comments = comments[:max_total]

        results = [
            {"id": i, "text": t, **analyze_text_emotion(t)}
            for i, t in enumerate(comments)
        ]

        logging.info(f"Successfully analyzed {len(results)} comments for {video_id}.")

        return jsonify({
            "results": results,
            "total_comments_analyzed": len(results),
            "source": f"YouTube: {video_id}",
            "nextPageToken": next_page_token
        })

    except Exception as e:
        logging.exception("An unexpected error occurred during analysis.")
        return jsonify({"error": "An internal server error occurred."}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
