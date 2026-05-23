"""
AgentSystem — X/Twitter Tools (xurl-based).

Wraps the official xurl CLI for comprehensive X API access.
Falls back to tweepy for operations xurl doesn't support directly.
All functions return structured dicts.

Requires xurl CLI installed and OAuth 2.0 configured (or OAuth 1.0a env vars).
Env vars: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)

# ── Credential detection ──────────────────────────────────────────────────

def _has_oauth1_creds() -> bool:
    """Check if OAuth 1.0a env vars are available (for fallback)."""
    return all(
        os.environ.get(v)
        for v in ["TWITTER_API_KEY", "TWITTER_API_SECRET",
                   "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"]
    )

def _has_xurl_oauth2() -> bool:
    """Check if xurl has OAuth 2.0 tokens configured."""
    try:
        result = subprocess.run(
            ["xurl", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        return "oauth2:" in result.stdout and "(none)" not in result.stdout
    except Exception:
        return False

def _xurl_available() -> bool:
    """Check if xurl CLI is installed and has auth configured."""
    try:
        result = subprocess.run(
            ["xurl", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        # xurl is available if it returns without "command not found" error
        return result.returncode == 0 and "No apps registered" not in result.stderr
    except FileNotFoundError:
        return False
    except Exception:
        return False

def _find_xurl_cmd() -> Optional[str]:
    """Find the xurl CLI binary in common install locations.
    
    Returns the full path, or None if not found.
    """
    import shutil
    # Check common locations
    candidates = [
        "xurl",                                    # PATH
        os.path.expanduser("~/.local/bin/xurl"),   # install.sh default
        "/usr/local/bin/xurl",                     # system-wide
        "/root/.local/bin/xurl",                   # Docker root
    ]
    for path in candidates:
        if shutil.which(path):
            return path
    # Last resort: check if xurl exists anywhere in PATH
    found = shutil.which("xurl")
    return found

# ── xurl CLI wrapper ──────────────────────────────────────────────────────

def _run_xurl(args: list[str], timeout: int = 30) -> dict:
    """Run xurl command and return parsed JSON result."""
    xurl_path = _find_xurl_cmd()
    if not xurl_path:
        return {"error": "xurl CLI not installed. Run: curl -fsSL https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash"}

    try:
        result = subprocess.run(
            [xurl_path] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.error("xurl command failed: %s — %s", " ".join(args), error_msg)
            return {"error": error_msg, "exit_code": result.returncode}

        stdout = result.stdout.strip()
        if not stdout:
            return {"error": "Empty response from xurl", "exit_code": result.returncode}

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            # Some xurl commands return plain text
            return {"text": stdout}
    except subprocess.TimeoutExpired:
        logger.error("xurl command timed out: %s", " ".join(args))
        return {"error": "Request timed out"}
    except FileNotFoundError:
        return {"error": "xurl CLI not installed. Run: curl -fsSL https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash"}
    except Exception as e:
        logger.error("xurl command exception: %s", e)
        return {"error": str(e)}

# ── Public API ────────────────────────────────────────────────────────────

def post_tweet(text: str, media_ids: Optional[list[str]] = None) -> dict:
    """Post a new tweet. Optionally attach media.

    Tries in order: x-cli subprocess → xurl CLI → direct OAuth 1.0a v1.1 → tweepy v2.
    Args:
        text: The tweet content (max 280 characters).
        media_ids: Optional list of media IDs to attach.

    Returns:
        Dict with id, url, and text of the posted tweet.
    """
    # Path 1: x-cli (confirmed working with OAuth 1.0a on Free tier)
    result = _post_via_xcli(text)
    if "error" not in result and result.get("id"):
        return result

    # Path 2: xurl CLI (OAuth 2.0, needs token config)
    args = ["post", text]
    if media_ids:
        for mid in media_ids:
            args.extend(["--media-id", mid])

    xurl_result = _run_xurl(args)
    if "error" not in xurl_result:
        data = xurl_result.get("data", {})
        return {
            "id": data.get("id", ""),
            "url": f"https://x.com/i/status/{data.get('id', '')}",
            "text": data.get("text", text),
        }

    # Path 3: Direct OAuth 1.0a v1.1 (bypass tweepy v2 auth issues)
    result = _post_via_oauth1(text)
    if "error" not in result and result.get("id"):
        return result

    # Path 4: tweepy v2 (last resort)
    return _tweepy_post_tweet(text)


def _find_xcli_cmd() -> Optional[str]:
    """Find x-cli binary in common locations."""
    import shutil
    candidates = [
        "x-cli",
        os.path.expanduser("~/.local/bin/x-cli"),
        "/usr/local/bin/x-cli",
    ]
    for path in candidates:
        if shutil.which(path):
            return path
    return shutil.which("x-cli")


def _post_via_xcli(text: str) -> dict:
    """Post via x-cli subprocess (OAuth 1.0a, confirmed working on Free tier)."""
    xcli_path = _find_xcli_cmd()
    if not xcli_path:
        return {"error": "x-cli not installed"}

    try:
        result = subprocess.run(
            [xcli_path, "-j", "tweet", "post", text],
            capture_output=True, text=True, timeout=30,
            env={**os.environ},  # inherit X_* env vars
        )
        if result.returncode != 0:
            return {"error": f"x-cli exit {result.returncode}: {result.stderr.strip()[:200]}"}

        data = json.loads(result.stdout)
        tweet_id = data.get("id", data.get("data", {}).get("id", ""))
        if tweet_id:
            return {
                "id": tweet_id,
                "url": f"https://x.com/i/status/{tweet_id}",
                "text": text,
            }
        return {"error": "x-cli returned no tweet ID"}

    except FileNotFoundError:
        return {"error": "x-cli not installed"}
    except json.JSONDecodeError as e:
        return {"error": f"x-cli parse error: {e}"}
    except Exception as e:
        return {"error": f"x-cli exception: {e}"}


def _post_via_oauth1(text: str) -> dict:
    """Post via direct OAuth 1.0a v1.1 API (requests_oauthlib).
    
    Hits POST https://api.x.com/1.1/statuses/update.json
    — the same endpoint x-cli uses. Confirmed working on Free tier.
    """
    try:
        from requests_oauthlib import OAuth1Session

        api_key = os.environ.get("TWITTER_API_KEY", "")
        api_secret = os.environ.get("TWITTER_API_SECRET", "")
        access_token = os.environ.get("TWITTER_ACCESS_TOKEN", "")
        access_secret = os.environ.get("TWITTER_ACCESS_SECRET", "")

        if not all([api_key, api_secret, access_token, access_secret]):
            return {"error": "Missing OAuth 1.0a credentials (TWITTER_* env vars)"}

        oauth = OAuth1Session(
            api_key,
            client_secret=api_secret,
            resource_owner_key=access_token,
            resource_owner_secret=access_secret,
        )

        resp = oauth.post(
            "https://api.x.com/1.1/statuses/update.json",
            data={"status": text},
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            tweet_id = data.get("id_str", data.get("id", ""))
            return {
                "id": str(tweet_id),
                "url": f"https://x.com/i/status/{tweet_id}",
                "text": text,
            }
        else:
            return {"error": f"X API v1.1 returned HTTP {resp.status_code}: {resp.text[:300]}"}

    except ImportError:
        return {"error": "requests_oauthlib not available"}
    except Exception as e:
        return {"error": f"OAuth 1.0a post exception: {e}"}


def _tweepy_post_tweet(text: str) -> dict:
    """Fallback: post via tweepy."""
    try:
        from tools.twitter_tools import post_tweet as tweepy_post
        return tweepy_post(text)
    except Exception as e:
        return {"error": f"Failed to post tweet (xurl + tweepy): {e}"}


def search_tweets(query: str, max_results: int = 10) -> dict:
    """Search recent tweets.

    Args:
        query: Search query (supports X search operators).
        max_results: Maximum number of results (default 10, max 100).

    Returns:
        Dict with 'tweets' list containing id, text, author, created_at.
    """
    result = _run_xurl(["search", query, "-n", str(max_results)])
    if "error" in result:
        return _tweepy_search_tweets(query, max_results)

    data = result.get("data", [])
    if isinstance(data, dict):
        data = [data]

    tweets = []
    for t in data:
        tweets.append({
            "id": t.get("id", ""),
            "text": t.get("text", ""),
            "author": t.get("author_id", ""),
            "created_at": t.get("created_at", ""),
        })

    return {"tweets": tweets, "count": len(tweets), "meta": result.get("meta", {})}


def _tweepy_search_tweets(query: str, max_results: int = 10) -> dict:
    """Fallback: search via tweepy."""
    try:
        from tools.twitter_tools import get_twitter_client
        client = get_twitter_client()
        response = client.search_recent_tweets(
            query=query,
            max_results=min(max_results, 100),
            tweet_fields=["created_at", "author_id"],
        )
        tweets = []
        for t in response.data or []:
            tweets.append({
                "id": str(t.id),
                "text": t.text,
                "author": t.author_id or "",
                "created_at": str(t.created_at) if t.created_at else "",
            })
        return {"tweets": tweets, "count": len(tweets), "meta": response.meta or {}}
    except Exception as e:
        return {"error": f"search failed (xurl + tweepy): {e}"}


def get_timeline(count: int = 20) -> dict:
    """Get the authenticated user's home timeline.

    Args:
        count: Number of tweets to retrieve (max 100).

    Returns:
        Dict with 'tweets' list.
    """
    result = _run_xurl(["timeline", "-n", str(count)])
    if "error" in result:
        return _tweepy_timeline(count)

    data = result.get("data", [])
    if isinstance(data, dict):
        data = [data]

    tweets = []
    for t in data:
        tweets.append({
            "id": t.get("id", ""),
            "text": t.get("text", ""),
            "author_id": t.get("author_id", ""),
            "created_at": t.get("created_at", ""),
        })

    return {"tweets": tweets, "count": len(tweets)}


def _tweepy_timeline(count: int = 20) -> dict:
    """Fallback: timeline via tweepy (reverse chronological)."""
    try:
        from tools.twitter_tools import get_twitter_client
        client = get_twitter_client()
        me = client.get_me()
        if not me or not me.data:
            return {"error": "tweepy could not get authenticated user"}
        response = client.get_users_tweets(
            id=me.data.id,
            max_results=min(count, 100),
            tweet_fields=["created_at", "author_id"],
        )
        tweets = []
        for t in response.data or []:
            tweets.append({
                "id": str(t.id),
                "text": t.text,
                "author_id": t.author_id or "",
                "created_at": str(t.created_at) if t.created_at else "",
            })
        return {"tweets": tweets, "count": len(tweets)}
    except Exception as e:
        return {"error": f"timeline failed (xurl + tweepy): {e}"}


def get_mentions(count: int = 20) -> dict:
    """Get recent mentions of the authenticated user.

    Args:
        count: Number of mentions to retrieve (max 100).

    Returns:
        Dict with 'mentions' list.
    """
    result = _run_xurl(["mentions", "-n", str(count)])
    if "error" in result:
        return result

    data = result.get("data", [])
    if isinstance(data, dict):
        data = [data]

    mentions = []
    for t in data:
        mentions.append({
            "id": t.get("id", ""),
            "text": t.get("text", ""),
            "author_id": t.get("author_id", ""),
            "created_at": t.get("created_at", ""),
        })

    return {"mentions": mentions, "count": len(mentions)}


def get_user(username: str) -> dict:
    """Look up a user by username/handle.

    Args:
        username: The X handle (with or without @).

    Returns:
        Dict with user profile data.
    """
    username = username.lstrip("@")
    result = _run_xurl(["user", username])

    if "error" in result:
        return result

    data = result.get("data", {})
    return {
        "id": data.get("id", ""),
        "username": data.get("username", username),
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "followers_count": data.get("public_metrics", {}).get("followers_count", 0),
        "following_count": data.get("public_metrics", {}).get("following_count", 0),
        "tweet_count": data.get("public_metrics", {}).get("tweet_count", 0),
        "verified": data.get("verified", False),
    }


def whoami() -> dict:
    """Get the authenticated user's profile.

    Returns:
        Dict with the authenticated user's profile data.
    """
    result = _run_xurl(["whoami"])
    if "error" in result:
        # Fallback to tweepy
        return _tweepy_whoami()

    data = result.get("data", {})
    return {
        "id": data.get("id", ""),
        "username": data.get("username", ""),
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "followers_count": data.get("public_metrics", {}).get("followers_count", 0),
        "following_count": data.get("public_metrics", {}).get("following_count", 0),
        "tweet_count": data.get("public_metrics", {}).get("tweet_count", 0),
    }


def _tweepy_whoami() -> dict:
    """Fallback: whoami via tweepy."""
    try:
        from tools.twitter_tools import get_twitter_client
        client = get_twitter_client()
        me = client.get_me(user_fields=["username", "name", "description", "public_metrics"])
        if me and me.data:
            metrics = me.data.public_metrics or {}
            return {
                "id": str(me.data.id),
                "username": me.data.username or "",
                "name": me.data.name or "",
                "description": me.data.description or "",
                "followers_count": metrics.get("followers_count", 0),
                "following_count": metrics.get("following_count", 0),
                "tweet_count": metrics.get("tweet_count", 0),
            }
        return {"error": "tweepy whoami returned no data"}
    except Exception as e:
        return {"error": f"whoami failed (xurl + tweepy): {e}"}


def like_tweet(tweet_id: str) -> dict:
    """Like a tweet.

    Args:
        tweet_id: The tweet ID or full URL.

    Returns:
        Dict with success status.
    """
    result = _run_xurl(["like", tweet_id])
    if "error" in result:
        return result
    return {"success": True, "tweet_id": tweet_id, "action": "liked"}


def unlike_tweet(tweet_id: str) -> dict:
    """Unlike a tweet."""
    result = _run_xurl(["unlike", tweet_id])
    if "error" in result:
        return result
    return {"success": True, "tweet_id": tweet_id, "action": "unliked"}


def repost(tweet_id: str) -> dict:
    """Repost (retweet) a tweet."""
    result = _run_xurl(["repost", tweet_id])
    if "error" in result:
        return result
    return {"success": True, "tweet_id": tweet_id, "action": "reposted"}


def unrepost(tweet_id: str) -> dict:
    """Undo a repost."""
    result = _run_xurl(["unrepost", tweet_id])
    if "error" in result:
        return result
    return {"success": True, "tweet_id": tweet_id, "action": "unreposted"}


def reply_to_tweet(tweet_id: str, text: str) -> dict:
    """Reply to a tweet.

    Args:
        tweet_id: The tweet ID or full URL to reply to.
        text: The reply text.

    Returns:
        Dict with the reply tweet data.
    """
    result = _run_xurl(["reply", tweet_id, text])
    if "error" in result:
        return result

    data = result.get("data", {})
    return {
        "id": data.get("id", ""),
        "url": f"https://x.com/i/status/{data.get('id', '')}",
        "text": data.get("text", text),
        "in_reply_to": tweet_id,
    }


def quote_tweet(tweet_id: str, text: str) -> dict:
    """Quote a tweet with commentary.

    Args:
        tweet_id: The tweet ID or full URL to quote.
        text: The quote text.

    Returns:
        Dict with the quote tweet data.
    """
    result = _run_xurl(["quote", tweet_id, text])
    if "error" in result:
        return result

    data = result.get("data", {})
    return {
        "id": data.get("id", ""),
        "url": f"https://x.com/i/status/{data.get('id', '')}",
        "text": data.get("text", text),
    }


def delete_tweet(tweet_id: str) -> dict:
    """Delete a tweet.

    Args:
        tweet_id: The tweet ID to delete.

    Returns:
        Dict with success status.
    """
    result = _run_xurl(["delete", tweet_id])
    if "error" in result:
        return result
    return {"success": True, "tweet_id": tweet_id, "action": "deleted"}


def follow_user(username: str) -> dict:
    """Follow a user.

    Args:
        username: The X handle (with or without @).

    Returns:
        Dict with success status.
    """
    username = username.lstrip("@")
    result = _run_xurl(["follow", username])
    if "error" in result:
        return result
    return {"success": True, "username": username, "action": "followed"}


def unfollow_user(username: str) -> dict:
    """Unfollow a user."""
    username = username.lstrip("@")
    result = _run_xurl(["unfollow", username])
    if "error" in result:
        return result
    return {"success": True, "username": username, "action": "unfollowed"}


def get_followers(username: Optional[str] = None, count: int = 50) -> dict:
    """Get followers of a user (defaults to authenticated user).

    Args:
        username: Optional username. Defaults to authenticated user.
        count: Number of followers to retrieve.

    Returns:
        Dict with 'followers' list.
    """
    if username:
        args = ["followers", "--of", username.lstrip("@"), "-n", str(count)]
    else:
        args = ["followers", "-n", str(count)]

    result = _run_xurl(args)
    if "error" in result:
        return result

    data = result.get("data", [])
    if isinstance(data, dict):
        data = [data]

    followers = []
    for u in data:
        followers.append({
            "id": u.get("id", ""),
            "username": u.get("username", ""),
            "name": u.get("name", ""),
        })

    return {"followers": followers, "count": len(followers)}


def get_following(username: Optional[str] = None, count: int = 50) -> dict:
    """Get users a user follows (defaults to authenticated user)."""
    if username:
        args = ["following", "--of", username.lstrip("@"), "-n", str(count)]
    else:
        args = ["following", "-n", str(count)]

    result = _run_xurl(args)
    if "error" in result:
        return result

    data = result.get("data", [])
    if isinstance(data, dict):
        data = [data]

    following = []
    for u in data:
        following.append({
            "id": u.get("id", ""),
            "username": u.get("username", ""),
            "name": u.get("name", ""),
        })

    return {"following": following, "count": len(following)}


def upload_media(file_path: str, media_type: Optional[str] = None) -> dict:
    """Upload media (image/video) to X for later use in tweets.

    Args:
        file_path: Path to the media file.
        media_type: Optional MIME type (auto-detected if not provided).

    Returns:
        Dict with media_id and status.
    """
    args = ["media", "upload", file_path]
    if media_type:
        args.extend(["--media-type", media_type])

    # Media uploads may take longer
    result = _run_xurl(args, timeout=120)
    if "error" in result:
        return result

    data = result.get("data", {})
    return {
        "media_id": data.get("id", data.get("media_id", "")),
        "status": data.get("processing_info", {}).get("state", "ready"),
    }


def get_bookmarks(count: int = 20) -> dict:
    """Get authenticated user's bookmarked tweets.

    Args:
        count: Number of bookmarks to retrieve.

    Returns:
        Dict with 'bookmarks' list.
    """
    result = _run_xurl(["bookmarks", "-n", str(count)])
    if "error" in result:
        return result

    data = result.get("data", [])
    if isinstance(data, dict):
        data = [data]

    bookmarks = []
    for t in data:
        bookmarks.append({
            "id": t.get("id", ""),
            "text": t.get("text", ""),
            "author_id": t.get("author_id", ""),
        })

    return {"bookmarks": bookmarks, "count": len(bookmarks)}


def bookmark_tweet(tweet_id: str) -> dict:
    """Bookmark a tweet."""
    result = _run_xurl(["bookmark", tweet_id])
    if "error" in result:
        return result
    return {"success": True, "tweet_id": tweet_id, "action": "bookmarked"}


def unbookmark_tweet(tweet_id: str) -> dict:
    """Remove a bookmark."""
    result = _run_xurl(["unbookmark", tweet_id])
    if "error" in result:
        return result
    return {"success": True, "tweet_id": tweet_id, "action": "unbookmarked"}


def get_likes(count: int = 20) -> dict:
    """Get authenticated user's liked tweets."""
    result = _run_xurl(["likes", "-n", str(count)])
    if "error" in result:
        return result

    data = result.get("data", [])
    if isinstance(data, dict):
        data = [data]

    likes = []
    for t in data:
        likes.append({
            "id": t.get("id", ""),
            "text": t.get("text", ""),
            "author_id": t.get("author_id", ""),
        })

    return {"likes": likes, "count": len(likes)}


