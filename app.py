import os

import telebot


from config import *
from law_agent import LawAgent



bot = telebot.TeleBot(os.environ["BOT_TOKEN"]) # create a bot instance

bot_commands = [
    "/new"
]

la = LawAgent()
# la.run("Wie schnell darf ich auf der Autobahn fahren?")
# la.run("Wie lange darf ein sich ein 15 jähriger in der Nacht auf der Straße aufhalten?")



@bot.message_handler(commands=bot_commands)
def send_welcome(message):

    # la.run("Wie schnell darf ich auf der Autobahn fahren?")


    # assert that command is valid
    assert message.text in bot_commands, f"Command {message.text} is not valid."


    # TODO: use reponse to refine question -> alignment between agent and user


    # TODO: la.run(question)


    # TODO: Format response/final_report
    





    bot.reply_to(message, "Hello, I'm a telegram bot written in python.")



@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    bot.reply_to(message, "I don't understand this message")








if __name__ == "__main__":

    bot.polling() # start listening for messages


    print("...done")


