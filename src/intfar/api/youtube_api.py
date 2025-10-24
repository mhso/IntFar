import httpx
from urllib.parse import quote_plus

NUM_SEARCH_RESULTS = 5
_API_SEARCH = "https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&key=[key]&q=[query]"

class YouTubeAPIClient:
    def __init__(self, config):
        self.config = config

    def query(self, term):
        api_endpoint = _API_SEARCH.replace("[key]", self.config.youtube_key).replace("[query]", quote_plus(term))
        response = httpx.get(api_endpoint)

        if response.status_code != 200:
            return False, "Something went wrong when trying to get search suggestions from YouTube :("
        
        try:
            results = response.json()["items"]
            results_output = []
            for result in results:
                title = result["snippet"]["title"]
                channel = result["snippet"]["channelTitle"]
                video_id = result["id"]["videoId"]
                url = f"https://youtube.com/watch?v={video_id}"
                results_output.append((title, channel, url))

            return True, results_output
        except Exception:
            return False, "Something went wrong when reading the response from YouTube :("
