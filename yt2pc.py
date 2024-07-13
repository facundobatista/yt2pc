#!/usr/bin/env fades

import argparse
import datetime
import glob
import json
import logging
import os
import subprocess
from dataclasses import dataclass

import croniter  # fades
import dateutil.parser  # fades python-dateutil
import yaml  # fades
import youtube_dl  # fades git+https://github.com/ytdl-org/youtube-dl.git
from feedgen.feed import FeedGenerator  # fades
from dateutil.utils import default_tzinfo
from dateutil.tz import tzoffset

logger = logging.getLogger()
h = logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-10s %(message)s"))
logger.addHandler(h)
logger.setLevel(logging.INFO)

DFLT_TZ = tzoffset("UTC", 0)


@dataclass
class PlayListItem:
    description: str
    item_id: str
    webpage_url: str
    title: str
    date: datetime.date
    best_format: str

    def __str__(self):
        return f"<PlayListItem id={self.item_id} date={self.date:%Y-%m-%d}>"


def list_yt(playlist_url):
    # youtbe-dl is in the path because `youtube_dl` is in the virtualenv
    cmd = ["youtube-dl", "--skip-download", "--print-json", playlist_url]
    logger.info("Getting playlist metadata")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)

    while True:
        line = proc.stdout.readline().strip()
        if not line:
            break
        shouldstop = yield line
        if shouldstop:
            break
    proc.terminate()


def get_playlist_content(playlist_url, filters):
    """Get the content of a YouTube playlist."""
    if filters is not None:
        filters = [x.lower() for x in filters]

    # filter to get only the last month (or at least 10 episodes)
    modern = []
    date_limit = default_tzinfo(datetime.datetime.now(), DFLT_TZ) - datetime.timedelta(days=30)
    list_gen = list_yt(playlist_url)
    for idx, line in enumerate(list_gen):
        data = json.loads(line)
        date = default_tzinfo(dateutil.parser.parse(data['upload_date']), DFLT_TZ)
        logger.debug("        exploring episode date %s", date)
        if date < date_limit and idx > 10:
            try:
                list_gen.send(True)
            except StopIteration:
                pass
            break
        modern.append(data)

    results = []
    for data in modern:
        # apply filters if present
        if filters is not None:
            text_to_search = data['fulltitle'].lower()
            logger.debug("        exploring title %r", text_to_search)
            if not any(f in text_to_search for f in filters):
                continue
            logger.debug("            match")

        for fmt in data['formats']:
            if fmt['ext'] == "m4a":
                best_format = fmt['format_id']
                break
        else:
            raise ValueError(f"Best format not found in {data['formats']}")

        date = default_tzinfo(dateutil.parser.parse(data['upload_date']), DFLT_TZ)
        plitem = PlayListItem(
            description=data['description'],
            item_id=data['display_id'],
            title=data['fulltitle'],
            webpage_url=data['webpage_url'],
            date=date,
            best_format=best_format,
        )
        results.append(plitem)

    results.sort(key=lambda item: item.date, reverse=True)
    return results


def report_progress(info):
    """Report download."""
    total = info.get('total_bytes', info.get('total_bytes_estimate'))
    if total is None:
        logger.debug("Progress? No 'total' in %s", info)
        return
    dloaded = info['downloaded_bytes']
    size_mb = total // 1024 ** 2
    perc = dloaded * 100.0 / total
    print(f"{perc:.1f}% of {size_mb:.0f} MB\r", end='', flush=True)


def _download_and_process(base_path, url, video_format):
    """Download from YouTube, showing process, and leave a .mp3."""
    logger.info("Download episode %s", base_path)

    # get from yt
    conf = {
        'outtmpl': base_path,
        'progress_hooks': [report_progress],
        'quiet': True,
        'format': video_format,
    }
    with youtube_dl.YoutubeDL(conf) as ydl:
        logger.debug("Downloading from url %r", url)
        ydl.download([url])

    # convert to mp3
    logger.info("    converting to mp3")
    mp3_name = base_path + ".mp3"
    cmd = [
        "ffmpeg", "-loglevel", "error",
        "-i", base_path,
        "-vn", "-ab", "128k", "-ar", "44100",
        mp3_name,
    ]

    subprocess.run(cmd, check=True)
    os.unlink(base_path)
    logger.info("    done")


def download(show_config, main_config):
    """Download a show."""
    playlist = get_playlist_content(show_config['url'], show_config.get("filters"))

    show_id = show_config['id']
    mp3_location = main_config['podcast-dir']
    already_downloaded = glob.glob(os.path.join(mp3_location, show_id) + "*.mp3")
    already_downloaded = [os.path.basename(x) for x in already_downloaded]

    # build the filename with the show id and the show hours for the ones we need to download
    for item in playlist:
        logger.debug("Found %s", item)
        if show_config['start-timestamp'] > item.date:
            logger.info("Ignoring episode (before start timestamp): %s", item)
            continue

        base_name = f"{show_id}-{item.date:%Y%m%d}-{item.item_id}"
        if any(x.startswith(base_name) for x in already_downloaded):
            logger.info("Ignoring episode (already downloaded): %s", item)
            continue

        logger.info("Downloading episode: %s", item)
        base_path = os.path.join(mp3_location, base_name)
        _download_and_process(base_path, item.webpage_url, item.best_format)

    # prepare some metadata from the playlist to write in the podcast
    metadata = {item.item_id: item for item in playlist}

    write_podcast(show_config, main_config, metadata)


