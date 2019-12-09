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
import requests
import asyncio
from jsonrpc_websocket import Server, ProtocolError

endpoint_url = 'wss://testapi.megafon.ru/v1/api'
megafon = None
activeSessions = None
sessions = None
call = None

user_token = None
user_login = None
user_password = None

def get_file(fname):
    global user_login,user_password

    records_url = "http://testapi.megafon.ru/media/records/"
    print("Получаю запись {0}".format(fname))
    if(user_login and user_password):
        r = requests.get(records_url+fname,auth=(user_login,user_password))
    elif(user_token):
        r = requests.get(records_url+fname,headers={'Authorization':'JWT '+user_token})
    open(fname,'wb').write(r.content)

async def setSubscribedEvents(call_session):
    subsd = dict.fromkeys(["voiceActivity","soundQuality"],True)
    # Будем ловить события наличия голоса в медиапотоке и качества звука через SubscribeForEvents(). Эти события
    # не приходят автоматически
    subs_events = await megafon.eventSubscribe(call_session=call_session,events=subsd)
    print('Подписан на события {0}'.format(subs_events['message']))

def call_accepted(call_session):
    print("Вызов {0} разрешен. Играю КПВ для {1}...".format(call_session,sessions[call_session]))
    asyncio.get_event_loop().create_task(setSubscribedEvents(call_session))

def call_answered(call_session):
    global activeSessions
    print("Вызов {0} принят".format(call_session))
    activeSessions[call_session].set()                
    asyncio.get_event_loop().create_task(play_before_trombone(call_session))

# Возможные значения возвращаемых кодов ISUP и их смысл можно найти, например, в RFC3398 (стр. 25)
def call_rejected(call_session,sipCode,cause,message):    
    print("Вызов {0} отклонен по причине SIP={1}, ISUP={2} с сообщением {3}".format(call_session,sipCode,cause,message))    
    call_terminated(call_session,sipCode,cause,message)

def call_terminated(call_session,sipCode,cause,message):
    global call
    print('Вызов {0} завершен с кодом SIP={1}, ISUP={2} и сообщением {3}'.format(call_session,sipCode,cause,message))
    call.set()    

def record_completed(call_session, record_id, sequence_number, filename, dtmf):
    print('Запись {0} для {1} в файле {2} завершена. Нажата клавиша {3}'.format(sequence_number,record_id,filename,dtmf))
    get_file(filename)

def fragment_completed(call_session, record_id, sequence_number, filename, silence):
    print('Фрагмент {0} для {1} в файле {2} завершен. Закрыто по тишине? {3}'.format(sequence_number,record_id,filename,silence))
    get_file(filename)    

def detect_silence(call_session):
    print('В сессии {0} для {1} нет голоса более 1 секунды'.format(call_session,sessions[call_session]))

def detect_sound(call_session):
    print('В сессии {0} для {1} появился голос'.format(call_session,sessions[call_session]))

async def callDestination(destination):
    global sessions,call
    response = await megafon.callMake(bnum=destination)
    sessions.update({response['data']['call_session']:destination})
    return response['data']['call_session']

async def play_before_trombone(call_session):
    global activeSessions
    await megafon.callTonePlay(call_session=call_session,tone_id="500",repeat=True)
#    await megafon.callFilePlay(call_session=call_session,filename='stay_connected.pcm',timeout=100,dtmf_term="#")    


async def main(login=None,password=None,token=None,destinations=None):
    global megafon
    global sessions
    global activeSessions
    global call
    global user_token,user_login,user_password

    # Создаем соединение с сетью и аутентифицируемся
    if (token):
        megafon = Server(endpoint_url, headers={'Authorization':'JWT '+token})
        user_token = token
    elif (login and password):
        megafon = Server(endpoint_url, auth=aiohttp.BasicAuth(login,password))
        user_login = login
        user_password = password

    megafon.onCallAccept = call_accepted
    megafon.onCallAnswer = call_answered
    megafon.onCallReject = call_rejected
    megafon.onCallTerminate = call_terminated
    megafon.onCallFragmentRecord = fragment_completed
    megafon.onCallRecord = record_completed
    megafon.onSilenceDetect = detect_silence
    megafon.onSoundDetect = detect_sound

    sessions = {}

    try:
        # Соединяемся и выставляем режим сохранения транзакций, если контроль за сессией исчезает
        await megafon.ws_connect()
        await megafon.setOptions(on_connection_lost="KEEP_ALIVE")
        call = asyncio.Event()

        # Устанаваливаем два плеча для "тромбона"
        callSessions = await asyncio.gather(*(callDestination(dest) for dest in destinations))
        activeSessions = dict((session, asyncio.Event()) for session in callSessions)
        # ждем, когда ОБА будут установлены (для этого используется gather())
        await asyncio.gather(*(event.wait() for event in activeSessions.values()))

        print('Обе сессии {0} и {1} установлены'.format(callSessions[0],callSessions[1]))
        call.clear()
        trom = await megafon.callTrombone(a_session=callSessions[0],b_session=callSessions[1])
        print('Тромбон сообщает: {0}'.format(trom['message']))

        rec = await megafon.callRecordingStart(call_session=callSessions[0],detect_silence=False,dtmf_term='#')
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
