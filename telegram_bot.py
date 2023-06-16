import os
import telebot

BOT_TOKEN = os.environ.get('BOT_TOKEN') # get your bot token from the .env file
bot = telebot.TeleBot(BOT_TOKEN) # create a bot instance

@bot.message_handler(commands=['start', 'hello']) # handle /start and /hello commands
def send_welcome(message):
    bot.reply_to(message, "Hello, I'm a telegram bot written in python.") # reply to the message

@bot.message_handler(func=lambda msg: True) # handle all other messages
def echo_all(message):
    bot.reply_to(message, "You said: " + message.text) # echo the message

bot.polling() # start polling for updates
