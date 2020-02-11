#!/usr/bin/env python3
#-*-coding: utf-8 -*-

# Программа создает конференцию и добавлят в нее абонентов по списку из 'destinations'. По каждому из номеров в
# этом файле осуществляется вызов, проигрывание приглашения и ожидания согласия (получения DTMF) на вход в конференцию.
# Между 20 и 30 секундой звонок на номер, указанный в mute_number будет заглушен.
# Осуществляется мониторинг состояния конференции и запись разгоров в файлы.
#
# Все вызовы происходят в параллельном режиме, для чего используется только механика "Питона" (пакет asyncio)

# Полезное руководство о том, что такое asyncio в Питоне и как им пользоваться. Для работы с МегаФон.API это
# ключевой инструмент, поскольку рабата с сетью связи по своей природе асинхронна
# https://realpython.com/async-io-python/
# и раздел документации по самому пакету на 
# https://docs.python.org/3/library/asyncio.html
# Для удобства работы будем использовать пакет 'jsonrpc_websocket', который позволяет сильно упростить синтаксис
# работы с JSON-RPC 

import sys
import aiohttp
import asyncio
from jsonrpc_websocket import Server, ProtocolError

# Для удобства работы вводим класс 'Call', описывающий звонок (сессию, номер B и события, связанные с этим звонком) 
class Call:
    def __init__(self, session,bnumber):
        self.session = session
        self.bnumber = bnumber
        self.answered = asyncio.Event()
        self.agreed = asyncio.Event()
        self.terminated = asyncio.Event()
        # ...
        # можно добавить что-нибудь еще, например, время входа в конференцию и выхода из нее 

endpoint_url = 'wss://testapi.megafon.ru/v1/api'
megafon = None
confId = None
mute_session = None
activeCalls = {}

# Тут можно написать номер, сессия которого будет заглушена на 10 секунд (например, mute_number = '79281234567')
mute_number = None

def call_accepted(call_session):
    global activeCalls
    print("Вызов {0} на номер {1} разрешен. Играю КПВ...".format(call_session,activeCalls[call_session].bnumber))

def call_answered(call_session):
    global activeCalls    
    print("Вызов {0} на номер {1} принят".format(call_session,activeCalls[call_session].bnumber))
    # Вызов принят: ставим флаг и запускаем проигрывать приветствие 
    activeCalls[call_session].answered.set()
    asyncio.get_event_loop().create_task(play(call_session))

def no_digits(call_session):
    global activeCalls 
    print("Вызов {0} на номер {1} не дал согласия".format(call_session,activeCalls[call_session].bnumber))
    # Раз согласия нет - принудительно завершить вызов 
    asyncio.get_event_loop().create_task(terminate_call(call_session))

def collected(call_session, dtmf):
    global activeCalls    
    print("Вызов {0} на номер {1} нажал: {2}".format(call_session,activeCalls[call_session].bnumber, dtmf))
    # Чего-то нажал - идём в конференцию. Не нажал - логика уйдёт в no_digits()    
    activeCalls[call_session].agreed.set()
    asyncio.get_event_loop().create_task(enterConf(call_session))

# Возможные значения возвращаемых кодов ISUP и их смысл можно найти, например, в RFC3398 (стр. 25)
def call_rejected(call_session,sipCode,cause,message):
    print("Вызов {0} на номер {1} отклонен по причине SIP={2}, ISUP={3} и сообщением {4}".format(call_session,activeCalls[call_session].bnumber,sipCode,cause,message))    
    call_terminated(call_session,sipCode,cause,message)

def call_terminated(call_session,source,cause,message):
    global activeCalls
    activeCalls[call_session].terminated.set()
    print("Вызов {0} на номер {1} завершен по причине SOURCE={2}, ISUP={3} и сообщением {4}".format(call_session,activeCalls[call_session].bnumber,source,cause,message))

def conf_record_fragment(conf_session, record_id, sequence_number, filename):
    print("Conference record fragment [{0}]: {1}".format(sequence_number, filename))

def conf_record_stop(conf_session, record_id, sequence_number, filename):
    print("Conference record stop [{0}]: {1}".format(sequence_number, filename))

