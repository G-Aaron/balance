# -*- coding: utf-8 -*-
# encoding: utf-8

import configparser
import sys
import time
import datetime
from util.MyUtil import from_time_stamp
from util.Logger import logger
import api.okex_sdk_v3.spot_api as spot

# read config
configBase = configparser.ConfigParser()
config = configparser.ConfigParser()
configBase.read("../key.ini")
config.read("config.ini")

# init apikey,secretkey,passphrase
api_key = configBase.get("okex-v3", "API_KEY")
seceret_key = configBase.get("okex-v3", "SECRET_KEY")
passphrase = configBase.get("okex-v3", "PASSPHRASE")

# currentAPIV3
spotAPI = spot.SpotAPI(api_key, seceret_key, passphrase, True)

granularityDict = {
    "1min": 60,
    "3min": 180,
    "5min": 300,
    "15min": 900,
    "30min": 1800,
    "1hour": 3600,
    "2hour": 7200,
    "4hour": 14400,
    "6hour": 21600,
    "12hour": 43200,
    "1day": 86400,
    "1week": 604800,
}


class OkexClient(object):
    BALANCE_USDT = "usdt"
    BALANCE_T = ""

    SYMBOL_T = ""

    TRADE_BUY = "buy"
    TRADE_SELL = "sell"

    FILLED_STATUS = 'filled'
    CANCELLED_STATUS = 'cancelled'

    MIN_AMOUNT = 1
    ACCURACY = 4
    TRADE_WAIT_COUNT = 1

    # trade params
    mode = ""
    amount = 0
    transaction = 0
    currentBase = 0
    percentage = 0
    rateP = 0
    emailDay = 0
    buyRate = 1
    sellRate = 1

    # global variable
    accountInfo = {BALANCE_USDT: {"total": 0, "available": 0, "freezed": 0}}

    priceInfo = {"version": 0, SYMBOL_T: {"asks": [], "bids": []}}

    def get_coin_num(self, symbol):
        return self.accountInfo[symbol]["available"]

    @classmethod
    def make_order(cls, my_order_info):
        print(
            u'\n-------------------------------------------spot order------------------------------------------------')
        result = {}
        try:
            result = spotAPI.take_order(my_order_info.orderType, my_order_info.symbol, 2, my_order_info.price,
                                        my_order_info.amount)
        except Exception as e:
            print("***trade:%s" % e)
        if result is not None and result.get('result'):
            print("OrderId", result['order_id'], my_order_info.symbol, my_order_info.orderType, my_order_info.price,
                  my_order_info.amount, "  ", from_time_stamp(int(time.time())))
            return result['order_id']
        else:
            print("order failed！", my_order_info.symbol, my_order_info.orderType, my_order_info.price,
                  my_order_info.amount, round(my_order_info.price * my_order_info.amount, 3))
            return -1

    def check_order_status(self, my_order_info, wait_count=0):
        order_id = my_order_info.orderId
        order_result = {}
        try:
            order_result = spotAPI.get_order_info(my_order_info.orderId, my_order_info.symbol)
        except Exception as e:
            print("***orderinfo:%s" % e)
        if order_result is not None and order_result.get('order_id') == my_order_info.orderId:
            order = order_result
            order_id = order["order_id"]
            status = order["status"]
            filled_size = float(order["filled_size"])
            if filled_size > 0:
                my_order_info.set_deal_amount(filled_size)
                my_order_info.set_avg_price(float(order["filled_notional"]) / filled_size)
            if status == self.CANCELLED_STATUS:
                print("order", order_id, "canceled")
            elif status == 'open':
                if wait_count == self.TRADE_WAIT_COUNT:
                    print("timeout no deal")
                else:
                    print("no deal", end=" ")
                    sys.stdout.flush()
            elif status == 'part_filled':
                if wait_count == self.TRADE_WAIT_COUNT:
                    print("part dealed ", my_order_info.dealAmount)
                else:
                    print("part dealed ", my_order_info.dealAmount, end=" ")
                    sys.stdout.flush()
            elif status == self.FILLED_STATUS:
                print("order", order_id, "filled")
            elif status == 'canceling':
                print("order", order_id, "canceling")
            elif status == 'ordering':
                print("order", order_id, "ordering")
            return status
        else:
            print(order_id, "checkOrderStatus failed,try again.")
            return self.check_order_status(my_order_info, wait_count)

    def trade(self, my_order_info):
        if my_order_info.amount < self.MIN_AMOUNT:
            return 2
        if my_order_info.price == 0:
            my_order_info.set_price(self.get_trade_price(my_order_info.symbol, my_order_info.orderType))
        order_id = self.make_order(my_order_info)
        if order_id != -1:
            my_order_info.set_order_id(order_id)
            wait_count = 0
            status = 0
            avg_price_bak = my_order_info.avgPrice
            while wait_count < self.TRADE_WAIT_COUNT and status != self.FILLED_STATUS:
                status = self.check_order_status(my_order_info, wait_count)
                # time.sleep(0.1)
                wait_count += 1
                if wait_count == self.TRADE_WAIT_COUNT and status != self.FILLED_STATUS:
                    trade_price = self.get_trade_price(my_order_info.symbol, my_order_info.orderType)
                    if trade_price == my_order_info.price:
                        wait_count -= 1
            my_order_info.reset_total_deal_amount(my_order_info.dealAmount)
            if my_order_info.totalDealAmount > 0:
                if my_order_info.orderType == self.TRADE_SELL:
                    my_order_info.set_transaction("plus")
                else:
                    my_order_info.set_transaction("minus")
                my_order_info.set_avg_price(round(
                    ((my_order_info.totalDealAmount - my_order_info.dealAmount) * avg_price_bak
                     + my_order_info.dealAmount * my_order_info.avgPrice) / my_order_info.totalDealAmount, 4))
            return status
        else:
            return "failed"

    def get_coin_price(self, symbol):
        data = {}
        try:
            data = spotAPI.get_depth(symbol)
        except Exception as e:
            print("***depth:%s" % e)
        price_info = self.priceInfo[symbol]
        if data is not None and data.get("asks") is not None:
            price_info["asks"] = list(map(lambda x: list(map(lambda d: float(d), x)), data["asks"]))
            price_info["bids"] = list(map(lambda x: list(map(lambda d: float(d), x)), data["bids"]))
        else:
            self.get_coin_price(symbol)

    def get_price_info(self, symbol, depth):
        price_info = self.priceInfo[symbol]
        asks = price_info['asks']
        bids = price_info['bids']
        amount_buy_sum = 0
        trans_buy_sum = 0
        amount_sell_sum = 0
        trans_sell_sum = 0
        for i in range(depth):
            amount_buy_sum += bids[i][1]
            trans_buy_sum += bids[i][0] * bids[i][1]
            amount_sell_sum += asks[i][1]
            trans_sell_sum += asks[i][0] * asks[i][1]
        avg_buy = round(trans_buy_sum / amount_buy_sum, 4)
        avg_sell = round(trans_sell_sum / amount_sell_sum, 4)
        return bids[depth - 1][0], avg_buy, amount_buy_sum, asks[depth - 1][0], avg_sell, amount_sell_sum

    def get_trade_price(self, symbol, order_type):
        self.get_coin_price(symbol)
        if order_type == self.TRADE_BUY:
            return self.priceInfo[symbol]["asks"][0][0]
        else:
            return self.priceInfo[symbol]["bids"][0][0]

    def get_account_info(self):
        logger.info(
            u'---------------------------------------spot account info------------------------------------------------')
        try:
            accounts = ['USDT', self.BALANCE_T.upper()]
            for symbol in accounts:
                t_account = spotAPI.get_coin_account_info(symbol)
                if t_account.get('currency') == symbol:
                    logger.info("%s:balance %s available %s frozen %s", symbol, t_account["available"],
                                t_account["available"],
                                t_account["frozen"])
                else:
                    print("getAccountInfo Fail,Try again!")
                    self.get_account_info()
        except Exception as err:
            print(err)
            self.get_account_info()

    @classmethod
    def get_line_data(cls, data):
        return [float(data[1]), float(data[2]), float(data[3]), float(data[4]), float(data[5])]

    # (开,高,低,收,交易量)
    @classmethod
    def get_klines(cls, symbol, period, size):
        result = {}
        granularity = granularityDict[period]
        end_s = int("%0.0f" % datetime.datetime.utcnow().timestamp())
        start_s = end_s - granularity * size
        start = datetime.datetime.fromtimestamp(start_s).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end = datetime.datetime.fromtimestamp(end_s).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        try:
            result = spotAPI.get_kline(symbol, start, end, granularity)
        except Exception as e:
            print("***klines:%s" % e)
        if isinstance(result, list):
            return list(map(cls.get_line_data, result))[::-1]
        else:
            return cls.get_klines(symbol, period, size)