#!/usr/bin/python3
#-*-coding: utf-8 -*-

# Программа вызывает воздает два исходящих плеча в сторону двух абонентов, проигрывает сообщение и объединяет
# два этих плеча в один вызов (делает "тромбон"). Параллельно идет запись вызова.

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
megafon = None
activeSessions = None
sessions = None
call = None

def call_accepted(call_session):
    print("Вызов {0} разрешен. Играю КПВ для {1}...".format(call_session,sessions[call_session]))

def call_answered(call_session):
    global activeSessions
    print("Вызов {0} принят".format(call_session))
    activeSessions[call_session].set()                
    asyncio.get_event_loop().create_task(play_before_trombone(call_session))

# Возможные значения возвращаемых кодов ISUP и их смысл можно найти, например, в RFC3398 (стр. 25)
def call_rejected(call_session,sipCode,cause,message):    
    print("Вызов {0} отклонен по причине SIP={1}, ISUP={2} с сообщением {3}".format(call_session,sipCode,cause,message))    
    call_terminated(call_session,cause,message)

def call_terminated(call_session,cause,message):
    global call
    print('Вызов {0} завершен с кодом ISUP={1} и сообщением {2}'.format(call_session,cause,message))
    call.set()    

def record_completed(call_session, record_id, sequence_number, filename, dtmf):
    print('Запись {0} для {1} в файле {2} завершена. Нажата клавиша {3}'.format(sequence_number,record_id,filename,dtmf))

def fragment_completed(call_session, record_id, sequence_number, filename, silence):
    print('Фрагмент {0} для {1} в файле {2} завершен'.format(sequence_number,record_id,filename))

async def callDestination(destination):
    global sessions,call
    response = await megafon.MakeCall(bnum=destination)
    sessions.update({response['data']['call_session']:destination})
    return response['data']['call_session']

async def play_before_trombone(call_session):
    global activeSessions
    await megafon.PlayAnnouncement(call_session=call_session,filename='stay_connected.pcm',timeout=100,dtmf_term="#")    


async def main(login=None,password=None,token=None,destinations=None):
    global megafon
    global sessions
    global activeSessions
    global call

    # Создаем соединение с сетью и аутентифицируемся
    if (token):
        megafon = Server(endpoint_url, headers={'Authorization':'JWT '+token})
    elif (login and password):
        megafon = Server(endpoint_url, auth=aiohttp.BasicAuth(login,password))

    megafon.OnAcceptCall = call_accepted
    megafon.OnAnswerCall = call_answered
    megafon.OnRejectCall = call_rejected
    megafon.OnTerminateCall = call_terminated
    megafon.OnCallRecordFragment = fragment_completed
    megafon.OnStopCallRecord = record_completed

    sessions = {}

    try:
        await megafon.ws_connect()
        call = asyncio.Event()

        # Устанаваливаем два плеча для "тромбона"
        callSessions = await asyncio.gather(*(callDestination(dest) for dest in destinations))
        activeSessions = dict((session, asyncio.Event()) for session in callSessions)
        # ждем, когда ОБА будут установлены (для этого используется gather())
        await asyncio.gather(*(event.wait() for event in activeSessions.values()))

        print('Обе сессии {0} и {1} установлены'.format(callSessions[0],callSessions[1]))
        call.clear()
        trom = await megafon.TromboneCall(a_session=callSessions[0],b_session=callSessions[1])
        print('Тромбон сообщает: {0}'.format(trom['message']))

        rec = await megafon.StartCallRecord(call_session=callSessions[0],detect_silence=False,dtmf_term='#')
        print('Запись с идентификатором {0} начата'.format(rec['data']['record_id']))

        await call.wait()

    except:
        print(sys.exc_info())

    await megafon.close()
    await megafon.session.close()

if len(sys.argv) == 5:
    asyncio.get_event_loop().run_until_complete(main(login=sys.argv[1],password=sys.argv[2],destinations=sys.argv[3:]))
elif len(sys.argv) == 4:
    asyncio.get_event_loop().run_until_complete(main(token=sys.argv[1],destinations=sys.argv[2:]))