def check_show(show_config, last_process, main_config, selected_show):
    """Check for a specific show."""
    now = datetime.datetime.now()

    if selected_show is not None:
        logger.info("    ignoring history (forced show)")
        download(show_config, main_config)
    elif last_process is None:
        # never did it before, do it now
        logger.info("    downloading show for the first time")
        download(show_config, main_config)
    else:
        from_cron = croniter.croniter(show_config['cron'], last_process)
        next_date = from_cron.get_next(datetime.datetime)
        logger.info("Next date to check: %s", next_date)
        if next_date > now:
            logger.info("    still in the future, pass")
        else:
            logger.info("    downloading show again")
            download(show_config, main_config)
    return now


def write_podcast(show_config, main_config, all_metadata):
    """Create the podcast file for a specific show (for all episodes)."""
    fg = FeedGenerator()
    fg.load_extension('podcast')

    base_public_url = main_config["base-public-url"]
    show_id = show_config["id"]
    url = "{}{}.xml".format(base_public_url, show_id)
    fg.id(show_id)
    fg.title(show_config["title"])
    fg.description(show_config["description"])
    image_url = show_config.get("image-url")
    if image_url is not None:
        fg.image(image_url)
    fg.link(href=url, rel='self')

    # collect all mp3s for the given show
    all_mp3s = glob.glob(os.path.join(main_config["podcast-dir"], f"{show_id}-*.mp3"))
    logger.info("Generating XML for %d mp3s", len(all_mp3s))

    for filepath in all_mp3s:
        filename = os.path.basename(filepath)
        mp3_id = filename.split('.')[0]
        episode_id = mp3_id.split("-", maxsplit=2)[2]
        ep_metadata = all_metadata.get(episode_id)
        if ep_metadata is None:
            logger.debug("ignoring mp3 in disk (no metadata): %s", episode_id)
            continue

        mp3_size = os.stat(filepath).st_size
        mp3_url = base_public_url + filename

        # build the rss entry
        fe = fg.add_entry()
        fe.id(mp3_id)
        fe.pubdate(ep_metadata.date)
        fe.title(ep_metadata.title)
        fe.description(ep_metadata.description)
        fe.enclosure(mp3_url, str(mp3_size), 'audio/mpeg')

    fg.rss_str(pretty=True)
    fg.rss_file(os.path.join(main_config["podcast-dir"], f'{show_id}.xml'))


class History:
    """Manage the history file."""
    def __init__(self, history_file):
        self.history_file = history_file

        # (try to) open it
        if os.path.exists(history_file):
            with open(history_file, 'rt', encoding='utf8') as fh:
                self.data = data = {}
                for line in fh:
                    show_id, last_timestamp = line.strip().split()
                    data[show_id] = dateutil.parser.parse(last_timestamp)
        else:
            self.data = {}

    def get(self, show_id):
        """Get the last process for given show_id (if any)."""
        return self.data.get(show_id)

    def _save(self):
        """Save the content to disk."""
        temp_path = self.history_file + ".temp"
        with open(temp_path, 'wt', encoding='utf8') as fh:
            for show_id, last_time in sorted(self.data.items()):
                fh.write("{} {}\n".format(show_id, last_time.isoformat()))

        os.rename(temp_path, self.history_file)

    def set(self, show_id, last_run):
        """Set the last process for the given show_id to 'now' and save."""
        self.data[show_id] = last_run
        self._save()


def load_config(config_file_path, selected_show):
    """Load the configuration file and validate format."""
    with open(config_file_path, 'rt', encoding='utf8') as fh:
        raw_config = yaml.safe_load(fh)

    if not isinstance(raw_config, dict):
        raise ValueError("Bad general config format, must be a dict/map.")

    # main section
    main_keys = {'base-public-url', 'podcast-dir', 'history-file'}
    main = raw_config.get('main', ())
    missing = main_keys - set(main)
    if missing:
        raise ValueError(f"Missing keys in main config: {missing}")

    # shows section
    shows = []
    show_keys = {'title', 'description', 'url', 'cron', 'start-timestamp'}
    for show_id, show_data in raw_config['shows'].items():
        if not show_id.isalnum():
            raise ValueError(
                "Bad format for show id {!r} (must be alphanumerical)".format(show_id))

        if selected_show is not None and selected_show != show_id:
            logger.warning("Ignoring config because not selected show: %r", show_id)
            continue

        missing = show_keys - set(show_data)
        if missing:
            raise ValueError("Missing keys {} for show id {}".format(missing, show_id))

        # ensure we always have a timezoned datetime
        tstamp = show_data['start-timestamp']
        tstamp = datetime.datetime.fromordinal(tstamp.toordinal())
        show_data['start-timestamp'] = default_tzinfo(tstamp, DFLT_TZ)

        show_data['id'] = show_id
        shows.append(show_data)

    return dict(main=main, shows=shows)


def main(config_file_path, selected_show=None):
    """Main entry point."""
    # open the config file
    try:
        config = load_config(config_file_path, selected_show)
    except ValueError as exc:
        logger.error("Problem loading config: %s", exc)
        exit()

    logger.info("Loaded config for shows %s", sorted(x['id'] for x in config['shows']))

    # open the history file
    history = History(config['main']['history-file'])

    for show_data in config['shows']:
        show_id = show_data['id']
        logger.info("Processing show %r", show_id)
        last_process = history.get(show_id)
        logger.info("    last process: %s", last_process)
        last_run = check_show(show_data, last_process, config['main'], selected_show)
        history.set(show_id, last_run)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--show', help="Work with this show only.")
    parser.add_argument('--quiet', action='store_true', help="Be quiet, unless any issue is found")
    parser.add_argument('--verbose', action='store_true', help="Be verbose")
    parser.add_argument('config_file', help="The configuration file")
    args = parser.parse_args()

    # parse input
    if args.quiet:
        logger.setLevel(logging.WARNING)
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    main(args.config_file, args.show)
