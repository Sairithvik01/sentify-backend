from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import re
import os

app = Flask(__name__, template_folder='templates')
CORS(app)

# ==========================================
# 🔒 SECURITY: API KEY CONFIGURATION
# ==========================================
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# ==========================================
# 🧠 DICTIONARY (Gen-Z, Hindi, Telugu)
# ==========================================
# ==========================================
# 🧠 LARGE MULTILINGUAL SENTIMENT DICTIONARY
# ==========================================

SENTIMENT_DICT = {

    # 🔥 EXCITED / HYPE
    "excited": [
        # English
        "excited","hyped","cant wait","can't wait","fire","lit","awesome","epic",
        "legendary","goated","w","win","sheesh","insane","crazy good",
        
        # Hindi
        "maza aa gaya","badiya","zabardast","josh","mast hai","bahut accha",
        "bahut badhiya","majedar","dhamaal",
        
        # Telugu
        "kirrak","keka","racha","mass","blockbuster",
        "bagundi ra","super ra","chala bagundi",
        "బాగుంది","సూపర్","అద్భుతం",
        
        # Tamil
        "vera level","semma","mass da","super da",
        "அருமை","சூப்பர்","மாஸ்"
    ],

    # 😊 HAPPY / POSITIVE
    "happy": [
        # English
        "love","amazing","beautiful","great","fantastic","nice","wonderful",
        "excellent","brilliant","cool","best","favourite",
        
        # Hindi
        "acha","accha","achha","khush","khushi","pyaar",
        "bahut achha","sundar","mast","badhiya",
        "अच्छा","खुश","सुंदर",
        
        # Telugu
        "bagundi","bagundhi","chala bagundi",
        "santosham","happy ga","nachindi",
        "బాగుంది","సంతోషం","నచ్చింది",
        
        # Tamil
        "nandri","romba nalla","nalla iruku","magizhchi",
        "நல்லா இருக்கு","மகிழ்ச்சி"
    ],

    # 🙏 GRATEFUL
    "grateful": [
        "thank","thanks","thank you","thx","appreciate","grateful","respect",
        "shukriya","dhanyavad","bohot shukriya",
        "nandri","thanks anna","thanks bro",
        "ధన్యవాదాలు","నன்றி"
    ],

    # 😡 ANGRY
    "angry": [
        # English
        "hate","worst","stupid","idiot","trash","useless","disgusting",
        "nonsense","fake","fraud","scam","terrible",
        
        # Hindi
        "bakwaas","ghatiya","bekaar","faltu","bewakoof",
        "bakwas hai","gussa aa raha",
        "बकवास","घटिया","बेकार",
        
        # Telugu
        "waste","daridram","bokka","rod","chee",
        "chala worst","nachaledu",
        "దారిద్రం","చీ","నచ్చలేదు",
        
        # Tamil
        "sollu","mokke","kevalam","kadupu",
        "கேவலம்","மொக்கை"
    ],

    # 😢 SAD
    "sad": [
        "sad","cry","crying","miss","heartbroken","pain","depressed",
        "dukh","dard","dukhi","rona aa gaya",
        "baadha","edupu","badha padutundi",
        "kashtam","paavam",
        "దుఃఖం","బాధ","கஷ்டம்"
    ],

    # 🤔 CONFUSED
    "confused": [
        "confused","why","what","how","really","seriously","doubt",
        "kya","kyun","kaise","samajh nahi aya",
        "enti","enduku","ela","ardham kaledu",
        "enna","epdi","puriyala",
        "ఎంటి","ఎందుకు","புரியல"
    ],

    # 👎 NEGATIVE GENERAL
    "negative": [
        "bad","boring","slow","mid","average","problem","issue",
        "bug","glitch","error","hard","lag",
        "problem hai","issue hai",
        "baledu","ledu","problem undi",
        "seri illa","problem iruku",
        "లేదు","இல்லை"
    ]
}

NEGATIONS = [
    "not","no","never","dont","don't","didn't","isn't",
    "nahi","mat","na","illa","illai",
    "kadhu","ledu","oddu"
]


def analyze_text_emotion(text):
    text = text.lower()
    for sentiment, keywords in SENTIMENT_DICT.items():
        for phrase in keywords:
            if " " in phrase and phrase in text:
                return {"emotion": sentiment, "score": 10}

    tokens = re.split(r'[\s,.!?;:"()]+', text)
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
    return "Sentify API is Online and Running!"

# New Route: Checks if server is Online
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "online"}), 200

@app.route('/analyze/text', methods=['POST'])
def analyze_text_route():
    data = request.json
    comments = data.get('comments', [])
    results = [
        {"id": i, "text": t, **analyze_text_emotion(t)} 
        for i, t in enumerate(comments) if t and isinstance(t, str)
    ]
    return jsonify({"results": results})

@app.route('/analyze/youtube', methods=['POST'])
def analyze_youtube_route():
    data = request.json
    video_url = data.get('url')
    page_token = data.get('pageToken') # 🆕 Check if frontend sent a token
    
    if not video_url:
        return jsonify({"error": "No URL provided"}), 400
    
    video_id = None
    if "v=" in video_url:
        video_id = video_url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in video_url:
        video_id = video_url.split("youtu.be/")[1].split("?")[0]
        
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400

    if YOUTUBE_API_KEY == "YOUTUBE_API_KEY":
        return jsonify({"error": "API Key missing in Backend"}), 500

    try:
        comments = []
        next_page_token = page_token # 🆕 Start from where we left off
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

            res = requests.get(
                "https://www.googleapis.com/youtube/v3/commentThreads",
                params=params
            )
            res_json = res.json()

            if "error" in res_json:
                return jsonify({"error": res_json['error']['message']}), 400

            items = res_json.get("items", [])
            for item in items:
                text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(text)

            next_page_token = res_json.get("nextPageToken")
            if not next_page_token:
                break # 🆕 Break if there are no more comments left on the video

        results = [
            {"id": i, "text": t, **analyze_text_emotion(t)}
            for i, t in enumerate(comments)
        ]

        return jsonify({
            "results": results,
            "total_comments_analyzed": len(results),
            "source": f"YouTube: {video_id}",
            "nextPageToken": next_page_token # 🆕 Send the bookmark back to the frontend
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    import os
    # Get port from environment variable, or default to 5000 for local dev
    port = int(os.environ.get("PORT", 5000))
    # Must bind to 0.0.0.0 to be accessible externally on Render
    app.run(host='0.0.0.0', port=port)

#Command to install dependencies:
    """pip install flask flask-cors requests"""
# To run the server:
    """python app.py"""


