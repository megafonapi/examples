#!/usr/bin/python3
#-*-coding: utf-8 -*-

# Программа осуществляет последовательный обзвон по списку в файле 'destinations', задаваемому в
# командной строке, проигрывает сообщение и ждет завершения вызова от вызывающего абонента.
# После этого продолжает дальше по списку

# Полезное руководство о том, что такое asyncio в Питоне и как им пользоваться. Для работы с МегаФон.API это
# ключевой инструмент, поскольку рабата с сетью связи по своей природе асинхронна
# https://realpython.com/async-io-python/
# и раздел документации по самому пакету на 
# https://docs.python.org/3/library/asyncio.html
# Для удобства работы будем использовать пакет 'jsonrpc_websocket', который позволяет сильно упростить синтаксис
# работы с JSON-RPC 

import sys
import json
import aiohttp
import asyncio
from jsonrpc_websocket import Server, ProtocolError

endpoint_url = 'wss://testapi.megafon.ru/v1/api'
play_file = 'testing.pcm'
megafon = None

terminated_ev = None
flow_ev = None

sessions = None

def call_accepted(call_session):
    # flow_ev.set() поставим ПОСЛЕ того, как абонент возмет трубку, не ранее, поэтому не здесь
    print("Вызов {0} на номер {1} разрешен. Играю КПВ...".format(call_session,sessions[call_session]))

def call_answered(call_session):
    global flow_ev
    global sessions
    print("Вызов {0} на номер {1} принят".format(call_session,sessions.get(call_session)))
    flow_ev.set()
    
# Возможные значения возвращаемых кодов ISUP и их смысл можно найти, например, в RFC3398 (стр. 25)
def call_rejected(call_session,sipCode,cause,message):
    global flow_ev,terminated_ev    
    print("Вызов {0} отклонен по причине SIP={1}, ISUP={2} и сообщением {3}".format(call_session,sipCode,cause,message))
    # Пока поставим тут terminated_ev. Вообще можно разбираться, почему вызов отвергнут и действовать по обстоятельствам
    terminated_ev.set()
    flow_ev.set()

def call_terminated(call_session,sipCode,cause,message):
    global flow_ev,terminated_ev
    print('Вызов {0} завершен с кодом SIP={1}, ISUP={2} и сообщением {3}'.format(call_session,sipCode,cause,message))
    terminated_ev.set()
    flow_ev.set()

async def main(login=None,password=None,token=None,destinations=None):
    global megafon
    global flow_ev,terminated_ev
    global sessions

    # Создаем соединение с сетью и аутентифицируемся
    if (token):
        megafon = Server(endpoint_url, headers={'Authorization':'JWT '+token})
    elif (login and password):
        megafon = Server(endpoint_url, auth=aiohttp.BasicAuth(login,password))

    # В словарь 'sessions' будем записывать идентификатор сессии и вызываемый номер телефона (номер B). В данном
    # примере это нужно для того, чтобы показать номер телефона по идущей сессии
    sessions = {}

    # Работа с сетью имеет четко "событийный" характер, поэтому на каждое из возможных событий необходимо определить callback
    megafon.onCallAccept = call_accepted        # вызов может быть не разрешен (нет денег и т.п.), поэтому такое событие существует
    megafon.onCallAnswer = call_answered        # возникает, когда абонент B снял трубку
    megafon.onCallReject = call_rejected        # возникает при отбое (возвращается причина - занятно и т.п.)
    megafon.onCallTerminate = call_terminated   # возникает по завершению вызова

    try:
        await megafon.ws_connect()
        # Создаем два события: flow_ev это какое-либо событие в процессе вызова, за исключением terminated_ev, которое
        # мы ожудаем при завершении вызова (по нему надо окончить работу программы) 
        flow_ev = asyncio.Event()
        terminated_ev = asyncio.Event()
        with open(destinations,'r') as phones:
            for bnumber in phones:
                bnumber = bnumber.rstrip('\n')
                print('Звоню на {0}... '.format(bnumber))
                # запустили звонилку и ждем, пока не вывалится какое-либо событие. Внутри callback'а на
                # событие flow_ev будет установлен флаг и работа программы должна продолжиться дальше
                calling = await megafon.callMake(bnum=bnumber)
                sessions.update({calling['data']['call_session']:bnumber})
                await flow_ev.wait()

                # если звонок был отбит или завершен, внутри соответствующего callback'а будет установлен terminated_ev и значит выходим
                if terminated_ev.is_set():
                    return

                flow_ev.clear()
                #await megafon.callTonePlay(call_session=calling['data']['call_session'],tone_id="800",repeat=True)
                await megafon.callFilePlay(call_session=calling['data']['call_session'],filename=play_file,timeout=100,dtmf_term='#')
                await flow_ev.wait()

                # если звонок был отбит или завершен, внутри соответствующего callback'а будет установлен terminated_ev и значит выходим
                if terminated_ev.is_set():
                    return

                # просто ждем, пока абонент сам не отключится, после чего последует следующий оборот цикла
                await terminated_ev.wait()
        phones.close()
    except:
        print(sys.exc_info())
    finally:        
        await megafon.session.close()
        await megafon.close()
        print('Завершен последовательный обзвон по списку')

if len(sys.argv) == 4:
    asyncio.get_event_loop().run_until_complete(main(login=sys.argv[1],password=sys.argv[2],destinations=sys.argv[3]))
elif len(sys.argv) == 3:
    asyncio.get_event_loop().run_until_complete(main(token=sys.argv[1],destinations=sys.argv[2]))
