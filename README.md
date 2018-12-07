Примеры использования МегаФон.API
---------------------------------

Платформа Мегафон.API предоставляет программный интерфейс для приложений, управляющих голосовыми коммуникациями. Она позволяет:

* принимать входящие вызовова
* инициировать исходящие вызовов
* проигрывать аудиофайлы
* получать информацию о нажатых клавишах
* объединять несколько вызовов в конференцию

Каждое приложение фактически является специальным абонентским терминалом (телефоном) и имеет собственный номер (MSISDN). Взаимодействие с платформой происходит по протоколу JSON-RPC поверх WebSocket c использованием базовой HTTP-аутентификации (при этом MSISDN является логином) или JWT-токена.

Для разработки приложений можно использовать [документацию](http://megafonapi.github.io/), а также примеры на [Python](/python) и [JavaScript](/javascript). В примерах используются аудиофайлы, доступные по протоколу WebDAV (т.е. фактически посредством простого REST API). Их можно скачать/загрузить/удалить с помощью curl следующим образом:

```
$ curl -X GET --user <login>:<password> http://127.0.0.127/media/welcome.alaw
$ curl -X PUT -T welcome.alaw --user <login>:<password> http://127.0.0.127/media/welcome.alaw
$ curl -X DELETE --user <login>:<password> http://127.0.0.127/media/welcome.alaw
```

