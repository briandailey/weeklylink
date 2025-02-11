I want to share interesting things that I posted to Pinboard and create a
weekly blog post, much like Tyler Cowen's [Assorted
Links](https://marginalrevolution.com/marginalrevolution/2025/02/friday-assorted-links-507.html).

## Configuration

- `RSS_URL`
- `MAX_LINKS` - Optional, We only post the most recent links.
- `TIMESPAN` - How far back do we go? This can be an integer, indicating number
  of days, or a date (YYYY-MM-DD).
- `BLOG_REPO` - The blog repository that we are going to fetch and add a post
  to.
- `PATH_TO_POST` - The path to where we are placing new blog files.

There are some other things you can customize, too, like the post template. You
can fork this and change the template.md, which uses Jinja for formatting.

## What we are doing

- Pull down the RSS from the URL.
- Loop over the `<items>` that match the given `TIMESPAN`
- Assemble them into a Markdown post using the Jinja template.
- Pull down the targeted Github repository
- Add the new blog post.
- Commit it. Push it to `master`.

The assumption is that pushing to `master` will handle the blog being
re-deployed, we don't want to pollute this function with secondary concerns.