async def terminate_call (call_session):
    resp1 = await megafon.callTerminate(call_session=call_session)
    print('Вызов {0} принудительно завершен. Статус завершения: {1}'.format(call_session,resp1['message']))

async def confStatus(conferenceId):
    global mute_number,mute_session
    
    await megafon.confRecordingStart(conf_session = conferenceId)
    # раз в пять секунд смотрим, сколько длится конференция и сколько в ней участников
    m=0
    while True:
        resp2 = await megafon.confStatusGet(conf_session = conferenceId)
        duration = int(resp2['data']['duration'])
        print('Конференция длится {0} секунд, в ней {1} участников'.format(duration,resp2['data']['participant_count']))
        if mute_session != None and 20 <= duration <= 30:            
            if m == 0:
                rm = await megafon.confConfereeMute(call_session=mute_session)
                print('Сессия {0} на {1} заглушена: {2}'.format(mute_session,mute_number,rm['message']))
                m=1
        else:
            if m == 1:
                rm = await megafon.confConfereeUnmute(call_session=mute_session)
                print('Сессия {0} на {1} восстановлена: {2}'.format(mute_session,mute_number,rm['message']))        
                m=0   
        await asyncio.sleep(5)

async def enterConf(call_session):
    await megafon.confAdd(call_session=call_session, conf_session=confId)

async def leaveConf(call_session):
    await megafon.confRemove(call_session=call_session, conf_session=confId)
    # тут по правилам надо бы удалять call_session из activeCalls и завершать эту сессию

async def play(call_session):
    await megafon.callFilePlay(call_session=call_session,filename='conference.pcm',timeout=100,dtmf_term="#")

async def callDestination(destination):
    global megafon,activeCalls
    global mute_number,mute_session
    response = await megafon.callMake(bnum=destination)
    session = response['data']['call_session']
    if destination == mute_number:
        mute_session = session
        print('Будем глушить сессию {0} на {1}'.format(mute_session,mute_number))
    outgoingCall = Call(session,destination)
    activeCalls[session] = outgoingCall
    return session

async def main(login=None,password=None,token=None,destinations=None):
    global megafon, activeCalls, confId

    # Создаем соединение с сетью и аутентифицируемся
    if (token):
        megafon = Server(endpoint_url+"/"+token)
    else:
        sys.exit(1)

    # Работа с сетью имеет четко "событийный" характер, поэтому на каждое из возможных в сценарии событий необходимо 
    # определить свой callback
    megafon.onCallAccept = call_accepted
    megafon.onCallAnswer = call_answered
    megafon.onCallFilePlay = no_digits
    megafon.onDTMFCollect = collected
    megafon.onCallReject = call_rejected
    megafon.onCallTerminate = call_terminated
    megafon.onConfFragmentRecord = conf_record_fragment
    megafon.onConfRecord = conf_record_stop

    try:
        # Соединямся и создаем конференцию
        await megafon.ws_connect()
        response = await megafon.confMake()
        confId = response['data']['conf_session']
        print('Конференция {0} создана...'.format(confId))

        # Запускаем мониторинг количества участников конференции
        confStatusTask = asyncio.get_event_loop().create_task(confStatus(confId))

        # Читаем файл с номерами (убираем '\n' в конце каждой строки), пишем номера в список,
        # после чего поднимаем все звонковые сессии одновременно        
        dest_list = [line.rstrip('\n') for line in open(destinations)]
        callSessions = await asyncio.gather(*(callDestination(dest) for dest in dest_list))

        # Начинаем мониторить события завершения всех сессий
        await asyncio.gather(*(activeCalls[s].terminated.wait() for s in callSessions))

        # Останавливаем запись конференции и отключаем Интернет-поток
        await megafon.confRecordingStop(conf_session = confId)

        # Останавливаем мониторинг количества участников
        confStatusTask.cancel()
    except:
        print(sys.exc_info())

    await megafon.close()
    await megafon.session.close()

if len(sys.argv) == 3:
    asyncio.get_event_loop().run_until_complete(main(token=sys.argv[1],destinations=sys.argv[2]))
else:
    print(f"Необходимый формат: {sys.argv[0]} <token> <файл со списком номеров>")
    sys.exit(1)
