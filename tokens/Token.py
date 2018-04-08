import time
import configparser
import random
import json
import api.OrderInfo as OrderInfo

# read config
config = configparser.ConfigParser()
config.read("config.ini")


def order_process(client, my_order_info):
    my_order_info.set_amount(my_order_info.get_unhandled_amount())
    state = client.trade(my_order_info)
    if my_order_info.amount < client.MIN_AMOUNT and state == client.COMPLETE_STATUS:
        client.write_log(my_order_info)
    elif my_order_info.dealAmount > 0:
        my_order_info.set_price(0)
        order_process(client, my_order_info)


def load_history():
    history_list = []
    history = ""
    try:
        history = config.get("trade", "history")
    except Exception as _err:
        print(_err)
    if history != "":
        history_list = json.loads(history)
    return history_list


def re_org_history(my_order_info):
    history_list = load_history()
    history_list.insert(0, my_order_info.__dict__)
    if len(history_list) > 5:
        history_list.pop()
    return json.dumps(history_list)


def get_next_buy_sell_rate(client):
    seconds_now = int(time.time())
    history_list = load_history()
    trend_count = 0
    buy_sell_rate = 1, 1
    for history in history_list:
        if history["orderType"] == client.TRADE_BUY:
            trend_count += 1
        else:
            trend_count -= 1
        seconds_now_diff = seconds_now - history["triggerSeconds"]
        # <15min buy twice
        if trend_count == 2 and seconds_now_diff < 900:
            buy_sell_rate = 2, 1
        # <30min buy three times
        elif trend_count == 3 and seconds_now_diff < 1800:
            buy_sell_rate = 3, 1
        # <60min buy four times
        elif trend_count == 4 and seconds_now_diff < 1800:
            buy_sell_rate = 4, 1
        # <60min buy five times
        elif trend_count == 5 and seconds_now_diff < 1800:
            buy_sell_rate = 5, 1
        # <15min sell twice
        elif trend_count == -2 and seconds_now_diff < 900:
            buy_sell_rate = 1, 2
        # <30min sell three times
        elif trend_count == -3 and seconds_now_diff < 1800:
            buy_sell_rate = 1, 3
        # <60min sell four times
        elif trend_count == -4 and seconds_now_diff < 1800:
            buy_sell_rate = 1, 4
        # <60min sell five times
        elif trend_count == -5 and seconds_now_diff < 1800:
            buy_sell_rate = 1, 4
    return buy_sell_rate


def get_next_buy_sell_info(client):
    amount = float(config.get("trade", "amount"))
    percentage = float(config.get("trade", "percentage"))
    current_base = float(config.get("trade", "currentbase"))
    buy_rate, sell_rate = get_next_buy_sell_rate(client)
    _ret = round(random.uniform(0.01 * percentage, 0.1 * percentage), 3)
    _num = random.randint(1, 10)
    if _num > 5:
        _ret = -_ret
    _next_buy = round(current_base * (100 - percentage * buy_rate - _ret) * 0.01, 4)
    _next_sell = round(current_base * (100 + percentage * sell_rate - _ret) * 0.01, 4)
    _next_buy_amount = amount * buy_rate
    _next_sell_amount = amount * sell_rate
    return _next_buy, _next_buy_amount, _next_sell, _next_sell_amount


def __main__(client, symbol):
    current_base = float(config.get("trade", "currentbase"))
    min_amount = float(config.get("trade", "minamount"))
    client.get_account_info()
    counter = 0
    next_buy, next_buy_amount, next_sell, next_sell_amount = get_next_buy_sell_info(client)
    while True:
        try:
            if counter > 300:
                next_buy, next_buy_amount, next_sell, next_sell_amount = get_next_buy_sell_info(client)
                counter = 0
            client.get_coin_price(symbol)
            buy_price, buy_amount, sell_price, sell_amount = client.get_price_info(symbol)
            print('\nBase:', current_base, ",Buy:", next_buy, ',Sell:', next_sell,
                  '|buy1:', buy_price, '(+', round(next_sell - buy_price, 4), ')',
                  ',sell1:', sell_price, '(', round(next_buy - sell_price, 4), ')',
                  )
            order_info = {}
            if next_buy >= sell_price and sell_amount >= next_buy_amount:
                buy_order = OrderInfo.MyOrderInfo(symbol, client.TRADE_BUY, sell_price, next_buy_amount)
                order_info = buy_order
            elif next_sell <= buy_price and buy_amount >= next_sell_amount:
                sell_order = OrderInfo.MyOrderInfo(symbol, client.TRADE_SELL, buy_price, next_sell_amount)
                order_info = sell_order
            if order_info != {}:
                order_process(client, order_info)
                if order_info.amount < min_amount:
                    current_base = round(order_info.avgPrice, 4)
                    config.read("config.ini")
                    config.set("trade", "currentBase", str(current_base))
                    config.set("trade", "history", str(re_org_history(order_info)))
                    fp = open("config.ini", "w")
                    config.write(fp)
                    fp.close()
                    next_buy, next_buy_amount, next_sell, next_sell_amount = get_next_buy_sell_info(client)
        except Exception as err:
            print(err)
        time.sleep(0.1)
        counter += 1
