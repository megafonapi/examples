#!/usr/bin/env python3

import sys
import asyncio
import aiohttp
from jsonrpc_websocket import Server

async def main(login=None, password=None, token=None, one=None, two=None):
    url = 'ws://megafon.api/v0/api'
    api = None
    if (token):
        api = Server(url, headers={'Authorization':'JWT '+token})
    elif (login and password):
        api = Server(url, auth=aiohttp.BasicAuth(login,password))
    try:
        await api.ws_connect()
        cnf_session = await api.CreateConf(max_participants=2)
        one_session = await api.MakeCall(bnum=one)
        two_session = await api.MakeCall(bnum=two)
        await api.AddToConf(conf_session=cnf_session['data']['conf_session'], call_session=one_session['data']['call_session'])
        await api.AddToConf(conf_session=cnf_session['data']['conf_session'], call_session=two_session['data']['call_session'])
    except:
        print(sys.exc_info())
    finally:
        await api.close()
        await api.session.close()

if len(sys.argv) == 5:
    asyncio.get_event_loop().run_until_complete(main(login=sys.argv[1],password=sys.argv[2],one=sys.argv[3],two=sys.argv[4]))
elif len(sys.argv) == 4:
    asyncio.get_event_loop().run_until_complete(main(token=sys.argv[1],one=sys.argv[2],two=sys.argv[3]))
