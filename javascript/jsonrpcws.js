class JsonRpcWs {

	constructor(url) {
		this.url = url;
		this.counter = 0;
		this.eventHandlers = {};
	}
	
	handle(method, handler) {
		this.eventHandlers[method] = handler;
	}

	open() {
		this.socket = new WebSocket(this.url);
		this.socket.onopen = () => {
			console.log('websocket ' + this.socket.url + ' opened');
			if (this.eventHandlers['OnOpen'])
				this.eventHandlers['OnOpen']();
		}
		this.socket.onmessage = message => {
			const data = JSON.parse(message.data);
			//console.log({ response : data });
			if (data.result) {
				console.log({ response : data });
				if (this.eventHandlers['OnSuccess'])
					this.eventHandlers['OnSuccess'](data.result);
			} else if (data.error) {
				console.log({ error : data });
				if (this.eventHandlers['OnError'])
					this.eventHandlers['OnError'](data.error);
			} else if (data.method) {
				console.log({ event : data });
				if (this.eventHandlers[data.method])
					this.eventHandlers[data.method](data.params);
			}
		}
	}

	request(method, params) {
		const request = { id: ++this.counter, jsonrpc: '2.0', method: method, params: params };
		console.log({ request : request });
		this.socket.send(JSON.stringify(request));
	}

	close() {
		this.socket.onclose = () => {
			console.log('websocket ' + this.socket.url + ' closed');
			if (this.eventHandlers['OnClose'])
				this.eventHandlers['OnClose']();
		}
		this.socket.close();
	}
}