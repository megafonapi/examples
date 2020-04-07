Пример использования МегаФон.API на Go
--------------------------------------

Пример является консольным приложением, принимающим логин, пароль и номер, на который нужно позвонить и проиграть аудиофайл, в командной строке:

```
$ go get nhooyr.io/websocket
$ go run call.go <login> <password> <destination>
```

В примере используется только [Minimal and idiomatic WebSocket library for Go](https://github.com/nhooyr/websocket), обмен запросами/ответами JSON-RPC реализован вручную поверх этой библиотеки.