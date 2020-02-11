#!/usr/bin/env python3
#-*-coding: utf-8 -*-

# Программа ожидает входящего вызова по аутентифицированному в МегаФон.API номеру. При поступлении такого
# вызова, она осуществляет исходящий вызов на указанный в командной строке номер и, по получении от обоих
# абонентов согласия, объединяет два плеча вызова в один (осуществляет "тромбон" вызова).

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

endpoint_url = 'wss://testapi.megafon.ru/v1/api'
megafon = None
newCall = None

incomingCall = None
outgoingCall = None

calls = {}

# переменная этого класса хранит сессию звонка с номерами телефонов и флаги трех событий, которые могут
# с этим звонком происходить: отвечен ли он, нажата ли кнопка (согласия на что-то) и завершился ли он
class Call:
    def __init__(self, session,anumber,bnumber):
        self.session = session
        self.anumber = anumber
        self.bnumber = bnumber
        self.answered = asyncio.Event()
        self.trombonAgree = asyncio.Event()
        self.terminated = asyncio.Event()

# функция срабатывает на событие возможности установки соединения - ведь вызов может быть отклонен,
# например, по причине недостатка денег на лицевом счете. После срабатывания этого события сеть обычно
# играет сигнал КПВ (гудки), ожидая ответа противоположной стороны
def accepted(call_session):
    print('Вызов {0} разрешен. Играю КПВ...'.format(call_session))

# функция срабатывает при отклонении возможности позвонить. В этом примере мы просто завершаем
# сеанс. В принципе, можем анализировать причины, почему звонок отклонен (в будущем)
# Возможные значения возвращаемых кодов ISUP и их смысл можно найти, например, в RFC3398 (стр. 25)
def rejected(call_session,sipCode,cause,message):    
    print("Вызов {0} отклонен по причине SIP={1}, ISUP={2} с сообщением {3}".format(call_session,sipCode,cause,message))       
    terminated(call_session,sipCode,cause,message)

# Если прилетает событие завершения сессии, говорим об этом и выставляем флаг события
def terminated(call_session,source,cause,message):
    global calls
    print('Вызов {0} завершен с кодом SOURCE={1}, ISUP={2} и сообщением {3}'.format(call_session,source,cause,message))
    calls[call_session].terminated.set()

# Если на звонок ответили, то пишем про это и выставляем флаг события 
def answered(call_session):
    global calls
    print('На вызов {0} ответили (сняли трубку)'.format(call_session))
    calls[call_session].answered.set()

# Если нажата клавиша, то показываем, что именно нажато и выставляем флаг события согласия
def collected(call_session, dtmf):
    global calls
    print('В процессе вызова {0} поступил код DTMF: {1}'.format(call_session, dtmf))
    calls[call_session].trombonAgree.set()

# Поступил новый вызов. Создаем переменную класса Call, которая содержит сессию вызова и флаги различных событий,
# связанных с нею. После этого записываем этот объект в словарь с ключом id сессии (входящих ведь может быть много)
# ну и ставим флажок в newCall, чтобы программа в main() продолжилась
def incoming(call_session, anum, bnum):
    global newCall, calls, incomingCall
    print('Входящий вызов по сессии {0} : номер A {1} => номер B {2}'.format(call_session, anum, bnum))
    incomingCall = Call(call_session,anum,bnum)
    calls[call_session] = incomingCall
    newCall.set()

# Делаем исходящий вызов. создаем 
async def callDestination(destination):
    global megafon, calls, outgoingCall
    response = await megafon.callMake(bnum=destination)
    session = response['data']['call_session']
    # пока в качестве anum поставим 'None': не охота доставать его из логина, особенно когда аутентификация по JWT
    outgoingCall = Call(session,None,destination)
    calls[session] = outgoingCall

