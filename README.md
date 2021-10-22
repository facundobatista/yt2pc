# yt2pc

YouTube to Podcast converter. It gets audios from a YouTube playlist and prepares them to be consumed by a podcast client.

**NOTE**: this is for personal usage only, get an audio and listen it yourself, do not distribute it.


# How does this work?

You need a server and setup `yt2pc` there. Then fill the config file for the playlists you want to convert, and run `yt2pc` like this:

    fades yt2pc.py config_file.yaml

You do NOT need to leave `yt2pc` running, is not a service; it will leave a bunch of files in a directory that needs to be served by a regular web server, though.

The configuration file is simple. See this example:

```yaml
# base config
main:
  # the public URL from where the podcast is served
  base-public-url: https://podcasts.yoursite.com/
  # the directory where podcast files will be stored
  podcast-dir: /var/lib/podcasts
  # the history file
  history-file: /var/lib/podcast_history.txt

# collections of shows, each key is the "show id" and all data is specific for that show
shows:
  my-crazy-show:
    # title and description for the podcast metadata
    title: My Crazy Show
    description: Stand up show about crazy people coding ad-hoc crazy software
    # the URL of the YouTube playlist
    url: https://www.youtube.com/playlist?list=238asd9asd...3.141592...83092183Dg
    # when the playlist will be checked to find new episodes
    cron: "00   10    *     *     6"  # m h (local) dom mon dow
    # episodes before this date will be ignored
    start-timestamp: 2021-09-18
    # the URL of the podcast's image
    image-url: https://crazy.software/wp-content/uploads/2019/02/pikachu.png
```

Ideally you should run `yt2pc` periodically, like every hour or so. Do not worry, it will NOT hit YouTube for new stuff everytime is run, but everytime is indicated in each podcast's `cron` (see config example above).
