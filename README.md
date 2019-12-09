Примеры использования МегаФон.API
---------------------------------

Платформа Мегафон.API предоставляет программный интерфейс для приложений, управляющих коммуникациями с использованием ресурсов оператора связи. Она позволяет:

* принимать входящие вызовова
* инициировать исходящие вызова
* проигрывать и записывать аудиофайлы
* получать информацию о нажатых клавишах
* объединять несколько вызовов в конференцию
* отправлять короткие сообщения (SMS)
* вещать голосовую конференцию в Интернет через icecast
* принимать сторонний icecast-медиапоток и включать его в идущую конференцию
* ... развитие непрерывно продолжается...

Проект находится в режиме активного бета-тестирования, поэтому использование его для критических задач пока не рекомендуется. Вопросы и предложения можно отправлять в Telegram-группу "МегаФон.API".

Каждое приложение фактически является специальным абонентским терминалом (телефоном), который имеет собственный номер (MSISDN) и ведет себя аналогично физическому терминалу. Взаимодействие с платформой происходит по протоколу JSON-RPC поверх WebSocket c использованием базовой HTTP-аутентификации (при этом MSISDN является логином) или JWT-токена.

Для разработки приложений можно использовать примеры:

* на [Python](/python) с использованием библиотечной реализации JSON-RPC/WebSocket из pip
* на [JavaScript](/javascript) с использованием собственной реализации JSON-RPC/WebSocket для современных браузеров в виде класса в отдельном файле
* на [Perl](/perl) с использованием библиотечной реализации WebSocket и обработкой запросов/ответов JSON-RPC вручную

В примерах используются аудиофайлы, доступные по протоколу WebDAV (т.е. фактически посредством простого REST API). Их можно скачать/загрузить/удалить с помощью curl следующим образом при аутентификации либо по имени пользователя/паролю или с посмощью токена в заголовке:

```
$ curl -X GET -H "Authorization: JWT eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9" http://testapi.megafon.ru/media/prompts/welcome.pcm
$ curl -X PUT -T welcome.alaw --user <login>:<password> http://testapi.megafon.ru/media/prompts/welcome.pcm
$ curl -X DELETE --user <login>:<password> http://testapi.megafon.ru/media/prompts/welcome.pcm
```

Платформа проигрывает аудиофайлы из каталога `prompts/` и записывает аудофайлы в каталог `records/`. Формат файлов - одноканальный A-law с битрейтом 8KHz без заголовка (и поэтому файлы не будут проигрываться большинством аудиоплееров). Для конвертации файлов из любого формата и наоборот можно использовать sox (первым указывается существующий файл, вторым - сконвертированный файл):

```
sox -V hello.ogg -r 8000 -c 1 -t al hello.pcm
sox -V -c 1 -r 8000 -t al 79286266488_56127.pcm 79286266488_56127.wav
```
