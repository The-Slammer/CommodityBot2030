"""
youtube.py — Polls YouTube channels for new videos and fetches transcripts.
Only runs during each channel's configured posting window to conserve API quota.
"""

import json
import logging
import os
from datetime import datetime, timezone

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

from database import insert_youtube_item, is_video_seen, log_poll

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def _get_youtube_client():
    if not YOUTUBE_API_KEY:
        raise EnvironmentError("YOUTUBE_API_KEY not set")
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def _in_posting_window(post_window_utc: tuple[int, int]) -> bool:
    start_hour, end_hour = post_window_utc
    current_hour = datetime.now(timezone.utc).hour
    return start_hour <= current_hour <= (end_hour + 2)


def _fetch_recent_video_ids(youtube, channel_id: str, max_results: int = 5) -> list[dict]:
    request = youtube.search().list(
        part="id,snippet",
        channelId=channel_id,
        order="date",
        type="video",
        maxResults=max_results,
    )
    response = request.execute()
    return [
        {
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"],
        }
        for item in response.get("items", [])
    ]


def _fetch_transcript(video_id: str) -> str | None:
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        return " ".join(chunk["text"] for chunk in transcript_list)
    except (NoTranscriptFound, TranscriptsDisabled) as e:
        logger.warning("No transcript for %s: %s", video_id, e)
        return None
    except Exception as e:
        logger.error("Transcript fetch error for %s: %s", video_id, e)
        return None


def poll_channel(channel_config: dict):
    name = channel_config["name"]
    channel_id = channel_config["channel_id"]
    post_window = channel_config.get("post_window_utc", (0, 23))
    error = None
    items_found = 0
    items_new = 0

    if not _in_posting_window(post_window):
        logger.debug("Outside posting window for %s, skipping", name)
        return 0, 0

    try:
        logger.info("Polling YouTube channel: %s", name)
        youtube = _get_youtube_client()
        videos = _fetch_recent_video_ids(youtube, channel_id)
        items_found = len(videos)

        for video in videos:
            video_id = video["video_id"]

            if is_video_seen(video_id):
                continue

            logger.info("New video found: %s — fetching transcript", video["title"][:60])
            transcript_raw = _fetch_transcript(video_id)

            insert_youtube_item({
                "source_name": name,
                "channel_id": channel_id,
                "source_type": channel_config["source_type"],
                "credibility_tier": channel_config["credibility_tier"],
                "video_id": video_id,
                "title": video["title"],
                "published_at": video["published_at"],
                "transcript_raw": transcript_raw,
                "transcript_summary": None,
                "topics": json.dumps(channel_config.get("topics", [])),
                "ingested_at": datetime.utcnow().isoformat(),
            })
            items_new += 1

    except Exception as e:
        error = str(e)
        logger.error("Error polling channel %s: %s", name, e)

    finally:
        log_poll(name, "youtube", items_found, items_new, error)

    return items_found, items_new


def poll_all_channels(channels: list[dict]):
    total_found = 0
    total_new = 0
    for channel in channels:
        found, new = poll_channel(channel)
        total_found += found
        total_new += new
    logger.info("YouTube cycle complete — %d found, %d new", total_found, total_new)
