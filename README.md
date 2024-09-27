python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pm2 start healthchecker.py --name hc -f --interpreter ../.venv/bin/python