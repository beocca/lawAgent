import requests
from bs4 import BeautifulSoup


def lookup(gesetzesnummer):

    url = f"https://www.ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer={gesetzesnummer}"

    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")


    document = soup.find("div", {"class": "document"})

    content_blocks = soup.find_all("div", {"class": "contentBlock"})

    