async def main(login=None,password=None,token=None,destination=None):
    global megafon, newCall, calls, incomingCall, outgoingCall

   # Создаем соединение с сетью и аутентифицируемся
    if (token):
        megafon = Server(endpoint_url+"/"+token)
    else:
        sys.exit(1)

    # Вешаем callback'и на нужные нам события
    megafon.onCallIncoming = incoming
    megafon.onCallAccept = accepted
    megafon.onCallAnswer = answered
    megafon.onCallReject = rejected
    megafon.onDTMFCollect = collected
    megafon.onCallTerminate = terminated

    # это событие будет означать новый поступивший входящий вызов
    newCall = asyncio.Event()

    try:
        # соединились с сокетом и ждем поступившего звонка
        # когда он появится по событию OnCallIncoming, в callback-функции флаг в newCall будет выставлен
        # и исполнение программы продолжится 
        await megafon.ws_connect()
        await newCall.wait()

        # Ответили на звонок: "сняли трубку" и проиграли приглашение
        await megafon.callAnswer(call_session=incomingCall.session)
        #await megafon.callReject(call_session=incomingCall.session)
        await megafon.callFilePlay(call_session=incomingCall.session, filename='leather.pcm', dtmf_term='#', timeout=100)

        # Ждем либо завершения входящего звонка, либо согласия (нажатия на клавишу)
        incomingTerminated = asyncio.create_task(incomingCall.terminated.wait())
        incomingAgree      = asyncio.create_task(incomingCall.trombonAgree.wait())
        done, pending = await asyncio.wait([ incomingTerminated, incomingAgree ], return_when=asyncio.FIRST_COMPLETED)
        # Если входящий звонок завершен, то дальше нечего делать - выходим. Предварительно убъем остальное, чтобы не ругалась
        # на не завершённую задачу
        if incomingTerminated in done:
            for task in pending:
                task.cancel()
            return
        # Как только нажата клавиша завершаем оставшиеся ожидания (там, соответственно, incomingCall.terminated.wait()): ждать 
        # больше не надо, надо инициировать исходящий звонок на destination
        for task in pending:
            task.cancel()

        # делаем звонок и играем ему тоновый сигнал
        await callDestination(destination)
        await megafon.callTonePlay(call_session=incomingCall.session, tone_id="500")

        # Опять ждем: либо отбоя во входящм или исходящем плече, либо ответа на исходящий вызов
        incomingTerminated = asyncio.create_task(incomingCall.terminated.wait())
        outgoingAnswered   = asyncio.create_task(outgoingCall.answered.wait())
        outgoingTerminated = asyncio.create_task(outgoingCall.terminated.wait())
        # Если оба плеча отбились, то дальше нечего делать - завершаем
        done, pending = await asyncio.wait([ incomingTerminated, outgoingAnswered, outgoingTerminated ], return_when=asyncio.FIRST_COMPLETED)
        if not (outgoingAnswered in done):
           return
        # Завершаем оставшиеся ожидания и двигаемся дальше
        for task in pending:
           task.cancel()

        # Играем приветствие в исходящий вызов
        await megafon.callFilePlay(call_session=outgoingCall.session, filename='leather.pcm', dtmf_term='#', timeout=100)

        # и опять - ждем либо отбоя в обоих плечах, либо согласия (нажатия на клавишу)
        incomingTerminated = asyncio.create_task(incomingCall.terminated.wait())
        outgoingTerminated = asyncio.create_task(outgoingCall.terminated.wait())
        outgoingAgree      = asyncio.create_task(outgoingCall.trombonAgree.wait())
        # Если оба плеча отбились, то дальше делать нечего - завершаем
        done, pending = await asyncio.wait([ incomingTerminated, outgoingTerminated, outgoingAgree ], return_when=asyncio.FIRST_COMPLETED)
        if outgoingAgree not in done:
           return
        # Завершаем оставшиеся ожидания и двигаемся дальше
        for task in pending:
           task.cancel()

        # Объединяем оба плеча в один вызов ("тромбон") и оба абонента разговаривают
        await megafon.callTrombone(a_session=incomingCall.session, b_session=outgoingCall.session)
        # пока кто-то из них (в каком-либо из плеч не отбился)
        incomingTerminated = asyncio.create_task(incomingCall.terminated.wait())
        outgoingTerminated = asyncio.create_task(outgoingCall.terminated.wait())
        done, pending = await asyncio.wait([ incomingTerminated, outgoingTerminated ], return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
           task.cancel()
    except:
        print(sys.exc_info())

    finally:
        await megafon.close()
        await megafon.session.close()

if len(sys.argv) == 3:
    asyncio.get_event_loop().run_until_complete(main(token=sys.argv[1],destination=sys.argv[2]))
else:
    print(f"Необходимый формат: {sys.argv[0]} <token> <номер>")
    sys.exit(1)

