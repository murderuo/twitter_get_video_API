from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import re
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Gerekirse spesifik originler
    # allow_credentials=False,
    # allow_origins=["chrome-extension://njkpjnkolglinkcgdjlhcpggbkedgbhc"],
    # allow_credentials=True,
    allow_methods=[""],
    allow_headers=["*"],
)

video_player_prefix = 'https://x.com/i/videos/tweet/'

class VideoRequest(BaseModel):
    tweetUrl: str

class VideoResponse(BaseModel):
    videoUrl: str | None

def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    return session

def __get_guest_token(req: requests.Session) -> str:
    res = req.post("https://api.x.com/1.1/guest/activate.json", timeout=10)
    res_json = res.json()
    token = res_json.get('guest_token', '')
    req.headers.update({'x-guest-token': token})
    return token

def __get_bearer_token(req: requests.Session, tweet_id: str) -> str:
    video_player_url = video_player_prefix + tweet_id
    response = req.get(video_player_url, timeout=10).text
    js_file_url_matches = re.findall(r'src="(.*js)', response)
    if not js_file_url_matches:
        return ''
    js_file_url = js_file_url_matches[0]
    js_file_response = req.get(js_file_url, timeout=10).text
    bearer_token_pattern = re.compile(r'Bearer ([a-zA-Z0-9%-]+)')
    match = bearer_token_pattern.search(js_file_response)
    if match:
        token = match.group(0)
        req.headers.update({'Authorization': token})
        return token
    return ''

def getvideo_url(tweet_url: str) -> str | None:
    session = create_session()
    __get_guest_token(session)

    # Tweet ID çıkarma
    tweet_url = tweet_url.split('?', 1)[0]
    segments = tweet_url.split('/')
    if len(segments) < 6:
        return None
    tweet_id = segments[5]

    try:
        __get_bearer_token(session, tweet_id)
        json_link = f"https://api.x.com/1.1/statuses/show/{tweet_id}.json?&tweet_mode=extended"
        resp = session.get(json_link, timeout=10).json()

        variants = resp["extended_entities"]["media"][0]["video_info"]["variants"]
        bitrate = 0
        chosen_video = ""
        for variant in variants:
            # m3u8 linkleri atla
            if variant.get('content_type') == "application/x-mpegURL":
                continue
            if variant.get('bitrate', 0) > bitrate:
                bitrate = variant['bitrate']
                chosen_video = variant["url"]
        if chosen_video:
            return chosen_video
    except Exception as e:
        print("Birincil yöntem başarısız oldu:", e)

    # Yedek yöntemler eklenebilir (örneğin getfvid kullanımı)
    return None

@app.post("/get_video_url", response_model=VideoResponse)
def api_get_video_url(request: VideoRequest):
    video_url = getvideo_url(request.tweetUrl)
    if video_url:
        return VideoResponse(videoUrl=video_url)
    else:
        raise HTTPException(status_code=404, detail="Video URL not found")

@app.get("/")
def home():
    return {"message": "FastAPI is running on Vercel."}

