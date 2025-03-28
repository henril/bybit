#!/bin/python

import socket
import time
import random
import requests
from json import dumps as json_dumps, loads as json_loads
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
import logging
import sys

logger = logging.getLogger(__name__)

def queryAllPaymentList():
    headers = {
        'cache-control': 'no-cache',
        'content-length': '0',
        'content-type': 'application/x-www-form-urlencoded'
    }

    resp = requests.post('https://api2.bybit.com/fiat/otc/configuration/queryAllPaymentList',
                         headers=headers)
    
    return resp.json()['result']

def queryOnline(params):
    data = {
        "userId":"",
        "canTrade": params.get('canTrade', ['1'])[0] == '1',
        "tokenId": params.get('tokenId', ["USDT"])[0],
        "currencyId":params.get('currencyId', ["RUB"])[0],
        "payment": params.get('payment', ["64","585"]),
        "side":"0",
        "size":"100",
        "page":"1",
        "amount": params.get('amount', ["30000"])[0],
        "vaMaker":False,
        "bulkMaker":False,
        "verificationFilter":0,
        "sortType":"TRADE_PRICE",
        "paymentPeriod":[],
        "itemRegion":1
    }

    headers = {
        'content-type': 'application/json;charset=UTF-8'
    }

    if 'secure-token' in params:
        headers['Cookie'] = f'secure-token={params["secure-token"][0]}'

    resp = requests.post('https://api2.bybit.com/fiat/otc/item/online',
        headers=headers,
        json=data)
    
    if resp.json()['ret_code'] != 0:
        raise resp.text

    return resp.json()['result']['items']

def row_user_url(row):
    return f'https://www.bybit.com/en/fiat/trade/otc/profile/{row["userMaskId"]}/USDT/RUB/item'

def humanizeUnixtime(unixtime):
    return datetime.utcfromtimestamp(unixtime).strftime('%H:%M')

def offlineSince(unixtime):
    return f'offline ({int((time.time()) - unixtime) // 60} mins)'

def make_row(row):
    #print(row)
    return f"""
    <tr class="tr-data">
        <td><a target="_blank" rel="noopener noreferrer" href="{row_user_url(row)}">{row['nickName']}</a></td>
        <td style="color: {'green' if row['isOnline'] else 'orange'}">{'online' if row['isOnline'] else offlineSince(int(row['lastLogoutTime']))}
        <td>{row['price']}</td>
        <td>{row['minAmount']} - {row['maxAmount']}</td>
        <td>{row['remark']}</td>
    </tr>
    """

def make_rows(data):
    return '\n'.join([make_row(row) for row in data])

def make_html(data):
    with open('template.html') as f:
        template = f.read()
        return template.replace('<!--%TABLE_BODY%-->', make_rows(data))

def only_eligible(data, params):
    tests = [
        {'key': 'completeRateDay30', 'enableKey': 'hasCompleteRateDay30'},
        {'key': 'orderFinishNumberDay30', 'enableKey': 'hasOrderFinishNumberDay30'}
    ]

    eligibles = []

    for item in data:
        prefs = item['tradingPreferenceSet']
        eligible = True
        if prefs is not None:
            for test in tests:
                if test['key'] in params and prefs[test['enableKey']] == 1:
                    if int(params[test['key']][0]) < int(prefs[test['key']]):
                        eligible = False
                        break
        if eligible:
            eligibles.append(item)
    return eligibles
        

def make_response(params):
    data = queryOnline(params)
    # with open('onlinemini.json') as f:
    #     data = json_loads(f.read())

    with open('last_response.txt', 'w') as f:
        f.write(json_dumps(data))

    eligible_data = only_eligible(data, params)

    return ('HTTP/1.1 200 OK\r\n'
            'Content-Type: text/html\r\n\r\n'
            f'{make_html(eligible_data)}')

def http_error(message=''):
    return (f'HTTP/1.1 500\r\n'
            f'Content-Type: text/html\r\n\r\n'
            f'{message}')

def start_listening(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(5)
    logger.info(f'Listening on {host}:{port}')
    return s

def serve_forever(sock):
    while True:
        try:
            client, addr = sock.accept()

            logger.info(f'Connection from {addr}')

            request = client.recv(9999).decode(encoding='utf-8')

            logger.info(request.splitlines()[0])

            location = request.splitlines()[0].strip().split()[1]
            params = parse_qs(urlparse(location).query)

            response = make_response(params)
            client.send(response.encode(encoding='utf-8'))
            client.close()
        except Exception as e:
            logger.error(e, exc_info=True)
            client.send(http_error('Unable to serve. Check all parameters.').encode(encoding='utf-8'))
            client.close()
            continue
        

def main():
    logging.basicConfig(filename='bybit.log', level=logging.DEBUG, format='%(asctime)s %(message)s')
    logger.addHandler(logging.StreamHandler(sys.stdout))
    socket = start_listening('127.0.0.1', 8889)
    serve_forever(socket)

if __name__ == '__main__':
    main()
