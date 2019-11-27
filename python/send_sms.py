#!/usr/bin/env python3
#-*-coding: utf-8 -*-

# Эта программа осуществляет рассылку SMS-сообщений. Номера телефонов берутся из файла, задаваемого в
# командной строке.
# Рассылать сообщения будем в виде flash sms, для чего используется data_coding=24
# Другие значения можно найти на https://en.wikipedia.org/wiki/Data_Coding_Scheme
# Рекомендуется ознакомиться с протоколом SMPP v3.4 для понимания смысла параметров, передаваемых методу SendSMS
# Кроме того, ОБЯЗАТЕЛЬНО необходимо анализировать коды возврата SMPP в случае ошибок
# Например, код 88 (0x58) означает превышение лимита на пропускную способность канала
# Табличку с кодами можно, например, найти на https://help.nexmo.com/hc/en-us/articles/204015763-SMPP-Error-Codes
# но лучше все же почитать про SMPP

# Полезное руководство о том, что такое asyncio в Питоне и как им пользоваться. Для работы с МегаФон.API это
# ключевой инструмент, поскольку рабата с сетью связи по своей природе асинхронна
# https://realpython.com/async-io-python/
# и раздел документации по самому пакету на 
# https://docs.python.org/3/library/asyncio.html
# Для удобства работы будем использовать пакет 'jsonrpc_websocket', который  сильно упростить синтаксис
# работы с JSON-RPC 

import sys
import aiohttp
import asyncio
from jsonrpc_websocket import Server,ProtocolError

endpoint_url = 'wss://testapi.megafon.ru/v1/api'
megafon = None

def sms_delivered(sms_id, status):
    print("SMS {0} delivered with status {1}".format(sms_id, status))
    asyncio.get_event_loop().create_task(close())

async def close():
    await megafon.close()
    await megafon.session.close()
    asyncio.get_event_loop().stop()

async def main(login=None,password=None,token=None,destinations=None):
    global megafon

    # Создаем соединение с сетью и аутентифицируемся
    if (token):
        megafon = Server(endpoint_url, headers={'Authorization':'JWT '+token})
    elif (login and password):
        megafon = Server(endpoint_url, auth=aiohttp.BasicAuth(login,password))

    megafon.onSMSDelivery = sms_delivered

    try:
        await megafon.ws_connect()
        with open(destinations,'r') as phones:
            for bnumber in phones:
                bnumber = bnumber.rstrip('\n')
                response = await megafon.smsSend(bnum=bnumber, message='Кожанные мешки, я МегаФон.API',type='TEXT',data_coding=24)
                print(response)
                print("Response sms_id: {0}. Status {1}".format(response['data']['sms_id'],response['data']['status']))
    except ProtocolError as e:
        print(e)
        print('Сообщение не отправлено. SMPP-код {0}'.format(e.args[2]['error']['code']))

    asyncio.get_event_loop().create_task(close())

if len(sys.argv) == 4:
    asyncio.get_event_loop().run_until_complete(main(login=sys.argv[1],password=sys.argv[2],destinations=sys.argv[3]))
elif len(sys.argv) == 3:
    asyncio.get_event_loop().run_until_complete(main(token=sys.argv[1],destinations=sys.argv[2]))

