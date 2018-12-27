#!/usr/bin/env python3

import sys
import asyncio
import aiohttp
from jsonrpc_websocket import Server

async def call(login=None, password=None, token=None, session=None, destination=None):
    url = 'ws://megafon.api/v0/api'
    api = None
    if (token):
        api = Server(url, headers={'Authorization':'JWT '+token}, session=session)
    elif (login and password):
        api = Server(url, auth=aiohttp.BasicAuth(login,password), session=session)
    try:
        await api.ws_connect()
        response = await api.MakeCall(bnum=destination)
        if response and response['data'] and response['data']['call_session']:
            response = await api.PlayAnouncement(call_session=response['data']['call_session'],filename='hello.pcm')
            await api.TerminateCall(call_session=response['data']['call_session'])
    except:
        print(sys.exc_info())
    finally:
        await api.close()
        await api.session.close()

async def main(login=None, password=None, token=None, destinations=None):
    tasks = []
    async with aiohttp.ClientSession() as session:
        for destination in destinations:
            tasks.append(call(login, password, token, session, destination))
        await asyncio.gather(*tasks)

if len(sys.argv) == 5:
    asyncio.get_event_loop().run_until_complete(main(login=sys.argv[1],password=sys.argv[2],destinations=[sys.argv[3],sys.argv[4]]))
elif len(sys.argv) == 4:
    asyncio.get_event_loop().run_until_complete(main(token=sys.argv[1],destinations=[sys.argv[2],sys.argv[3]]))
