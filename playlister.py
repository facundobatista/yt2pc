from datetime import datetime, timedelta, date

from yt_dlp import YoutubeDL
from yt_dlp.extractor.youtube._tab import YoutubeTabBaseInfoExtractor

IGNORE_TAGS = {"views", "vistas", "Futurock", "elDiarioAR", "estrena", "Smok", "Radio", "Eduardo"}

MULTIPLIER = {
    "seg": 1,
    "segundo": 1,
    "segundos": 1,

    "min": 60,
    "minuto": 60,
    "minutos": 60,

    "h": 60 * 60,
    "hora": 60 * 60,
    "horas": 60 * 60,

    "d": 24 * 60 * 60,
    "día": 24 * 60 * 60,
    "días": 24 * 60 * 60,

    "sem.": 7 * 24 * 60 * 60,
    "semana": 7 * 24 * 60 * 60,
    "semanas": 7 * 24 * 60 * 60,

    "m": 30 * 24 * 60 * 60,
    "mes": 30 * 24 * 60 * 60,
    "meses": 30 * 24 * 60 * 60,

    "a": 365 * 24 * 60 * 60,
    "año": 365 * 24 * 60 * 60,
    "años": 365 * 24 * 60 * 60,
}

MONTHS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


def _date_aprox_parsing(text):
    if "hoy" in text:
        return 3600  # 1h

    if "ayer" in text:
        return 3600 * 24

    start = text.find("por última vez el")
    if start > 0:
        text = text[start + len("por última vez el"):]
        sd, sm, sy = text.split()
        y = int(sy)
        m = MONTHS[sm]
        d = int(sd)
        delta = date.today() - date(y, m, d)
        return delta.days * 3600 * 24

    start = text.index("hace")
    text = text[start:]
    hace, quant, scale = text.split()
    assert hace == "hace"
    quant = int(quant)
    mult = MULTIPLIER[scale]
    return quant * mult


def _parse_time_text(self, text, report_failure=False):
    # complexity here is that this receives a weird amount of metadata, not only text time

    if not text:
        # just empty
        return

    if any(x in text for x in IGNORE_TAGS):
        # '1.4\xa0K vistas'
        # '1.4\xa0K views'
        # 'Futurock FM y Prisma - Justicia y Seguridad'
        return

    if text[0].isdigit():
        # '6.8\xa0K'
        # '240'
        return

    try:
        value = _date_aprox_parsing(text)
    except Exception as exc:
        # print(f"ERROR PARSING {text!r}: {exc!r}")
        return

    dt = datetime.now() - timedelta(seconds=value)
    tstamp = int(dt.timestamp())
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
