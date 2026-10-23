"""Send realistic traffic to the live API, then print the drift report."""
import csv
import json
import random
import sys
import urllib.request

url = sys.argv[1].rstrip("/")
with open("data/raw/telco_churn.csv") as f:
    ids = [row["customerID"] for row in csv.DictReader(f)]
for cid in random.sample(ids, 40):
    urllib.request.urlopen(f"{url}/customers/{cid}/churn-risk").read()
print(json.dumps(json.load(urllib.request.urlopen(f"{url}/monitoring/drift")), indent=2))