import os
import re
import json
import time

import requests
from bs4 import BeautifulSoup



# load bundesrecht index
with open(os.path.join("ris", "bundesrecht_index.json"), "r") as f:
    bundesrecht_index = json.load(f)

print("Bundesrecht index loaded successfully!")



def fill_recursive(index, counter=0, depth=0, force_update=False):

    for key, value in index.items():
        print("  "*depth, key)
        
        if isinstance(value, list):
            time.sleep(1)
            
            # start_scraping
            index_num = key.split(" ")[0]
            position = 1
            
            while True:
                results_url = f"https://www.ris.bka.gv.at/Ergebnis.wxe?Abfrage=Bundesnormen&Kundmachungsorgan=&Index={index_num}&Titel=&Gesetzesnummer=&VonArtikel=&BisArtikel=&VonParagraf=0&BisParagraf=&VonAnlage=&BisAnlage=&Typ=&Kundmachungsnummer=&Unterzeichnungsdatum=&FassungVom=29.05.2023&VonInkrafttretedatum=&BisInkrafttretedatum=&VonAusserkrafttretedatum=&BisAusserkrafttretedatum=&NormabschnittnummerKombination=Und&ImRisSeitVonDatum=&ImRisSeitBisDatum=&ImRisSeit=Undefined&ResultPageSize=100&Suchworte=&Position={position}"


                req = requests.get(results_url).text
                soup = BeautifulSoup(req, "html.parser")

                if "Die eingegebene Suchabfrage liefert keine Treffer" in req:
                    break 

                table = soup.find("tbody", {"class": "bocListTableBody"})
                rows = table.find_all('tr')

                # check if there are more than 100 documents
                from_to_amount_string = soup.find_all("span", {"class": "NumberOfDocuments"})[0].text.strip()
                numbers = re.findall(r'\d+', from_to_amount_string)
                assert len(numbers) == 3, "Extracting from, to and amount of documents failed"
                from_number = int(numbers[0])
                to_number = int(numbers[1])
                amount = int(numbers[2])
                position = to_number + 1

                print(f"  "*(depth+1), f"Scraping {from_number} to {to_number} of {amount} documents.")

                for row in rows:
                    time.sleep(0.1)
                    s = time.time()
                    # get the link to the html from the nativeDocumentLinkCell
                    html_link = row.find_all("a", {"class": "iconOnlyLink"})[0]["href"]

                    doc_nr = html_link.strip().split("/")[-1].split(".")[0]
                    doc_nrs_in_value = [doc["gesetzesnummer"] for doc in value]
                    if (doc_nr in doc_nrs_in_value) and not force_update:
                        print("  "*(depth+1), f" * Gesetz already scraped: {doc_nr}")
                        continue

                    # fetch the html
                    gesetz_url = f"https://www.ris.bka.gv.at{html_link}"
                    gesetz = requests.get(gesetz_url).text
                    gesetz_soup = BeautifulSoup(gesetz, "html.parser")

                    content_blocks = gesetz_soup.find_all("div", {"class": "contentBlock"})

                    gesetz_info = {
                        "gesetzesnummer": "",
                        "kurztitel": "",
                        "langtitel": "",
                        "kundmachungsorgan": "",
                        "inkrafttretensdatum": "",
                        "zuletzt_aktualisiert_am": "",
                        "typ": "",
                        "schlagworte": "",
                        "dokumentnummer": "",
                        "zusammenfassung": ""
                    }
                    
                    # fill the gesetz_info dict
                    for block in content_blocks:
                        # get the title of the block
                        title = block.find("h1", {"class": "Titel"}).text.strip()
                        # get the content of the block
                        try:
                            content = block.find("p").text.strip()
                        except KeyboardInterrupt:
                            raise KeyboardInterrupt
                        except:
                            content = "* extraction failed *"

                        # fill the gesetz_info dict
                        if title == "Gesetzesnummer":
                            gesetz_info["gesetzesnummer"] = content
                        elif title == "Kurztitel":
                            gesetz_info["kurztitel"] = content
                        elif title == "Langtitel":
                            gesetz_info["langtitel"] = content
                        elif title == "Kundmachungsorgan":
                            gesetz_info["kundmachungsorgan"] = content
                        elif title == "Inkrafttretensdatum":
                            gesetz_info["inkrafttretensdatum"] = content
                        elif title == "Zuletzt aktualisiert am":
                            gesetz_info["zuletzt_aktualisiert_am"] = content
                        elif title == "Typ":
                            gesetz_info["typ"] = content
                        elif title == "Schlagworte":
                            gesetz_info["schlagworte"] = content
                        elif title == "Dokumentnummer":
                            gesetz_info["dokumentnummer"] = content
                        elif title == "Zusammenfassung":
                            gesetz_info["zusammenfassung"] = content
                        else:
                            gesetz_info[title] = content
                            
                    counter += 1

                    kurztitel = gesetz_info["kurztitel"]
                    print("  "*(depth+1), f" [{counter}] - {time.time()-s:.4f}s - Filled Gesetz: {kurztitel}")

                    value.append(gesetz_info)
                
                # break if all documents are scraped
                if position > amount: break
            
        else:
            assert isinstance(value, dict)
            value, counter = fill_recursive(value, depth=depth+1, counter=counter)
    
    return index, counter




print("Starting recursive filling.")
bundesrecht_index, counter = fill_recursive(bundesrecht_index)
print("Recursive filling completed successfully!")
print(f"Filled {counter} Gesetze.")


# save bundesrecht index
with open(os.path.join("ris", "bundesrecht_index_filled.json"), "w") as f:
    json.dump(bundesrecht_index, f, indent=4, ensure_ascii=False)