def read_tweet(tweet_id: str) -> dict:
    """Read a single tweet by ID or URL.

    Args:
        tweet_id: The tweet ID or full URL.

    Returns:
        Dict with tweet data.
    """
    result = _run_xurl(["read", tweet_id])
    if "error" in result:
        return result

    data = result.get("data", {})
    return {
        "id": data.get("id", ""),
        "text": data.get("text", ""),
        "author_id": data.get("author_id", ""),
        "created_at": data.get("created_at", ""),
        "public_metrics": data.get("public_metrics", {}),
    }


def send_dm(username: str, message: str) -> dict:
    """Send a direct message to a user.

    Args:
        username: The recipient's X handle.
        message: The DM text.

    Returns:
        Dict with success status.
    """
    username = username.lstrip("@")
    result = _run_xurl(["dm", username, message])
    if "error" in result:
        return result
    return {"success": True, "recipient": username, "action": "dm_sent"}


def get_dms(count: int = 25) -> dict:
    """Get recent direct messages."""
    result = _run_xurl(["dms", "-n", str(count)])
    if "error" in result:
        return result

    data = result.get("data", [])
    if isinstance(data, dict):
        data = [data]

    dms = []
    for msg in data:
        dms.append({
            "id": msg.get("id", ""),
            "text": msg.get("text", ""),
            "sender_id": msg.get("sender_id", ""),
            "created_at": msg.get("created_at", ""),
        })

    return {"dms": dms, "count": len(dms)}


# ── Tool discovery for AgentSystem ────────────────────────────────────────

def list_available_tools() -> list[str]:
    """List all available X tools and their status."""
    tools = []
    has_xurl = _xurl_available()
    has_oauth1 = _has_oauth1_creds()

    status_msg = []
    if has_xurl:
        status_msg.append("xurl CLI (OAuth 2.0) ✓")
    if has_oauth1:
        status_msg.append("tweepy/OAuth 1.0a ✓")

    if not has_xurl and not has_oauth1:
        status_msg.append("⚠ No X auth configured")

    return status_msg


# ── Export for AgentSystem tool registration ──────────────────────────────

X_TOOLS = [
    post_tweet,
    search_tweets,
    get_timeline,
    get_mentions,
    get_user,
    whoami,
    like_tweet,
    unlike_tweet,
    repost,
    unrepost,
    reply_to_tweet,
    quote_tweet,
    delete_tweet,
    follow_user,
    unfollow_user,
    get_followers,
    get_following,
    upload_media,
    get_bookmarks,
    bookmark_tweet,
    unbookmark_tweet,
    get_likes,
    read_tweet,
    send_dm,
    get_dms,
    list_available_tools,
]
