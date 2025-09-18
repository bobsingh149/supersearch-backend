import time
from pytrends.request import TrendReq

pytrends = TrendReq(hl='en-US', tz=360)

keywords = ["summer dress", "vintage fashion"]

for kw in keywords:
    pytrends.build_payload([kw], timeframe='today 12-m', geo='US')
    related = pytrends.related_queries()

    print(f"\nKeyword: {kw}")

    if related[kw]['top'] is not None:
        print("Top Related Queries:\n", related[kw]['top'].head())
    else:
        print("Top Related Queries: None")

    if related[kw]['rising'] is not None:
        print("Rising Related Queries:\n", related[kw]['rising'].head())
    else:
        print("Rising Related Queries: None")

