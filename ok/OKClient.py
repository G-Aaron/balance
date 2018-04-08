import sys
import importlib

sys.path.append("/home/balance")
importlib.reload(sys)

import time
import configparser
import api.OkexClient as OkexClient
import random
import json

# read config
config = configparser.ConfigParser()
config.read("config.ini")

OkexClient.get_account_info()

symbol = OkexClient.SYMBOL_OKB
transaction = float(config.get("trade", "transaction"))
currentBase = float(config.get("trade", "currentBase"))
percentage = float(config.get("trade", "percentage"))


def order_process(my_order_info):
    my_order_info.set_amount(my_order_info.get_unhandled_amount())
    state = OkexClient.trade(my_order_info)
    if my_order_info.amount < 1 and state == 2:
        OkexClient.write_log(my_order_info)
    elif my_order_info.dealAmount > 0:
        my_order_info.set_price(0)
        order_process(my_order_info)


def reOrgHistory(my_order_info):
    history_list = []
    history = ""
    try:
        history = config.get("trade", "history")
    except Exception as err:
        print(err)
    if history != "":
        history_list = json.loads(history)
    history_list.insert(0, my_order_info.__dict__)
    if len(history_list) > 5:
        history_list.pop()
    return json.dumps(history_list)


ret = round(random.uniform(0.01 * percentage, 0.1 * percentage), 3)
num = random.randint(1, 10)
if num > 5:
    ret = -ret
nextBuy = round(currentBase * (100 - percentage - ret) * 0.01, 4)
nextSell = round(currentBase * (100 + percentage - ret) * 0.01, 4)

while True:
    try:
        OkexClient.get_coin_price(symbol)
        priceInfo = OkexClient.priceInfo
        buyPrice = priceInfo[symbol]["buy"]
        buyAmount = priceInfo[symbol]["buyAmount"]
        sellPrice = priceInfo[symbol]["sell"]
        sellAmount = priceInfo[symbol]["sellAmount"]
        print('\nBase:', currentBase, ",Buy:", nextBuy, ',Sell:', nextSell,
              '|buy1:', buyPrice, '(+', round(nextSell - buyPrice, 4), ')',
              ',sell1:', sellPrice, '(', round(nextBuy - sellPrice, 4), ')',
              )
        orderInfo = {}
        if nextBuy >= sellPrice and sellAmount >= transaction:
            buyOrder = OkexClient.MyOrderInfo(symbol, OkexClient.TRADE_BUY, sellPrice, transaction)
            orderInfo = buyOrder
        elif nextSell <= buyPrice and buyAmount >= transaction:
            sellOrder = OkexClient.MyOrderInfo(symbol, OkexClient.TRADE_SELL, buyPrice, transaction)
            orderInfo = sellOrder
        if orderInfo != {}:
            order_process(orderInfo)
            if orderInfo.amount < 1:
                currentBase = round(orderInfo.avgPrice, 4)
                config.read("config.ini")
                config.set("trade", "currentBase", str(currentBase))
                config.set("trade", "history", str(reOrgHistory(orderInfo)))
                fp = open("config.ini", "w")
                config.write(fp)
                fp.close()
                ret = round(random.uniform(0.01 * percentage, 0.1 * percentage), 3)
                num = random.randint(1, 10)
                if num > 5:
                    ret = -ret
                nextBuy = round(currentBase * (100 - percentage - ret) * 0.01, 4)
                nextSell = round(currentBase * (100 + percentage - ret) * 0.01, 4)
    except Exception as err:
        print(err)
    time.sleep(0.1)
