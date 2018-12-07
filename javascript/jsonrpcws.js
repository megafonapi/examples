class JsonRpcWs {

	constructor(url) {
		this.url = url;
		this.counter = 0;
		this.requestHandlers = {};
		this.responseHandlers = {};
	}
	
	handle(method, handler) {
		this.requestHandlers[method] = handler;
	}

	async open() {
		return new Promise(resolve => {
			this.socket = new WebSocket(this.url);
			this.socket.onopen = () => {
				console.log('websocket ' + this.socket.url + ' opened');
				if (this.requestHandlers['OnOpen'])
					this.requestHandlers['OnOpen']();
				resolve();
			}
			this.socket.onmessage = message => {
				const data = JSON.parse(message.data);
				if (data.result) {
					console.log({ response : data });
					if (data.id && this.responseHandlers[data.id])
						this.responseHandlers[data.id](data.result);
				} else if (data.method) {
					console.log({ event : data });
					if (this.requestHandlers[data.method])
						this.requestHandlers[data.method](data.params);
				}
			}
		})
	}

	async request(method, params) {
		const id = ++this.counter;
		const request = { id: id, jsonrpc: '2.0', method: method, params: params };
		console.log({ request : request });
		this.socket.send(JSON.stringify(request));
		return new Promise(resolve => this.responseHandlers[id] = resolve);
	}

	async close() {
		return new Promise(resolve => {
			this.socket.onclose = () => {
				console.log('websocket ' + this.socket.url + ' closed');
				if (this.requestHandlers['OnClose'])
					this.requestHandlers['OnClose']();
				resolve();
			}
			this.socket.close();
		})
	}
}