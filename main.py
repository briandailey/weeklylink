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
    def __init__(
        self,
        rss_url: Optional[str] = None,
        rss_path: Optional[str] = None,
        max_links: Optional[int] = None,
        timespan: str = "7",
        blog_repo: str = None,
        blog_repo_branch: str = "main",
        path_to_post: str = "content/post",
    ):
        if rss_url is None and rss_path is None:
            raise ValueError(
                "Either rss URL or a local path to an RSS file must be provided"
            )

        self.rss_url = rss_url
        self.rss_path = rss_path
        self.max_links = max_links
        self.timespan = timespan
        self.blog_repo = blog_repo
        self.blog_repo_branch = blog_repo_branch
        self.path_to_post = path_to_post

        self.jinja_env = Environment(
            loader=PackageLoader("main"),
            autoescape=select_autoescape(),
        )

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


@click.command()
@click.option("--rss-url", help="URL of the RSS feed")
@click.option("--rss-path", help="Path to local RSS file")
@click.option("--max-links", type=int, help="Maximum number of links to include")
@click.option("--timespan", default="7", help="Timespan in days for filtering posts")
@click.option(
    "--blog-repo", required=True, help="Git repository URL (with token if needed)"
)
@click.option("--blog-repo-branch", default="main", help="Git repository branch")
@click.option(
    "--path-to-post", default="content/post", help="Path where posts should be saved"
)
@click.option("--no-interactive", is_flag=True, help="Skip confirmation before posting")
def main(
    rss_url,
    rss_path,
    max_links,
    timespan,
    blog_repo,
    blog_repo_branch,
    path_to_post,
    no_interactive,
):
    """Generate and publish blog posts from RSS feeds."""
    try:
        builder = PostBuilder(
            rss_url=rss_url,
            rss_path=rss_path,
            max_links=max_links,
            timespan=timespan,
            blog_repo=blog_repo,
            blog_repo_branch=blog_repo_branch,
            path_to_post=path_to_post,
        )

        rss = builder.fetch_rss()
        if not rss:
            logger.error("Failed to fetch RSS content")
            return

        items = builder.parse_rss(rss)
        items = builder.filter_items(items)

        if len(items) == 0:
            logger.info("Nothing to post.")
            return

        post = builder.assemble_post(items)

        if not no_interactive:
            click.echo("\nGenerated post content:")
            click.echo("-" * 40)
            click.echo(post)
            click.echo("-" * 40)
            if not click.confirm("\nDo you want to publish this post?"):
                click.echo("Aborted.")
                return

        builder.push_post_to_blog_repo(post)
        logger.info("Successfully published new post")

    except Exception as e:
        logger.error("Error occurred", error=str(e))
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
