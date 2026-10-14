# Marketing Tune-Up

Static site for **podcast.6stringcreative.com**, hosted on GitHub Pages. `build.py` reads `site.json` and `content/posts/*.md`, then writes `dist/`. There are no package dependencies.

## Add a weekly episode

1. Copy the latest file in `content/posts/`. Right now that is `content/posts/2026-10-20-how-many-google-reviews.md`.
2. Name the copy `YYYY-MM-DD-short-slug.md`. The date in the name is for you. The build uses the header fields below.
3. Put the episode thumbnail in `assets/` and set `thumbnail` to that path.
4. Fill in the header. Use the search phrase as `title` (what a business owner would type), not a clever hook. Keep it under about 70 characters. `Marketing Tune-Up` is added to the browser title automatically.
5. Write the show notes in the body: chapters, sources, and a cleaned-up transcript. Plain `- ` bullets. No emojis.
6. Commit to `main`. A push rebuilds the site. You do not have to wait for the push if the episode is in the future: the scheduled workflow publishes it. See below.

Header fields:

```
title: "Search phrase people actually type"
date: YYYY-MM-DD
time: "11:30"
episode: "N"
minutes: "5"
summary: "One or two sentences. This is the meta description and the episode card."
tag: "Topic"
slug: "short-slug"
thumbnail: "assets/your-thumbnail.jpg"
thumbnail_alt: "Short description of the thumbnail"
youtube_id: ""
audio: ""
spotify: ""
apple: ""
disclosure: "The hosts are AI voices; every stat is real and credited."
```

`time` is America/New_York, 24-hour. Episodes publish at 11:30 AM ET. Leave a field as an empty string to hide that control:

| Field | What to paste | When it is empty |
| --- | --- | --- |
| `youtube_id` | The YouTube video id only, not the full URL | The thumbnail is shown instead of an embed |
| `audio` | Direct audio URL for the player | The audio player is hidden |
| `spotify` | This episode's Spotify URL | The Spotify button is hidden |
| `apple` | This episode's Apple Podcasts URL | The Apple Podcasts button is hidden |

Show-level listen links live in `site.json` under `subscribe`. Each entry has a `label` and a `url`. An empty `url` hides that button on the home page.

| Label | Paste this when it exists |
| --- | --- |
| Subscribe on YouTube | The YouTube channel URL, with `?sub_confirmation=1` |
| Spotify | The show URL on Spotify |
| Apple Podcasts | The show URL on Apple Podcasts |
| RSS | The podcast RSS URL. The site also writes `/rss.xml`. Point this at that feed, or at your podcast host, once you want the button. |

Set `draft: true` in the header to keep a file out of the build entirely.

### When it goes live

The build drops any episode whose `date` and `time` are still in the future in America/New_York. It does not generate the page, the card, the sitemap entry, or the RSS item.

GitHub Actions rebuilds on every push to `main`, on **Run workflow**, and on a schedule: Tuesday at 16:45 UTC. That is 11:45 AM EST and 12:45 PM EDT, so it is always after 11:30 AM Eastern, including daylight saving. To publish in the minutes right after 11:30, use **Run workflow** on the Pages workflow.

Preview upcoming episodes locally without changing the gate:

```
SHOW_FUTURE=1 python3 build.py
```

Check a specific Eastern Time moment with `BUILD_AS_OF=2026-10-13T11:30 python3 build.py`.

## Content rules

- No emojis in titles, notes, buttons, or descriptions. Use plain `- ` bullets.
- Credit every stat with the source and year from the episode notes. Do not round or reword the finding.
- Do not name vendors, prices, real clients, or a city or region.
- Dan and Kate are AI, and the page should say so in the `disclosure` line.

## Local preview

`python3 build.py`, then open `dist/index.html` or run `python3 -m http.server -d dist`.

## Hosting

Settings > Pages > Source: **GitHub Actions**. Custom domain: `podcast.6stringcreative.com` (also in `CNAME`). Leave `CNAME` as it is.

DNS: CNAME record `podcast` pointing to `OWNER.github.io`.
