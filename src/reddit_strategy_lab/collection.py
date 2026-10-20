import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .schema import Post


def now():
    return datetime.now(timezone.utc).isoformat()


def read_posts(path, limit=100):
    path = Path(path)
    if path.stat().st_size > 5_000_000:
        raise ValueError("post import too large")
    text = path.read_text()
    items = (
        [json.loads(line) for line in text.splitlines() if line.strip()]
        if path.suffix == ".jsonl"
        else json.loads(text)
    )
    if isinstance(items, dict):
        items = [items]
    if len(items) > limit:
        raise ValueError("batch limit exceeded")
    seen, result = set(), []
    for item in items:
        post = Post.model_validate(item)
        key = (post.id, post.content_hash)
        if key not in seen:
            result.append(post)
            seen.add(key)
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("unexpected HTTP redirect blocked")


class Reddit:
    def __init__(self, store):
        if os.environ.get("REDDIT_API_APPROVED") != "true":
            raise ValueError(
                "approved Reddit API access required; set REDDIT_API_APPROVED=true only after approval"
            )
        self.token = os.environ.get("REDDIT_ACCESS_TOKEN")
        self.agent = os.environ.get("REDDIT_USER_AGENT")
        if not self.token or not self.agent:
            raise ValueError("missing REDDIT_ACCESS_TOKEN or REDDIT_USER_AGENT")
        self.store = Path(store)
        self.store.mkdir(parents=True, exist_ok=True)
        self.opener = build_opener(NoRedirect)

    def get(self, endpoint, params):
        req = Request(
            "https://oauth.reddit.com/" + endpoint + "?" + urlencode(params),
            headers={"Authorization": "Bearer " + self.token, "User-Agent": self.agent},
        )
        for attempt in range(3):
            try:
                with self.opener.open(req, timeout=30) as response:
                    body = response.read(5_000_001)
                    if len(body) > 5_000_000:
                        raise ValueError("response exceeds size cap")
                    remaining = float(response.headers.get("x-ratelimit-remaining", "100"))
                    reset = float(response.headers.get("x-ratelimit-reset", "0"))
                if remaining < 1:
                    if reset > 60:
                        raise ValueError("Reddit rate budget exhausted; retry after reset")
                    time.sleep(max(0, reset))
                return json.loads(body)
            except HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise ValueError(f"Reddit HTTP {e.code}; no anonymous fallback") from None
                delay = max(2**attempt, float(e.headers.get("Retry-After", "0")))
                if delay > 60:
                    raise ValueError("rate limited; resume later") from None
                time.sleep(delay)
        raise ValueError("Reddit request failed")

    def save(self, d):
        if not d.get("selftext") or d["selftext"] in ("[deleted]", "[removed]"):
            record = dict(id=d.get("id"), status="missing/inaccessible", collected_at=now())
            with (self.store / "inaccessible.jsonl").open("a") as f:
                f.write(json.dumps(record) + "\n")
            return None
        edited = d.get("edited")
        post = Post(
            id=d["id"],
            url="https://www.reddit.com" + d["permalink"],
            subreddit=d["subreddit"],
            title=d["title"],
            body=d["selftext"],
            published_at=datetime.fromtimestamp(d["created_utc"], timezone.utc).isoformat(),
            collected_at=now(),
            edited_at=datetime.fromtimestamp(edited, timezone.utc).isoformat() if edited else None,
            access_method="reddit_oauth",
        )
        target = self.store / (post.id + "-" + post.content_hash + ".json")
        if not target.exists():
            target.write_text(post.model_dump_json(indent=2))
        return post

    def link(self, url):
        match = re.fullmatch(
            r"https://(?:www\.)?reddit\.com/r/[A-Za-z0-9_]+/comments/([a-z0-9]+)(?:/[^?#]*)?", url
        )
        if not match:
            raise ValueError("canonical Reddit post URL required")
        items = self.get("api/info", {"id": "t3_" + match[1]})["data"]["children"]
        if not items:
            raise ValueError("post missing/inaccessible")
        post = self.save(items[0]["data"])
        if post is None:
            raise ValueError("post text missing/inaccessible")
        return [post]

    def discover(
        self,
        subreddit="algotrading",
        limit=20,
        feeds=("new", "top"),
        queries=None,
        max_requests=8,
        time_filter="year",
    ):
        """Bounded, diverse source streams with independent resumable cursors and an audit ledger."""
        import math

        from .schema import digest

        subs = subreddit.split(",")
        if not subs or len(subs) > 5 or any(not re.fullmatch(r"[A-Za-z0-9_]{1,30}", sub) for sub in subs):
            raise ValueError("supply 1..5 valid comma-separated subreddits")
        if (
            not 1 <= limit <= 100
            or not 1 <= max_requests <= 30
            or any(f not in ("new", "top", "hot") for f in feeds)
            or time_filter not in ("day", "week", "month", "year", "all")
        ):
            raise ValueError("invalid discovery batch/request/feed/time bounds")
        if queries is None:
            queries = [
                "overnight OR premarket OR close",
                "momentum OR breakout",
                "volume OR volatility",
                "entry AND exit",
            ]
        if len(queries) > 8 or any(len(q) > 200 for q in queries):
            raise ValueError("search query budget exceeded")
        channels = [(sub, feed, None) for sub in subs for feed in feeds] + [
            (sub, "search", q) for sub in subs for q in queries
        ]
        if not channels:
            raise ValueError("at least one discovery channel required")
        posts = []
        seen = set()
        audit = []
        cutoff = now()
        # Rotate which channel gets first use of a bounded request budget between invocations.
        rotation_file = self.store / ("discovery-rotation-" + digest(channels)[:16] + ".json")
        rotation = json.loads(rotation_file.read_text()).get("next", 0) if rotation_file.exists() else 0
        channels = channels[rotation % len(channels) :] + channels[: rotation % len(channels)]
        requests = 0
        for index in range(max_requests):
            if len(posts) >= limit:
                break
            sub, feed, query = channels[index % len(channels)]
            channel = digest(dict(subreddit=sub, feed=feed, query=query, time_filter=time_filter))
            checkpoint = self.store / ("cursor-" + channel[:20] + ".json")
            state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
            quota = min(25, limit - len(posts), max(1, math.ceil(limit / min(len(channels), max_requests))))
            params = {"limit": quota, "raw_json": 1}
            if state.get("after"):
                params["after"] = state["after"]
            if feed in ("search", "top"):
                params["t"] = time_filter
            if feed == "search":
                params.update(q=query, restrict_sr="on", sort="new")
            page = self.get("r/" + sub + "/" + feed, params)["data"]
            requests += 1
            for item in page["children"]:
                post = self.save(item["data"])
                event = dict(
                    subreddit=sub,
                    feed=feed,
                    query=query,
                    source_id=item["data"].get("id"),
                    collected_at=cutoff,
                )
                if post is None:
                    event["status"] = "missing/inaccessible"
                else:
                    key = (post.id, post.content_hash)
                    event["content_hash"] = post.content_hash
                    event["status"] = "duplicate source version" if key in seen else "candidate"
                    if key not in seen:
                        posts.append(post)
                        seen.add(key)
                audit.append(event)
            checkpoint.write_text(
                json.dumps(
                    dict(
                        after=page.get("after"),
                        collected_at=cutoff,
                        channel=dict(subreddit=sub, feed=feed, query=query, time_filter=time_filter),
                    )
                )
            )
        rotation_file.write_text(json.dumps(dict(next=(rotation + requests) % len(channels))))
        batch = dict(
            collected_at=cutoff,
            requests=requests,
            request_cap=max_requests,
            candidate_cap=limit,
            candidates=len(posts),
            sources=audit,
            coverage="bounded listing/search slices; not complete historical coverage; no comments or linked pages",
        )
        (self.store / ("discovery-batch-" + digest(batch)[:20] + ".json")).write_text(
            json.dumps(batch, indent=2)
        )
        (self.store / "latest-discovery.json").write_text(json.dumps(batch, indent=2))
        return posts
