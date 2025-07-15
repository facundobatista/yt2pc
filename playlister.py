from datetime import datetime, timedelta

from yt_dlp import YoutubeDL
from yt_dlp.extractor.youtube._tab import YoutubeTabBaseInfoExtractor


MULTIPLIER = {
    "segundo": 1,
    "segundos": 1,
    "minuto": 60,
    "minutos": 60,
    "hora": 60 * 60,
    "horas": 60 * 60,
    "día": 24 * 60 * 60,
    "días": 24 * 60 * 60,
    "semana": 7 * 24 * 60 * 60,
    "semanas": 7 * 24 * 60 * 60,
    "mes": 30 * 24 * 60 * 60,
    "meses": 30 * 24 * 60 * 60,
    "año": 365 * 24 * 60 * 60,
    "años": 365 * 24 * 60 * 60,
}


def _date_aprox_parsing(text):
    hace, quant, scale = text.split()
    assert hace == "hace"
    quant = int(quant)
    mult = MULTIPLIER[scale]
    return quant * mult


def _parse_time_text(self, text):
    print("=========== parse src", text)
    tstamp = None
    if text:
        try:
            value = _date_aprox_parsing(text)
        except Exception as exc:
            print(f"ERROR PARSING {text!r}: {exc!r}")
        else:
            dt = datetime.now() - timedelta(seconds=value)
            tstamp = int(dt.timestamp())

    print("=========== parse res", tstamp)
    return tstamp


YoutubeTabBaseInfoExtractor._parse_time_text = _parse_time_text


def get(url):
    """Get a playlist from the given URL."""
    options = {
        "extract_flat": True,
        "quiet": True,
        "extractor_args": {
            "youtubetab": {"approximate_date": ["true"]},
            "youtube": {"lang": ["es-419"]},
        },
    }

    with YoutubeDL(options) as ydl:
        result = ydl.extract_info(url, download=False)
        entries = result["entries"]
        return entries
