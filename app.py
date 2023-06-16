import os

import telebot


from config import *
from law_agent import LawAgent



bot = telebot.TeleBot(os.environ["BOT_TOKEN"]) # create a bot instance

bot_commands = [
    "/new"
]




@bot.message_handler(commands=bot_commands)
def send_welcome(message):


    # assert that command is valid
    assert message.text in bot_commands, f"Command {message.text} is not valid."


    bot.reply_to(message, "Hello, I'm a telegram bot written in python.") # reply to the message



@bot.message_handler(func=lambda msg: True) # handle all other messages
def echo_all(message):
    bot.reply_to(message, "I don't understand this message") # echo the message

bot.polling() # start polling for updates





if __name__ == "__main__":
    

    la = LawAgent()
    la.run("Wie schnell darf ich auf der Autobahn fahren?")
    la.run("Wie lange darf ein sich ein 15 jähriger in der Nacht auf der Straße aufhalten?")


    print("...done")


