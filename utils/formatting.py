
import string


def dict_to_string(d):
    return str(d).replace("'", '"')


def clean_text_for_prompt(text):
    printable = set(string.printable + "§ßäöüÄÖÜ")
    cleaned_text = ''.join(filter(lambda x: x in printable, text))
    return cleaned_text


