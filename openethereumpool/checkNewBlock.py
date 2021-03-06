#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
import configparser
import telebot
import pymongo
import urllib3
import json
import os
from datetime import datetime

# Go to directory
directory = os.path.dirname(os.path.realpath(__file__))
os.chdir(directory)


# Request to API data
def requestAPI(argUrl):
    try:
        response = http.request('GET', argUrl)
        if response.status != 200:
            data_json = {"ok": False, "error_code": response.status, "description": response.data.decode('utf-8')}
        else:
            data_json = json.loads(response.data.decode('utf-8'))
        return data_json

    except Exception as e2:
        data_json = {"ok": False, "description": str(e2)}
        return data_json


# ---------- Settings Config ----------
conf = configparser.ConfigParser()
conf.read('conf/OpenEthereumPool.conf')
LOG = conf['BASIC']['pathLog']
TOKEN = conf['BASIC']['tokenBot']
MONGOCONNECTION = conf['BASIC']['connectMongoDB']
BLOCKSSTATS = conf['API']['blocksStats']
FILELOG = conf['BASIC']['fileLog']

# -------------------------------------
# ---------- Logging ----------
if not os.path.exists('log'):
    os.makedirs('log')

logger = logging.getLogger('checkNewBlock')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if FILELOG == "enabled":
    fh = logging.FileHandler(LOG)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

# -----------------------------

logger.info("--- Start CheckNewBlock ---")

# Object for TelegramBot
bot = telebot.TeleBot(TOKEN)

# Connect to DB
db = pymongo.MongoClient(MONGOCONNECTION).get_database()
usersCol = db.Users
blocksCol = db.Blocks

# Object for API request
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
http = urllib3.PoolManager()

# Search stats for blocks
res = requestAPI(BLOCKSSTATS)

# Check mature total blocks first time save in db
total_matured = int(res["maturedTotal"])
tmdb = blocksCol.find_one({'_id': "maturedTotal"})

if tmdb != None:
    total_matured_db = tmdb["maturedTotal"]
else:
    logger.debug("First time save maturedblock in db")

    total_matured_db = total_matured
    blocksCol.insert_one({'_id': "maturedTotal", "maturedTotal": total_matured})

    for block_matured in res["matured"]:
        blocksCol.insert_one(block_matured)


if res["immature"] is not None or total_matured > total_matured_db:

    if res["immature"] is not None:
        list_block = res["immature"]

    else:
        list_block = res["matured"]

    for block in list_block:

        hash = block["hash"]
        timestamp = block["timestamp"]
        difficulty = block["difficulty"]
        shares = block["shares"]
        uncle = block["uncle"]
        variance = int((shares/difficulty)*100)
        reward = 1e-18 * int(block["reward"])

        date = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S %d-%m-%Y")

        # We search if the new block has already been notified
        new_block = blocksCol.find_one({'hash': block["hash"]})
        logger.debug("Search block in db: {0}".format(block))

        if new_block == None:

            # Send notification to users with notification = true
            users = usersCol.find(
                {"$or": [{"notification_newblock": {"$exists": False}}, {"notification_newblock": True}]})

            for user in users:
                try:
                    if uncle == False:
                        message = "🌀 *New Block found!*\n\n*Variance*: `{0}%`\n*Reward*: `{1}`\n*Block Hash*: `{2}`".format(
                            variance, reward, hash)
                    else:
                        message = "🌀 *New Uncle found!*\n\n*Variance*: `{0}%`\n*Reward*: `{1}`\n*Block Hash*: `{2}`".format(
                            variance, reward, hash)

                    bot.send_message(chat_id=user["_id"], text=message, parse_mode='Markdown')
                    logger.debug("Send message to user: {0}".format(user["_id"]))

                except:
                    logger.error("Error send message to user: {0}".format(user["_id"]))

            # Save block in db
            blocksCol.insert_one(block)
            logger.debug("Save block in db: {0}".format(block))

    blocksCol.update_one({'_id': "maturedTotal"},{"$set": {"maturedTotal": total_matured}}, upsert=True)
            
