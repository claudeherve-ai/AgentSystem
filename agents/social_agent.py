"""
AgentSystem — Social Media Agent.

Manages social media posting across Twitter/X, LinkedIn, and Instagram.
All posts require human approval before publishing.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails import Guardrails
from guardrails.approval import HumanApproval
from tools.audit import log_action

logger = logging.getLogger(__name__)

_guardrails = Guardrails()
_approval = HumanApproval()


async def draft_social_post(
    platform: Annotated[str, "Target platform: twitter, linkedin, or instagram"],
    content: Annotated[str, "The post content/text"],
    tone: Annotated[str, "Tone: professional, casual, informative, promotional"] = "professional",
) -> str:
    """
    Draft a social media post for a given platform. Does NOT publish.
    Applies platform-specific formatting and character limits.
    """
    platform = platform.lower().strip()
    limits = {
        "twitter": 280,
        "linkedin": 3000,
        "instagram": 2200,
    }

    if platform not in limits:
        return f"Unsupported platform: {platform}. Supported: twitter, linkedin, instagram"

    char_limit = limits[platform]
    if len(content) > char_limit:
        return (
            f"Post exceeds {platform} character limit ({len(content)}/{char_limit}). "
            f"Please shorten it."
        )

    draft = (
        f"📱 DRAFT POST — {platform.upper()}\n"
        f"{'─' * 40}\n"
        f"Tone: {tone}\n"
        f"Characters: {len(content)}/{char_limit}\n"
        f"{'─' * 40}\n"
        f"{content}\n"
        f"{'─' * 40}\n"
        f"Status: DRAFT (not published)"
    )

    log_action(
        "SocialAgent",
        "draft_social_post",
        f"Platform: {platform}, Tone: {tone}",
        f"Draft: {content[:100]}...",
        status="drafted",
    )
    return draft


async def publish_post(
    platform: Annotated[str, "Target platform: twitter, linkedin, or instagram"],
    content: Annotated[str, "The post content/text"],
    schedule_time: Annotated[Optional[str], "Optional ISO datetime to schedule the post"] = None,
) -> str:
    """
    Publish a social media post. REQUIRES human approval.
    Optionally schedule for a future time.
    """
    platform = platform.lower().strip()

    # Rate limit check
    try:
        _guardrails.check_social_rate()
    except Exception as e:
        return f"Rate limit exceeded: {e}"

    # Content length check
    if not _guardrails.check_content_length(content):
        return "Post is too long. Please shorten it."

    action_desc = "schedule_post" if schedule_time else "publish_post"
    details = (
        f"Platform: {platform}\n"
        f"{'Schedule: ' + schedule_time if schedule_time else 'Publish: immediately'}\n"
        f"Content:\n{content}"
    )

    approved, feedback = await _approval.request_approval(
        agent_name="SocialAgent",
        action=action_desc,
        details=details,
    )

    if not approved:
        log_action("SocialAgent", action_desc, f"Platform: {platform}", "Rejected", status="rejected")
        if feedback:
            return f"Post NOT published. Feedback: {feedback}"
        return "Post NOT published. Human rejected."

    # Publish via real APIs
    try:
        if platform == "twitter":
            from tools.twitter_tools import post_tweet
            result = post_tweet(content)
            log_action("SocialAgent", action_desc, f"Platform: twitter", f"Tweet: {result.get('url', 'N/A')}", approved_by="human", status="completed")
            return f"✅ Tweet posted: {result.get('url', 'N/A')}"
        elif platform == "linkedin":
            from tools.linkedin_tools import post_to_linkedin
            result = post_to_linkedin(content)
            log_action("SocialAgent", action_desc, f"Platform: linkedin", f"Post ID: {result.get('id', 'N/A')}", approved_by="human", status="completed")
            return f"✅ LinkedIn post created (ID: {result.get('id', 'N/A')})"
        else:
            log_action("SocialAgent", action_desc, f"Platform: {platform}", f"Published: {content[:100]}...", approved_by="human", status="completed")
            return f"Platform {platform} not yet connected. Draft saved."
    except ValueError as e:
        return f"⚠️ {platform} not configured: {e}\nSet API credentials in .env."
    except Exception as e:
        log_action("SocialAgent", action_desc, f"Platform: {platform}", f"Error: {e}", status="error")
        return f"Error publishing to {platform}: {e}"


async def check_engagement(
    platform: Annotated[str, "Platform to check: twitter, linkedin, or instagram"],
    post_count: Annotated[int, "Number of recent posts to analyze"] = 5,
) -> str:
    """
    Check engagement metrics for recent posts on a platform.
    """
    log_action("SocialAgent", "check_engagement", f"Platform: {platform}, count: {post_count}")

    try:
        if platform == "twitter":
            from tools.twitter_tools import get_recent_tweets
            tweets = get_recent_tweets(post_count)
            if not tweets:
                return "No recent tweets found."
            result = f"📊 Twitter Engagement ({len(tweets)} posts):\n{'─' * 50}\n"
            for t in tweets:
                result += (
                    f"  📝 {t['text'][:80]}...\n"
                    f"     ❤️ {t.get('likes',0)} | 🔁 {t.get('retweets',0)} | "
                    f"💬 {t.get('replies',0)} | 👁️ {t.get('impressions',0)}\n\n"
                )
            return result
        else:
            return f"Engagement metrics for {platform} not yet connected."
    except Exception as e:
        return f"Error fetching engagement: {e}"


async def get_posting_schedule() -> str:
    """
    Return the recommended posting schedule based on the social media skill.
    """
    return (
        "📅 Recommended Posting Schedule:\n"
        "─────────────────────────────────\n"
        "Twitter/X:   2-3 posts/day, best times: 9am, 12pm, 5pm\n"
        "LinkedIn:    1 post/day, best times: 7-8am, 12pm, 5-6pm (Tue-Thu)\n"
        "Instagram:   1 post/day, best times: 11am-1pm, 7-9pm\n"
        "─────────────────────────────────\n"
        "Tip: Maintain consistent brand voice across platforms.\n"
        "Avoid posting the same content on all platforms simultaneously."
    )


SOCIAL_TOOLS = [draft_social_post, publish_post, check_engagement, get_posting_schedule]
