rm -rf env
python3 -m venv env
source env/bin/activate
pip install -U pip setuptools
pip install -r requirements.txt
python yt2pc.py "$@"