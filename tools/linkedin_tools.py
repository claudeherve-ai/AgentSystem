"""
LinkedIn API integration module using the requests library.

Provides functions to retrieve profile information and
create text posts via the LinkedIn v2 API.
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


def get_linkedin_headers() -> dict:
    """Build authorization headers for LinkedIn API requests.

    Reads the LINKEDIN_ACCESS_TOKEN environment variable.

    Returns:
        Dict of HTTP headers including Authorization and Content-Type.
    """
    access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if not access_token:
        raise EnvironmentError("LINKEDIN_ACCESS_TOKEN environment variable is not set.")

    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }


def get_linkedin_profile_id() -> str:
    """Get the authenticated user's LinkedIn profile URN.

    Returns:
        The profile URN string (e.g. 'urn:li:person:AbCdEf1234').
    """
    try:
        headers = get_linkedin_headers()
        response = requests.get(
            f"{LINKEDIN_API_BASE}/me",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        profile_id = data.get("id", "")
        urn = f"urn:li:person:{profile_id}"

        logger.info("LinkedIn profile URN: %s", urn)
        return urn

    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error getting LinkedIn profile ID: %s – %s", e, e.response.text if e.response else "")
        raise
    except Exception as e:
        logger.error("Failed to get LinkedIn profile ID: %s", e)
        raise


def get_linkedin_profile() -> dict:
    """Get the authenticated user's basic LinkedIn profile information.

    Returns:
        Dict with id, first_name, last_name, and headline.
    """
    try:
        headers = get_linkedin_headers()
        response = requests.get(
            f"{LINKEDIN_API_BASE}/me",
            headers=headers,
            params={"projection": "(id,firstName,lastName,headline)"},
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        # LinkedIn localised fields use {locale: {language_tag: value}} structure
        first_name = ""
        if "firstName" in data and "localized" in data["firstName"]:
            localized = data["firstName"]["localized"]
            first_name = next(iter(localized.values()), "") if localized else ""

        last_name = ""
        if "lastName" in data and "localized" in data["lastName"]:
            localized = data["lastName"]["localized"]
            last_name = next(iter(localized.values()), "") if localized else ""

        headline = ""
        if "headline" in data and "localized" in data.get("headline", {}):
            localized = data["headline"]["localized"]
            headline = next(iter(localized.values()), "") if localized else ""

        result = {
            "id": data.get("id", ""),
            "first_name": first_name,
            "last_name": last_name,
            "headline": headline,
        }

        logger.info("Retrieved LinkedIn profile for %s %s", first_name, last_name)
        return result

    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error getting LinkedIn profile: %s – %s", e, e.response.text if e.response else "")
        raise
    except Exception as e:
        logger.error("Failed to get LinkedIn profile: %s", e)
        raise


def post_to_linkedin(text: str) -> dict:
    """Create a text post on LinkedIn via the ugcPosts endpoint.

    Args:
        text: The text content of the post.

    Returns:
        Dict with id and text of the created post.
    """
    try:
        headers = get_linkedin_headers()
        author_urn = get_linkedin_profile_id()

        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text,
                    },
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
            },
        }

        response = requests.post(
            f"{LINKEDIN_API_BASE}/ugcPosts",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        post_id = data.get("id", "")

        result = {
            "id": post_id,
            "text": text,
        }

        logger.info("LinkedIn post created: %s", post_id)
        return result

    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error posting to LinkedIn: %s – %s", e, e.response.text if e.response else "")
        raise
    except Exception as e:
        logger.error("Failed to post to LinkedIn: %s", e)
        raise
