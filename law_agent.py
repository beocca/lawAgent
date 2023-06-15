import os
import json
import string

import requests
from bs4 import BeautifulSoup

from langchain.chat_models import ChatOpenAI
from langchain.schema import (
	SystemMessage,
    HumanMessage,
    AIMessage
)

from config import *


CONVERSATIION = {
    "rechtsfrage": str(),
    "antwort": None,                 # answer to the question "not None" only if answered
    "progress": str(),               # summary of the conversation
    "gesetze_durchsucht": list(),    # list of gesetznamen (id - name - sektion)
    "conversation_history": list(),  # list of messages
}



class LawAgent:

    rechtsfrage: str
    summary: dict
    gesetze_durchsucht: list

    bundesrecht_index: dict
    prompts: dict
    messages: list
    conversation_history: list

    chat: ChatOpenAI
    chat_16k: ChatOpenAI


    def __init__(self) -> None:
        # Load Bundesrecht Index Filled
        with open(os.path.join("ris", "bundesrecht_index_filled.json"), "r") as f:
            self.bundesrecht_index = json.load(f)

        # Load Prompts
        self.prompts = {
            "system":                       self.init_prompt("01_system.txt"),
            "kategorie_waehlen":            self.init_prompt("02_kategorie_waehlen.txt"),
            "gesetz_waehlen":               self.init_prompt("03_gesetz_waehlen.txt"),
            "zusammenfassung_erstellen":    self.init_prompt("04_zusammenfassung_erstellen.txt"),
            "gesetzestext_teil_waehlen":    self.init_prompt("05_gesetzestext_teil_waehlen.txt"),
            "gesetzestext_teil_zeigen":     self.init_prompt("06_gesetzestext_teil_zeigen.txt"),
            "gesetzestext_gesamt":          self.init_prompt("07_gesetzestext_gesamt.txt"),
            "finaler_report":               self.init_prompt("08_finalen_report_erstellen.txt"),
        }

        self.chat = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.15,
            max_tokens=2048
        )
        self.chat_16k = ChatOpenAI(
            model="gpt-3.5-turbo-16k",
            temperature=0.15,
            max_tokens=4096
        )

        self.summary = dict()
        self.gesetze_durchsucht = list()
        self.messages = list()
        self.conversation_history = list()


    def init_prompt(self, prompt_name):
        with open(os.path.join(CHAIN_DIR, "01_get_gesetze", prompt_name), "r") as f: prompt = f.read()
        return prompt
    



    def run(self, question):
        # main function to answer a question

        ## INIT MAIN VARIABLES FOR AGENT
        self.rechtsfrage = question
        self.add_message(SystemMessage(content=self.prompts["system"]))
        

        while True:
                
            ## CHOOSE GESETZ
            # define layers, erstelle zusammenfassung und reset messages
            layers = self.define_layers()
            self.summarize_progress()
            self.reset_messages(out=True)

            # choose gesetz, erstelle zusammenfassung und reset messages
            
            gesetz = self.choose_gesetz(layers)
            self.gesetze_durchsucht.append(gesetz)
            self.summarize_progress()
            self.reset_messages(out=True)

            if gesetz.lower() == "nichts gefunden": 
                continue

            ## SCRAPE GESETZ
            assert len(gesetz.split(" - ")) == 2
            gesetz_id, gesetz_name = gesetz.split(" - ")
            gesetz_structure = self.get_gesetz_structure(gesetz_id)

            gesetz_is_long = sum([
                len(k) + len("".join(v)) for k, v in gesetz_structure.items()]
            ) > 1000

            if gesetz_is_long:
                ## CHOOSE SEKTION VON GESETZ            
                # choose sektion
                chosen_section = self.choose_section_from_gesetz(gesetz, gesetz_structure)

                # show requested section and try to answer question with it 
                analysis = self.analyze_section_from_gesetz(gesetz, gesetz_structure, chosen_section)
            
            else:
                analysis = self.analyze_full_gesetz(gesetz, gesetz_structure)


            vermutung = analysis["vermutung"]
            

            ## DECISION
            if vermutung.lower() == "noch nicht":
                # TODO: create summary and start over
                self.summarize_progress()
                self.reset_messages()
                


            else:
                # create final report


                final_report = self.create_final_report()
                # TODO: save whole conversation
                
                

                break



            ## DECIDE IF QUESTION IS ANSWERED
            # TODO: 


    def lookup_bundesrecht(self, layers):
        if len(layers) == 0:
            return self.bundesrecht_index.keys()
        elif len(layers) == 1:
            l1 = layers[0]
            return self.bundesrecht_index[l1].keys()
        elif len(layers) == 2:
            l1, l2 = layers
            try: return self.bundesrecht_index[l1][l2].keys()
            except KeyboardInterrupt: raise KeyboardInterrupt
            except: return None
        else:
            raise ValueError("Too many layers.")


    def bundesrecht_gesetze_for_category(self, layers):
        assert len(layers) <= 3
        
        first, second, third = layers

        if third is None:
            gesetze = self.bundesrecht_index[first][second]
            assert isinstance(gesetze, list)
            return gesetze 
        else:
            gesetze = self.bundesrecht_index[first][second][third]
            assert isinstance(gesetze, list)
            return gesetze
        


    def define_layers(self):
        
        # Define initial variables
        layers = list()
        output_format = {"kategorie": "gewaehlte Kategorie inklusive voranstehende Zahl"}

        ## Set layers
        layers = self.define_layer(layers, output_format, f"Zu beantwortende Rechtsfrage: {self.rechtsfrage}")  # first layer
        assert len(layers) == 1
        assert layers[0] in self.bundesrecht_index.keys()
        layers = self.define_layer(layers, output_format, f"Du hast {layers[0]} gewaehlt.")                      # second layer
        assert len(layers) == 2
        assert layers[1] in self.bundesrecht_index[layers[0]].keys()
        layers = self.define_layer(layers, output_format, f"Du hast {layers[1]} gewaehlt.")                      # third layer
        assert 2 <= len(layers) <= 3

        if layers[-1] is not None:
            assert isinstance(self.bundesrecht_index[layers[0]][layers[1]], dict)
            assert isinstance(self.bundesrecht_index[layers[0]][layers[1]][layers[2]], list)

        return layers


    def define_layer(self, layers, output_format, context):

        next_layer = self.lookup_bundesrecht(layers)
        if next_layer is None: return layers
        
        # Define human message
        output_format = {"kategorie": "gewaehlte Kategorie inklusive voranstehende Zahl"}
        current_human_message = HumanMessage(
            content=self.prompts["kategorie_waehlen"].format(
                context=context,
                categories="\n".join(next_layer),
                output_format=self.clean_output_format(output_format)
            )
        )
        response = self.get_chat_completion(current_human_message)

        # Define chosen layers and return
        chosen_category = response["kategorie"]
        if len(layers) == 0: layers = [chosen_category]
        else: layers.append(chosen_category)
        return layers


    def summarize_progress(self):
        output_format = {
            "zusammenfassung": "eine kurze, aber detailierte zusammenfassung ueber deinen bisherigen Fortschritt",
            "frage beantwortet": "hast du die frage schon beantwortet? waehle aus folgender liste: 'ja' | 'noch nicht' ",
            "begruendung": "begruende deine Entscheidung",
        }
        current_human_message = HumanMessage(
            content=self.prompts["zusammenfassung_erstellen"].format(
                output_format=str(output_format).replace("'", '"'),
            )
        )

        summary = self.get_chat_completion(current_human_message)
        self.summary = summary

    
    def choose_gesetz(self, layers):
        # Choose gesetz to look through

        zusammenfassung = self.summary["zusammenfassung"]
        context = f"Zu beantwortende Rechtsfrage: {self.rechtsfrage}\n\nZusammenfassung des bisherigen Fortschritts: {zusammenfassung}"

        gesetze = [g["gesetzesnummer"] + " - " + g["kurztitel"] for g in self.bundesrecht_gesetze_for_category(layers)]
        output_format = {"nummer": "die davorstehende nummer des gesetzes", "titel": "der titel des gewählten gesetzes 'nichts gefunden'"}
        current_human_message = HumanMessage(
            content=self.prompts["gesetz_waehlen"].format(
                context=context,
                laws="\n".join(gesetze),
                output_format=str(output_format).replace("'", '"')
            )
        )
        response = self.get_chat_completion(current_human_message)
        gesetz = response["nummer"] + " - " + response["titel"]
        return gesetz




    def choose_section_from_gesetz(self, gesetz, gesetz_structure):
        context = f"Zu beantwortende Rechtsfrage: {self.rechtsfrage}\n\nZusammenfassung des bisherigen Fortschritts: {self.summary['zusammenfassung']}"
        output_format = {
            "gewaehlte_sektionen": ["sektion (ganze zeile zitiert!!)", "..." ]
        }
        choose_section_message = HumanMessage(
            content=self.prompts["gesetzestext_teil_waehlen"].format(
                context=context,
                gesetz=gesetz,
                struktur="\n".join([s for s in gesetz_structure.keys() if s.strip().startswith("§")]),
                output_format=str(output_format).replace("'", '"')
            ) + "\n\nAchte darauf, dass du immer die gesamte Zeile zitierst und nicht nur die Nummer der Sektion!"
        )
        response = self.get_chat_completion(choose_section_message, model="16k")
        chosen_sections = response["gewaehlte_sektionen"]

        # chosen_sections = [s["paragraph"] + " - " + s["name"] for s in chosen_sections]

        return chosen_sections[0]  # TODO: return all chosen sections
    



    def analyze_full_gesetz(self, gesetz, gesetz_structure):
        geltende_fassung = str()
        for k, v in gesetz_structure.items():
            content = " ".join(v)
            geltende_fassung += f"{k}\n"
            geltende_fassung += f"{content}\n\n"
        geltende_fassung = geltende_fassung.strip()

        output_format = {
            "vermutung": "stelle eine Vermutungen an ob dieses Gesetz ausreichend ist um die Frage zu beantworten? waehle aus folgender liste: 'ja' | 'nein'",
            "begruendung": "eine kurze begruendung warum",
            "loesungsansatz": "wie koennte die frage beantwortet werden?",
            "naechster schritt": "was sollte als naechstes getan werden? waehle aus folgender liste: 'neues_gesetz' | 'done' "
        }
        show_chosen_section_message = HumanMessage(
            content=self.prompts["gesetzestext_gesamt"].format(
                gesetz=gesetz,
                geltende_fassung=geltende_fassung,
                output_format=str(output_format).replace("'", '"')
            )
        )

        # get chat completion and return analysis of gesetz
        analysis = self.get_chat_completion(show_chosen_section_message, model="16k")
        return analysis

    


    def analyze_section_from_gesetz(self, gesetz, gesetz_structure, chosen_section):
        assert chosen_section in gesetz_structure.keys()

        geltende_fassung = gesetz_structure[chosen_section]
        output_format = {
            "vermutung": "stelle eine Vermutungen an ob der gebene Teil ausreichend ist um die Frage zu beantworten? waehle aus folgender liste: 'ja' | 'nein'",
            "begruendung": "eine kurze begruendung warum",
            "loesungsansatz": "wie koennte die frage beantwortet werden?",
            "naechster schritt": "was sollte als naechstes getan werden? waehle aus folgender liste: 'neues_gesetz' | 'done' "
        }
        show_chosen_section_message = HumanMessage(
            content=self.prompts["gesetzestext_teil_zeigen"].format(
                gesetz=gesetz,
                geltende_fassung=geltende_fassung,
                output_format=str(output_format).replace("'", '"')
            )
        )

        # get chat completion and return analysis of gesetz
        analysis = self.get_chat_completion(show_chosen_section_message, model="16k")
        return analysis
        

    
    def create_final_report(self):
        output_format = {
            "zusammenfassung": "fasse nocheinmal zusammen wie du beim beantworten der Frage vorgegangen bist",
            "komplexe antwort": "gib eine möglichst genaue und komplexe antwort und erklaerung; gerichtet an einen juristischen Experten",
            "einfache antwort": "gib eine einfache antwort und erklaerung; gerichtet an einen juristischen Laien",
            "begruendung": "begruende deine antwort",
            # "weiter lernen": "gib empfehlungen ab welche themen noch interessant sein koennten",
        }

        current_human_message = HumanMessage(
            content=self.prompts["finaler_report"].format(
                output_format=str(output_format).replace("'", '"'),
            )
        )

        # get chat completion and return the final report
        final_report = self.get_chat_completion(current_human_message, model="16k")
        return final_report

    
    def get_chat_completion(self, human_message, model="4k"):
        assert model in ["4k", "16k"]

        # clean human message
        human_message = HumanMessage(
            content=self.clean_text(human_message.content)
        )


        # append human message to conversation history and agent memory
        self.add_message(human_message)
        
        # get chat completion
        if model == "4k": response = self.chat(self.messages)
        if model == "16k": response = self.chat_16k(self.messages)
        
        # append response message to conversation history and agent memory
        self.add_message(response)

        # do checks and return 
        assert isinstance(response, AIMessage)
        try:
            return json.loads(response.content)
        except:
            return response.content


    def reset_messages(self, out=False):

        if out: 
            for m in self.messages:
                assert isinstance(m, SystemMessage) or isinstance(m, HumanMessage) or isinstance(m, AIMessage)
                if isinstance(m, SystemMessage):    u = "System"
                if isinstance(m, HumanMessage):     u = "Human"
                if isinstance(m, AIMessage):        u = "AI"
                print(u, m.content)

        self.messages = self.messages[:1]


    def add_message(self, message):
        self.messages.append(message)
        self.conversation_history.append(message)
    

    def clean_output_format(self, d):
        return str(d).replace("'", '"')
    
    def clean_text(self, text):
        printable = set(string.printable + "§ßäöüÄÖÜ")
        cleaned_text = ''.join(filter(lambda x: x in printable, text))
        return cleaned_text
    

    def get_gesetz_structure(self, gesetz_id):

        # Get Geltende Fassung von Gesetz
        gesetz_structure_path = os.path.join("ris", "bundesrecht", f"gesetz_structure_{gesetz_id}.json")
        if not os.path.exists(gesetz_structure_path):
            url = f"https://www.ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer={gesetz_id}"
            html = requests.get(url).text
            soup = BeautifulSoup(html, "html.parser")
            pagebase = soup.find("div", {"id": "pagebase"})
            content = pagebase.find("div", {"id": "content"})
            document_contents = content.find_all("div", {"class": "documentContent"})
            gesetz_structure = {}
            for doc_content in document_contents:
                text_nodes = doc_content.find_all(string=True)
                text_nodes = [tn.strip() for tn in text_nodes if len(tn.strip()) > 0]
                text_nodes = [tn for tn in text_nodes if tn.lower() != "text"]
                text_nodes = [tn for tn in text_nodes if not tn.startswith("Art. ")]
                text_nodes = [self.clean_text(tn) for tn in text_nodes]
                section_name, section_content = " - ".join(text_nodes[:2]), text_nodes[2:]
                section_content = [c for c in section_content if not c.startswith("§")]
                section_content = [c for c in section_content if not c.startswith("Paragraph ")]
                section_content = [self.clean_text(c) for c in section_content]
                gesetz_structure[section_name.replace(" ", "")] = text_nodes[2:]
            
            # create cleaner gesetz structure
            gesetz_structure = self.structure_gesetz_helper(gesetz_structure)

            # save as json
            with open(gesetz_structure_path, "w") as f:    
                json.dump(gesetz_structure, f, indent=4, ensure_ascii=False)

        else:
            with open(gesetz_structure_path, "r") as f:
                gesetz_structure = json.load(f, strict=False)

        return gesetz_structure
    


    def structure_gesetz_helper(self, gesetz_structure):
        # Set up messages for structure cleaner chain
        output_format = [["alter titel", "neuer (schoen formatierter) titel"]]
        messages = [
            SystemMessage(
                content="Bitte konvertiere diese Liste in Namen mit einheitlicher Struktur.\n"
                "Gib deine Antworten ausschließlich in form von JSON in folgendem Format aus:\n"
                f"{output_format}"
            ),
            HumanMessage(
                content=str(list(gesetz_structure.keys()))
            )
        ]

        cleaned_section_names = []
        section_names = list(gesetz_structure.keys())

        # Process sections in batches of 10
        for i in range(0, len(section_names), 10):
        # for i in range(0, 10, 10):
            batch = section_names[i:i+10]
            messages[-1] = HumanMessage(content=str(batch))

            # Let agent clean the structure for the current batch
            response = self.chat(messages)
            response = response.content.replace("'", '"')
            cleaned_batch = json.loads(response)

            for row in cleaned_batch:
                assert len(row) == 2
                cleaned_section_names.append(row)

        # Create new gesetz structure and return it
        new_gesetz_structure = {}
        for old, new in cleaned_section_names:
            new_gesetz_structure[new] = gesetz_structure[old]

        return new_gesetz_structure







if __name__ == "__main__":
    
    la = LawAgent()
    la.run("Wie schnell darf ich auf der Autobahn fahren?")


    print("...done")



