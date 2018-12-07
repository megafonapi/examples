#!/usr/bin/env python3

import sys
import asyncio
import aiohttp
from jsonrpc_websocket import Server

async def main(login=None, password=None, token=None, destination=None):
    url = 'ws://127.0.0.127/v0/api'
    api = None
    if (token):
        api = Server(url, headers={'Authorization':'JWT '+token})
    elif (login and password):
        api = Server(url, auth=aiohttp.BasicAuth(login,password))
    try:
        await api.ws_connect()
        response = await api.MakeCall(bnum=destination)
        if response and response['data'] and response['data']['call_session']:
            response = await api.PlayAnouncement(call_session=response['data']['call_session'],filename='record.pcm',timeout=100)
            pin = response['data']['dtmf'].replace('#','')
            print("PIN : {0}".format(pin))
            if (pin.isnumeric()):
                print("PIN is number, so recoding for {0} seconds".format(pin))
                record = await api.RecordCall(call_session=response['data']['call_session'], mode='nowait')
                print("RECORD : {0}".format(record))
                await asyncio.sleep(int(pin))
            else:
                print("PIN is not number")
            await api.TerminateCall(call_session=response['data']['call_session'])
    except:
        print(sys.exc_info())
    finally:
        await api.close()
        await api.session.close()

if len(sys.argv) == 4:
    asyncio.get_event_loop().run_until_complete(main(login=sys.argv[1],password=sys.argv[2],destination=sys.argv[3]))
elif len(sys.argv) == 3:
    asyncio.get_event_loop().run_until_complete(main(token=sys.argv[1],destination=sys.argv[2]))
