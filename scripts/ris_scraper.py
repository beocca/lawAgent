import os
import re
import json
import requests
from bs4 import BeautifulSoup


import time
import datetime as dt



## SCRAPE BUNDESRECHT
def scrape_bundesrecht_ris():
    position = 1
    docs_info = []

    while True:

        ris_url = f"https://www.ris.bka.gv.at/Ergebnis.wxe?Abfrage=BgblAuth&Titel=&Bgblnummer=&SucheNachGesetzen=True&SucheNachKundmachungen=True&SucheNachVerordnungen=True&SucheNachSonstiges=True&SucheNachTeil1=True&SucheNachTeil2=True&SucheNachTeil3=True&Einbringer=&VonDatum=01.01.2004&BisDatum=28.05.2023&ImRisSeitVonDatum=01.01.2004&ImRisSeitBisDatum=28.05.2023&ImRisSeit=Undefined&ResultPageSize=100&Suchworte=&Position={position}&SkipToDocumentPage=true"


        req = requests.get(ris_url)
        soup = BeautifulSoup(req.text, "html.parser")

        # get number of results
        from_to_amount_string = soup.find_all("span", {"class": "NumberOfDocuments"})[0].text.strip()
        numbers = re.findall(r'\d+', from_to_amount_string)
        assert len(numbers) == 3, "Extracting from, to and amount of documents failed"
        to_value = int(numbers[1])
        amount_value = int(numbers[2])

        # get all table rows -> <tr class="bocListDataRow odd" role="row">
        trs = soup.find_all("tr", {"class": ["bocListDataRow odd", "bocListDataRow even"]})

        # get information about the rows
        for i, tr in enumerate(trs):
            s = time.time()

            bgbi_nr = tr.find_all("td")[2].text.strip()
            kundmachung = tr.find_all("td")[3].text.strip()
            kurzinfo = tr.find_all("td")[4].text.strip()
            html_link = tr.find_all("span", attrs={"class": "nativeDocumentLinkCell"})[0].find_all("a", {"class": "iconOnlyLink"})[0]["href"]
            pdf_link = tr.find_all("span", attrs={"class": "nativeDocumentLinkCell"})[0].find_all("a", {"class": "iconOnlyLink"})[2]["href"]
            # convert kundmachung from dd.mm.yyyy to yyyymmdd
            kundmachung = dt.datetime.strptime(kundmachung, "%d.%m.%Y").strftime("%Y%m%d")
            docs_info.append(
                {
                    "bgbi_nr": bgbi_nr,
                    "kundmachung": kundmachung,
                    "kurzinfo": kurzinfo,
                    "html_link": html_link,
                    "pdf_link": pdf_link
                }
            )

            # clean bgbi_nr
            bgbi_nr = bgbi_nr.replace("/", "_")
            bgbi_nr = bgbi_nr.replace(" ", "_")
            bgbi_nr = bgbi_nr.replace(".", "")


            html_save_path = os.path.join("ris", "bundesrecht", f"{bgbi_nr}_{kundmachung}.html")

            # DOWNLOAD & SAVE HTML
            if not os.path.exists(html_save_path):
                
                # download html
                download_link = f"https://www.ris.bka.gv.at{html_link}"
                html = requests.get(download_link, timeout=300).text
                time.sleep(0.25)

                # remove script, style and meta tags
                doc_soup = BeautifulSoup(html, "html.parser")
                for script in doc_soup(["script", "style", "meta"]):
                    script.decompose()

                # save html body
                soup = BeautifulSoup(str(doc_soup), "html.parser")
                html = soup.prettify()

                with open(html_save_path, "w") as f:
                    f.write(html)
                
            print(position+i, round(time.time()-s, ndigits=4), kundmachung, bgbi_nr)


        # check if last page was just parsed
        if to_value == amount_value:
            print("Last page was parsed")
            break
        else: 
            position = to_value + 1

        time.sleep(1)

    return docs_info



# scrape and save to json
docs_info = scrape_bundesrecht_ris()
with open("ris/bundesrecht.json", "w") as f:
    json.dump(docs_info, f, indent=4)    




