import os
import tempfile
import click
import requests
import feedparser
from datetime import datetime, timedelta
from calendar import timegm

import structlog

from typing import Optional
from jinja2 import Environment, PackageLoader, select_autoescape


logger = structlog.get_logger(__name__)


class PostBuilder(object):
    def __init__(self):
        self.load_environment_variables()
        self.jinja_env = Environment(
            loader=PackageLoader("main"),
            autoescape=select_autoescape(),
        )

    def load_environment_variables(self):
        self.rss_url = os.getenv("RSS_URL")
        self.max_links = os.getenv("MAX_LINKS")
        # By default, we look at the past 7 days.
        self.timespan = os.getenv("TIMESPAN", "7")
        # This must be http with a github token.
        # For example https://x-access-token:$GITHUB_TOKEN@github.com/briandailey/repo.git
        self.blog_repo = os.getenv("BLOG_REPO")
        self.blog_repo_branch = os.getenv("BLOG_REPO_BRANCH", "main")
        # Path to which we are saving the file.
        self.path_to_post = os.getenv("PATH_TO_POST", "content/post")

        if self.rss_url is None:
            self.rss_path = os.getenv("RSS_PATH")

        if self.rss_url is None and self.rss_path is None:
            raise ValueError("RSS_URL or RSS_PATH must be set")

    def fetch_rss(self) -> Optional[str]:
        """Fetch RSS content from the provided URL."""
        if self.rss_url is not None:
            return self.fetch_rss_from_url(self.rss_url)
        else:
            return self.fetch_rss_from_file(self.rss_path)

    def fetch_rss_from_url(self, rss_url: str) -> Optional[str]:
        logger.info("Fetching RSS from URL", rss_url=rss_url)
        try:
            response = requests.get(rss_url)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.text
        except requests.RequestException as e:
            click.echo(f"Error fetching RSS feed: {e}", err=True)
            return None

    def fetch_rss_from_file(self, rss_path: str) -> Optional[str]:
        logger.info("Fetching RSS from file", rss_path=rss_path)
        with open(rss_path, "r") as f:
            return f.read()

    def parse_rss(self, rss: str) -> list[dict]:
        """Parse the RSS content into a list of dictionaries."""
        # Read the RSS content into a list of dictionaries.
        # Use feedparser to parse the RSS content.
        feed = feedparser.parse(rss)
        return feed.entries

    def filter_items(self, items: list[dict]) -> list[dict]:
        """Filter the items based on the timespan."""
        # Filter the items based on the timespan.
        # If the timespan is a number (it will always be a string, but
        # check to see if it's numeric), filter the items based on the number of days.
        # If the timespan is a date, filter the items based on the date.

        if isinstance(self.timespan, str) and self.timespan.isdigit():
            return self.filter_items_by_days(items)
        else:
            raise NotImplementedError("Filtering by date not implemented")

    def filter_items_by_days(self, items: list[dict]) -> list[dict]:
        """Filter the items based on the number of days."""
        matching_items = []
        for item in items:
            item_date = datetime.fromtimestamp(timegm(item.updated_parsed))
            days_ago = (datetime.now() - item_date).days
            logger.debug("Item date", item_date=item_date, days_ago=days_ago)
            if days_ago > int(self.timespan):
                continue
            matching_items.append(item)
        return matching_items

    def assemble_post(self, items: list[dict]) -> str:
        """Assemble the post from the items."""
        # Assemble the post from the items.
        # Use the Jinja template to assemble the post.
        template = self.jinja_env.get_template("template.md")
        post = template.render(items=items, date=datetime.now())
        return post

    def push_post_to_blog_repo(self, post: str):
        """Push the post to the blog repo."""
        # Checkout the blog repo locally into a temporary directory.

        # We create a slug for this post, e.g., "assorted-links-2025-02-11"

        slug = f"assorted-links-{datetime.now().strftime('%Y-%m-%d')}"

        content_directory = ""
        tmp_dir = tempfile.mkdtemp()
        logger.debug("Cloning blog repo", repo=self.blog_repo, tmp_dir=tmp_dir)
        os.system(f"git clone {self.blog_repo} {tmp_dir}")
        os.mkdir(os.path.join(tmp_dir, self.path_to_post, slug))
        # Add the file to the repo in the correct place.
        logger.debug(
            "Writing post to repo",
            post=post,
            path=os.path.join(tmp_dir, self.path_to_post, slug, "index.md"),
        )
        with open(os.path.join(tmp_dir, self.path_to_post, slug, "index.md"), "w") as f:
            f.write(post)
        # Commit the file.
        # Temporarily disable signed commits.
        os.system(f"git -C {tmp_dir} config --local commit.gpgsign false")
        os.system(
            f"git -C {tmp_dir} add {os.path.join(tmp_dir, self.path_to_post, slug, 'index.md')}"
        )
        os.system(f"git -C {tmp_dir} commit -m 'Add new assorted links.'")
        # Push the file to the repo.
        os.system(f"git -C {tmp_dir} push")


if __name__ == "__main__":
    builder = PostBuilder()
    rss = builder.fetch_rss()
    items = builder.parse_rss(rss)
    items = builder.filter_items(items)
    if len(items) == 0:
        logger.info("Nothing to post.")
        exit(0)
    post = builder.assemble_post(items)
    builder.push_post_to_blog_repo(post)
