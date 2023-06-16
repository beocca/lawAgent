import os
import json
import string
import time

import requests
from bs4 import BeautifulSoup

from openai.error import InvalidRequestError

from langchain import LLMChain
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.schema import (
	SystemMessage,
    HumanMessage,
    AIMessage
)

from config import *



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
            temperature=0,
            max_tokens=2048
        )
        self.chat_16k = ChatOpenAI(
            model="gpt-3.5-turbo-16k",
            temperature=0,
            max_tokens=4096
        )

        self.llm_curie = OpenAI(
            model="text-curie-001",
            temperature=0.0,
            max_tokens=1024
        )

        self.summary = dict()
        self.gesetze_durchsucht = list()
        self.messages = list()
        self.conversation_history = list()


    def init_prompt(self, prompt_name):
        with open(os.path.join(CHAIN_DIR, "01_get_gesetze", prompt_name), "r") as f: prompt = f.read()
        return prompt
    



    def run(self, question, max_interations=5):
        # main function to answer a question

        ## INIT MAIN VARIABLES FOR AGENT
        if isinstance(question, str):
            self.rechtsfrage = question
            self.add_message(SystemMessage(content=self.prompts["system"]))
        
        elif isinstance(question, dict):
            # TODO: init variables from previous conversation state
            raise NotImplementedError
        
        try:
            final_report = None
            for i in range(max_interations):        
                ## CHOOSE GESETZ
                # define layers, choose gesetz, erstelle zusammenfassung und reset messages
                layers = self.define_layers()
                gesetz = self.choose_gesetz(layers)
                self.summarize_progress()
                self.reset_messages(out=True)

                # choose gesetz, erstelle zusammenfassung und reset messages
                # self.summarize_progress()
                # self.reset_messages(out=True)

                if gesetz.lower() == "nichts gefunden":
                    # create summary and start over
                    # self.summarize_progress()
                    # self.reset_messages()
                    continue

                ## SCRAPE GESETZ
                assert len(gesetz.split(" - ")) == 2
                gesetz_id, gesetz_name = gesetz.split(" - ")
                gesetz_structure = self.get_gesetz_structure(gesetz_id)
                gesetz_is_long = sum([
                    len(k) + len("".join(v)) for k, v in gesetz_structure.items()]
                ) > 2000

                if gesetz_is_long:
                    ## CHOOSE SEKTION VON GESETZ            
                    # choose sektion and analyse
                    chosen_section = self.choose_section_from_gesetz(gesetz, gesetz_structure) 
                    analysis = self.analyze_section_from_gesetz(gesetz, gesetz_structure, chosen_section)
                    # add gesetz to gesetze_durchsucht
                    analyzed_section = analysis["analysierte_sektion"]
                    self.gesetze_durchsucht.append(f"{gesetz} - {analyzed_section}")
                
                else:
                    ## ANALYZE FULL GESETZ
                    # analyse
                    analysis = self.analyze_full_gesetz(gesetz, gesetz_structure)
                    # add gesetz to gesetze_durchsucht
                    self.gesetze_durchsucht.append(gesetz)


                ## DECISION
                vermutung = analysis["vermutung"]
                if vermutung.lower() == "noch nicht":
                    # create summary and start over
                    self.summarize_progress()
                    self.reset_messages()
                    continue

                else:
                    # create summary and final report
                    self.summarize_progress()
                    final_report = self.create_final_report()

                    # reset messages and break loop
                    self.reset_messages()
                    break

        except KeyboardInterrupt:
            # TODO: stop and summarize conversation
            # TODO: save whole conversation status
            pass
        
        
        # save whole conversation
        save_dict = {
            "rechtsfrage": self.rechtsfrage,
            "gesetze_durchsucht": self.gesetze_durchsucht,
            "summary": self.summary,
            "final_report": final_report,
            "conversation_history": [f"{m.type}: {m.content}" for m in self.conversation_history]
        }
        # save conversation history
        frage_str = self.rechtsfrage.replace(" ", "_").replace("?", "").replace("!", "").replace(".", "").strip()
        with open(os.path.join("answered", f"conversation_history_{frage_str}.json"), "w") as f:
            json.dump(save_dict, f, indent=4, ensure_ascii=False)

        # reset all variables after run
        self.rechtsfrage = None
        self.messages = list()
        self.conversation_history = list()
        self.gesetze_durchsucht = list()
        self.summary = dict()




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

        ## Set layers
        layers = self.define_layer(layers, f"Zu beantwortende Rechtsfrage: {self.rechtsfrage}")  # first layer
        assert len(layers) == 1
        assert layers[0] in self.bundesrecht_index.keys()
        layers = self.define_layer(layers, f"Du hast {layers[0]} gewaehlt.")                      # second layer
        assert len(layers) == 2
        assert layers[1] in self.bundesrecht_index[layers[0]].keys()
        layers = self.define_layer(layers, f"Du hast {layers[1]} gewaehlt.")                      # third layer
        assert 2 <= len(layers) <= 3

        if layers[-1] is not None:
            assert isinstance(self.bundesrecht_index[layers[0]][layers[1]], dict)
            assert isinstance(self.bundesrecht_index[layers[0]][layers[1]][layers[2]], list)

        return layers


    def define_layer(self, layers, context):

        next_layer = self.lookup_bundesrecht(layers)
        if next_layer is None: return layers
        assert len(next_layer) > 0

        # # get 2 random choices if possible
        # if len(next_layer) < 2: rand = next_layer[1]
        # else:
        #     random_choices = random.sample(next_layer, 2)
        #     rand = f"{random_choices[0]}, {random_choices[1]}, ..."
        
        output_format = {"kategorie": f"gewaehlte Kategorie inklusive voranstehende Zahl"}
        
        # Define human message
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

        # zusammenfassung = self.summary["zusammenfassung"]
        context = f"Zu beantwortende Rechtsfrage: {self.rechtsfrage}"  #\n\nZusammenfassung des bisherigen Fortschritts: {zusammenfassung}"

        gesetze = [
            g["gesetzesnummer"] + " - " + g["kurztitel"]
            for g in self.bundesrecht_gesetze_for_category(layers)
            if len(str(g["gesetzesnummer"]).strip()) > 0
        ]
        output_format = {"nummer": "die davorstehende nummer des gesetzes", "titel": "der titel des gewählten gesetzes 'nichts gefunden'"}
        current_human_message = HumanMessage(
            content=self.prompts["gesetz_waehlen"].format(
                context=context,
                laws="\n".join(gesetze),
                gesetze_durchsucht="\n".join(self.gesetze_durchsucht),
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
            "analysierte_sektion": "der name oder id der sektion die analysiert wurde",
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
            "zusammenfassung": "fasse noch einmal zusammen wie du beim beantworten der Frage vorgegangen bist",
            "komplexe antwort": "gib eine möglichst genaue und komplexe antwort und erklaerung; zusätzliche informationen sind gerne gesehen; gerichtet an einen juristischen Experten",
            "einfache antwort": "gib eine einfache antwort und erklaerung; vermeide informationen nach welchen nicht explizit gefragt wird; gerichtet an einen juristischen Laien",
            "explizite antwort": "die anwort in einem satz",
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
            content=self.clean_text(human_message.content) + "\n\n"
        )

        # append human message to conversation history and agent memory
        self.add_message(human_message)
        
        # get chat completion
        try:
            if model == "4k": response = self.chat(self.messages)
            if model == "16k": response = self.chat_16k(self.messages)
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except InvalidRequestError:
            response = self.chat_16k(self.messages)

        # append response message to conversation history and agent memory
        self.add_message(response)

        # do checks and return 
        time.sleep(1)
        assert isinstance(response, AIMessage)
        return json.loads(response.content)
        # TODO: handle this better! -> i.e. return a message that the agent did not understand the human message


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

        # load prompt
        prompt = None
        with open(os.path.join("chains", "00_helper", "clean_gesetz_section_title.txt"), "r") as f:
            prompt = f.read()
        assert prompt is not None

        # initialize variables for loop
        cleaned_section_names = []
        section_names = list(gesetz_structure.keys())

        # loop over all section names
        for i, section_name in enumerate(section_names):

            # format prompt and get response
            formatted_prompt = prompt.format(eingabe=section_name)
            response = self.llm_curie.generate([formatted_prompt]).generations[0][0].text
            
            # clean response
            response = response.split("\n")[0]
            response = response.strip()

            # append cleaned response to list
            cleaned_section_names.append(response)

        # Create new gesetz structure and return it
        new_gesetz_structure = {}
        assert len(cleaned_section_names) == len(gesetz_structure.keys())
        for old, new in zip(gesetz_structure.keys(), cleaned_section_names):
            new_gesetz_structure[new] = gesetz_structure[old.replace(" ", "")]
            

        return new_gesetz_structure
    


    def format_gesetz_structure(self):
        pass


    def format_gesetz_section_content(self):
        pass






if __name__ == "__main__":
    
    la = LawAgent()
    la.run("Wie schnell darf ich auf der Autobahn fahren?")
    la.run("Wie lange darf ein sich ein 15 jähriger in der Nacht auf der Straße aufhalten?")


    print("...done")



