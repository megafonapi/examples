#!/usr/bin/env python3

import sys
import asyncio
import aiohttp
from jsonrpc_websocket import Server

api = None

def terminate(call_session):
    print('CALL {0} COMPLETED'.format(call_session))
    asyncio.get_event_loop().create_task(close())

async def close():
    await api.close()
    await api.session.close()
    asyncio.get_event_loop().stop()

def incoming(call_session, anum, bnum):
    print('CALL {0} : {1} => {2}'.format(call_session, anum, bnum))
    asyncio.get_event_loop().create_task(play_and_terminate(call_session))
    
async def play_and_terminate(call_session):
    await api.AnswerCall(call_session=call_session)
    await api.PlayAnouncement(call_session=call_session,filename='hello.pcm')
    await api.TerminateCall(call_session=call_session)

async def main(login=None, password=None, token=None):
    global api
    url = 'ws://127.0.0.127/v0/api'
    if (token):
        api = Server(url, headers={'Authorization':'JWT '+token})
    elif (login and password):
        api = Server(url, auth=aiohttp.BasicAuth(login,password))
    api.OnIncomingCall = incoming
    api.OnTerminateCall = terminate
    try:
        await api.ws_connect()
    except:
        print(sys.exc_info())

if len(sys.argv) == 3:
    asyncio.ensure_future(main(login=sys.argv[1],password=sys.argv[2]))
elif len(sys.argv) == 2:
    asyncio.ensure_future(main(token=sys.argv[1]))

asyncio.get_event_loop().run_forever()
