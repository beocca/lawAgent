import json
import codecs

def convert_json_file(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        json_data = file.read()

    parsed_json = json.loads(json_data)

    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(parsed_json, file, ensure_ascii=False, indent=4)

# Usage example
input_file_path = 'ris/bundesrecht_index_filled.json'
output_file_path = 'output.json'
convert_json_file(input_file_path, output_file_path)



import json
import requests as r
from bs4 import BeautifulSoup as bs
gesetz_id = 10002296
url = f"https://www.ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer={gesetz_id}"
html = r.get(url).text
soup = bs(html, "html.parser")
pagebase = soup.find("div", {"id": "pagebase"})
content = pagebase.find("div", {"id": "content"})
document_contents = content.find_all("div", {"class": "documentContent"})

ueberschrG1 = content.find_all("h4", {"class": "UeberschrG1"})
paragraphen_mit_absatzzahl = content.find_all("div", {"class": "ParagraphMitAbsatzzahl"})


gesetz_structure = {}
for doc_content in document_contents:
    text_nodes = doc_content.find_all(string=True)
    text_nodes = [tn.strip() for tn in text_nodes if len(tn.strip()) > 0]
    text_nodes = [tn for tn in text_nodes if tn.lower() != "text"]
    text_nodes = [tn for tn in text_nodes if not tn.startswith("Art. ")]
    section_name, section_content = " - ".join(text_nodes[:2]), text_nodes[2:]
    section_content = [c for c in section_content if not c.startswith("§")]
    section_content = [c for c in section_content if not c.startswith("Paragraph ")]
    gesetz_structure[section_name] = text_nodes[2:]

# save as json
with open(f"ris/bundesrecht/gesetz_structure_{gesetz_id}.json", "w") as f:    
    json.dump(gesetz_structure, f, indent=4, ensure_ascii=False)




for ub in ueberschrG1:
    text = " - ".join(text_nodes) # join the text nodes with a dash
    print(text)
