"""
Twitter/X API integration module using tweepy.

Provides functions to post tweets, retrieve recent tweets,
and delete tweets via the Twitter API v2.
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tweepy

logger = logging.getLogger(__name__)


def get_twitter_client() -> tweepy.Client:
    """Create an authenticated tweepy Client using environment variables.

    Required env vars:
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
    """
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_SECRET")

    missing = []
    if not api_key:
        missing.append("TWITTER_API_KEY")
    if not api_secret:
        missing.append("TWITTER_API_SECRET")
    if not access_token:
        missing.append("TWITTER_ACCESS_TOKEN")
    if not access_secret:
        missing.append("TWITTER_ACCESS_SECRET")

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    logger.info("Twitter client created successfully")
    return client


def post_tweet(text: str) -> dict:
    """Post a new tweet.

    Args:
        text: The tweet content (max 280 characters).

    Returns:
        Dict with id, url, and text of the posted tweet.
    """
    try:
        client = get_twitter_client()
        response = client.create_tweet(text=text)

        tweet_id = response.data["id"]
        result = {
            "id": tweet_id,
            "url": f"https://x.com/i/status/{tweet_id}",
            "text": text,
        }

        logger.info("Tweet posted: %s", tweet_id)
        return result

    except tweepy.TweepyException as e:
        logger.error("Failed to post tweet: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error posting tweet: %s", e)
        raise


def get_recent_tweets(count: int = 5) -> list[dict]:
    """Get the authenticated user's recent tweets with engagement metrics.

    Args:
        count: Number of recent tweets to retrieve (max 100).

    Returns:
        List of dicts with id, text, created_at, and public_metrics
        (likes, retweets, replies, impressions).
    """
    try:
        client = get_twitter_client()

        # Get the authenticated user's ID
        me = client.get_me()
        if not me or not me.data:
            raise RuntimeError("Could not retrieve authenticated user info")

        user_id = me.data.id

        response = client.get_users_tweets(
            id=user_id,
            max_results=min(count, 100),
            tweet_fields=["created_at", "public_metrics", "text"],
        )

        results = []
        for tweet in response.data or []:
            metrics = tweet.public_metrics or {}
            results.append({
                "id": tweet.id,
                "text": tweet.text,
                "created_at": tweet.created_at.isoformat() if tweet.created_at else "",
                "public_metrics": {
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "impressions": metrics.get("impression_count", 0),
                },
            })

        logger.info("Retrieved %d recent tweets", len(results))
        return results

    except tweepy.TweepyException as e:
        logger.error("Failed to get recent tweets: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error getting recent tweets: %s", e)
        raise


def delete_tweet(tweet_id: str) -> bool:
    """Delete a tweet by its ID.

    Args:
        tweet_id: The ID of the tweet to delete.

    Returns:
        True if the tweet was deleted successfully.
    """
    try:
        client = get_twitter_client()
        response = client.delete_tweet(id=tweet_id)

        deleted = response.data.get("deleted", False) if response.data else False
        if deleted:
            logger.info("Tweet deleted: %s", tweet_id)
        else:
            logger.warning("Tweet deletion returned unexpected result for %s", tweet_id)

        return deleted

    except tweepy.TweepyException as e:
        logger.error("Failed to delete tweet %s: %s", tweet_id, e)
        raise
    except Exception as e:
        logger.error("Unexpected error deleting tweet %s: %s", tweet_id, e)
        raise
