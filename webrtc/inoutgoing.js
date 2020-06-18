//
// Этот пример иллюстрирует работу WebRTC-подсистемы МегаФон.API. Он позволяет зарегистрировать браузер
// в API, совершать (или принимать) звонки из браузера (или в него). Пример можно отнески к категории
// "активных", когда браузеринициирует создание своего плеча.
//
// Для работы необходимо ввести полный УРЛ точки присоединения к МегаФон.API и нажать "Connect".
// На первом этапе будет установлено соединение браузера и платформы, после успешного завершения
// которого можно будет либо ввести номер телефона для совершения вызова (тогда браузер позвонит),
// либо набрать на номер телефона учётной записи МегаФон.API.
//
// Следует помнить, что получение ICE-кандидатов может занимать некоторое время - десятки секунд,
// публичные STUN-сервера могут быть нагружены!
// 
// В примере SDP_b означает SDP браузера, а SDP_m - это SDP, "приехавшее" из платформы МегаФон.API
//
// Спецификация WebRTC описывает только трафиковую/медийную часть, никак не задавая сигнализацию 
// (процесс управления сессией связи). Эту часть реализуется в каждом конкретном случае.
// МегаФон.API для этого вводит RTC-методы (см. спецификацию МегаФон.API) и оборачивает их
// в JSON-RPC (v2.0), как и всё другие свои методы. Поэтому нам нужна какая-то его JS-реализация.
// Используем оную с https://github.com/jershell/simple-jsonrpc-js. Отважные могут исользовать 
// что-то друге или написать сами.
//
// В упомянутой реализации НЕОБХОДИМО переопределить toStream() для конкретной отправки байтов 
// в установленное соединение (см. ниже). Экземпляр назовём megafon, по аналогии с другими 
// примерами (на Питоне)
//
// Серия общих примеров для WebRTC на https://webrtc.github.io/samples/
// Неплохой учебник на https://www.tutorialspoint.com/webrtc, хоть и староват.
// На https://www.webcodegeeks.com/web-development/webrtc-tutorial-beginners/ новее, но "мусорнее"
// Вообще, в Интернете есть много материалов по теме, но, к сожалению, большая их часть излагает
// материал очень "отрывисто" и не всегда прозрачно. Поэтому настоящий код сильно откоментирован,
// что может несколько раздражать опытного разработчика. Просим за это прощения!
// 
const megafon = new simple_jsonrpc();
const MFserverMediaConfig = {
    // Эти сервера нужны браузеру для преодоления NAT, через них он узнает свои внешние IP и порт,
    // а потом предложит МегаФон.API в качестве кандидатов на передачу SRTP
    iceServers: [
        { urls: 'stun:stun.stunprotocol.org:3478' },
        { urls: 'stun:stun.l.google.com:19302' },
    ],
};
const constraints = {
    // Определяем ограничения, являющиеся аргументом функции getUserMedia()    
    video: false, // Отключим видео, так как если нет камеры весь пример не заработает
    audio: true,  // работаем, очевидно, с аудио
};

var localAudio;         // это объект HTML-тега <audio id="localAudio">, микрофон браузера 
var remoteAudio;        // это объект HTML-тега <audio id="remoteAudio">, динамик браузера (удалённый микрофон)
var localStream;        // это медиапоток в браузере (получаем его из getUserMedia())
var MFserverMedia;      // это соединение непосредственно для передачи звука (медийная часть) 
var MFserverSignaling;  // это websocket-соединение с сервером МегаФон.API (сигнальная часть)
//let ice = '';

var browser_leg;        // это идентификатор сессии между платформой и браузером
var gsm_leg;            // это идентификатор сессии между платформой и телефонной сетью

// По загрузке страницы целиком, делаем всякие инициализации
document.addEventListener('DOMContentLoaded', function () {
    localAudio = document.getElementById('localAudio');
    remoteAudio = document.getElementById('remoteAudio');
    // URL можно сохранить в локальном хранилище браузера, чтобы постоянно не вводить его
    // Поэтому достаём из localStorage (если он там есть)
    document.getElementById('megafon_api_url').value = localStorage.getItem('megafon_api_url') || '';
    // Меняем статус на Ready
    document.getElementById('ready').innerHTML = 'Готов к работе';    
});

// После нажатия на кнопку Connect вызываем функцию соединения с сервером МегаФон.API
function connect() {
    let endpoint_url = document.getElementById('megafon_api_url').value;
    // Кладём URL в localStorage, чтобы потом не вводить его много раз
    localStorage.setItem('megafon_api_url', endpoint_url);

    // Обнуляем call_session для двух плечей разговора (может остаться мусор от предыдущих вызовов)  
    browser_leg = null;
    gsm_leg = null;

    // Это ws-подключение к серверу МегаФон.API
    MFserverSignaling = new WebSocket(endpoint_url);
    // В этом месте определяем функцию toStream(), как необходимо для JS-реализации JSON-RPC
    // и посылающую сообщение в открытое соединение
    megafon.toStream = function(msg) {
        console.log('Отправлено на сервер: ', JSON.parse(msg));
        MFserverSignaling.send(msg);
    };

    // Если соединение установилось, то...
    MFserverSignaling.onopen = function() {
        // Первая стандартная магия WebRTC: вызываем метод getUserMedia() с заданными ограничениями
        // В этот момент всплывает запрос на разрешение доступа к локальным медиаустройствам, доступным
        // браузеру
        if (navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices
                .getUserMedia(constraints)
                .then(stream => {
                    // В случае, если браузер поддерживает всё, что нужно, getUserMedia() возвращает
                    // медиапоток: в нашем случае в этом потоке только один трек - микрофон, видео нет. 
                    // Его и вставляем в теге <audio id="localAudio"> на HTML-странице.
                    localStream = stream;
                    localAudio.srcObject = stream;
                    // Вторая стандартная магия WebRTC: создаём соединение, указывая ему ICE-сервера,
                    // и вешаем обработчики на нужные события, которые происходят внутри "черного ящика" RTCPeerConnection:
                    // .onicecandidate 
                    //      взлетает, когда RTCPeerConnection получает ICE-кандидата от STUN-серверов для преодоления NAT
                    // .ontrack 
                    //      взлетает, когда к соединению добавляется новый трек: удалённый, локальный
                    // .addStream
                    //      Добавляем локальный медиапоток к соединению 
                    MFserverMedia = new RTCPeerConnection(MFserverMediaConfig);   // конфигурация ICE серверов
                    MFserverMedia.onicecandidate = gotIceCandidate;
                    MFserverMedia.ontrack = gotRemoteStream;
                    MFserverMedia.addStream(localStream);
                    // А теперь запускаем сам поиск ICE-кандидатов. Этот процесс может занять какое-то время, до десятков
                    // секунд, в зависимости от нагруженности STUN-серверов
                    MFserverMedia
                        .createOffer()                                              
                        .then(session_description => {                              // получили SD и прикрутили к "черному
                            MFserverMedia.setLocalDescription(session_description)  // ящику" нашего RTCPeerConnection 
                        })
                        .catch(errorHandler)
                    // Все, теперь надо инициализировать МегаФон.API для работы с WebRTC: отправляем туда метод setupRTC
                    megafon.call('setupRTC');
                    // и на нашей страничке открываем кнопку, окно ввода и т.п.
                    document.getElementById('status').innerHTML = 'Соединение установлено...';
                    document.getElementById('connect').disabled = true;
                    document.getElementById('disconnect').disabled = false;
                })
                .catch(errorHandler);
        } else {
            alert('ОШИБКА: ваш браузер не поддерживает WebRTC (нет getUserMedia API).');
            document.getElementById('status').innerHTML = 'ОШИБКА: Браузер не поддерживает getUserMedia API';
        }
    };

    // Если соединение закрывается, то
    MFserverSignaling.onclose = function(event) {
        if (event.wasClean) {
            console.info('Соединение завершено успешно');
            document.getElementById('status').innerHTML = 'Соединение завершено успешно';
        } else {
            console.error('Соединение завершено с ошибкой');
            document.getElementById('status').innerHTML = 'Соединение завершено с ошибкой';
        }
        console.info('код завершения: ' + event.code + ', причина: ' + event.reason);
        document.getElementById('status').innerHTML += ', код завершения: ' + event.code + ', ошибка: ' + event.reason;
        disconnect();
    };

    // А вот если сервер что-то прислал, то надо обрабатывать (см. ниже)
    // Спецификация WebRTC описывает только трафиковую/медийную часть, никак не задавая сигнализацию 
    // (процесс управления сессией связи). Эта часть отдана на откуп конкретной реализации и
    // МегаФон.API вводит для этого несколько RPC-методов (см. спецификацию МегаФон.API)
    MFserverSignaling.onmessage = gotMessageFromServer;

    // Если ошибка в соединении
    MFserverSignaling.onerror = errorHandler;
}

// Событие возникает всякий раз при получении ICE-кандидата. Мы должны собрать
// их все (проверка на то, завершён этот процесс или нет)
function gotIceCandidate(event) {
    document.getElementById('status').innerHTML = 'Получаю ICE-кандидатов. Это может занять некоторое время...';
    // Ожидаем последнего кандидата
    if (event.target.iceGatheringState === 'complete') {
        document.getElementById('status').innerHTML = 'Готово! Все ICE-кандидаты получены...';
        // Раз все ICE-кандидаты получены, можем передать готовый SDP в МегаФон.API.
        // Внимание! С точки зрения WebRTC сервер МегаФон.API равнозначен другому браузеру,
        // с которым мы хотим разговаривать и мы должны передавать ему наш SDP_b (локальный).
        // SDP_m из МегаФон.API, с другой стороны, для нас remoteDescription.sdp
        console.log('Все ICE-кандидаты получены. Отправляю SDP_b в МегаФон.API...');
        megafon.call('callMakeRTC', {
            sdp: event.target.localDescription.sdp
        });
        // При получении такого RTC-запроса, платформа среагирует на него также, как если бы на неё
        // "упал" настоящий телефонный вызов - она вернёт нам onCallIncoming, содержащий call_session
        // этого соединения. Используя этот call_session, можно применять всю механику МегаФон.API.
        // Будем обрабатывать этот onCallIncoming в ответах сервера (см. ниже) 
        document.getElementById('callMakeRTC').checked = true;        
    }
}

function gotMessageFromServer(message) {
    megafon.messageHandler(message.data); // Этот метод должен обязательно вызываться для обработки входящих событий
    const signal = JSON.parse(message.data);
    console.log('Получено от сервера: ', signal);

    // Обработка ответа и вывод в поле 'status' на HTML-странице (согласно JSON-RPC, в ответе либо поле 'result', либо 'error')
    const result = signal.result ? signal.result : signal.error ? signal.error : '';
    document.getElementById('status').innerHTML = result ? result.message : document.getElementById('status').innerHTML;

    // Обработка JRPC-ответов
    handleMessageFromServer();
}

function handleMessageFromServer() {
    // Итак, после отправки в МегаФон.API callMakeRTC (см. gotIceCandidate()) платформа должна вернуть нам
    // onCallIncoming, содержащий call_session браузерного плеча вызова. Это по смыслу эквивалентно входящему 
    // звонку на мобильный телефон и мы должны ответить на этот звонок - нажать "зелёную кнопку" -, то есть
    // послать callAnswer.
    megafon.on('onCallIncoming','pass',event => {
        // Если браузерного плеча ещё нет, получим его call_session. Оно должно появится первым при регистрация браузера,
        // но надёжнее будет проверить, возвращается ли "нулевой" anum (индикация RTC-плеча)
        if(event.anum.toString() === "0000000000") {
            browser_leg = event.call_session.toString();
            console.log('Браузерное плечо имеет call_session: ',browser_leg);
            document.getElementById('onCallIncoming').checked = true;        
            megafon.call('callAnswer',{
                call_session: browser_leg            
            });
        } else {
        // Однако, onCallIncoming может появится второй раз - в случае, если после установки браузерного плеча мы не будем
        // сами инициировать вызов, а будем ждать входящего звонка. В этом случае прилетевший call_session будет GSM-плечом.
        // Ответим на этот звонок и в onCallAnswer (см. ниже) отработает вся та же механика, что и при инициации 
        // звонка из браузера (гудок и соединение)
            gsm_leg = event.call_session.toString();            
            console.log(`Входящий телефонный вызов имеет call_session: ${gsm_leg}`);
            document.getElementById('onCallIncoming_check').checked = true;                    
            megafon.call('callAnswer',{
                call_session: gsm_leg
            });
        }
    });

    // Поймаем результат выполнения callAnswer. В нашем сценарии на платформе таких может возникнуть два: от браузерного плеча
    // и от GSM'ого. Поскольку браузерное плечо возникает раньше GSM'ого, будем проверять на его наличие. Проиграем в это
    // плечо тоновый сигнал
    megafon.on('onCallAnswer','pass', event => {
        if(event.call_session.toString() == browser_leg) {
            console.log(`onCallAnswer для браузерного плеча с call_session ${browser_leg}`);
            document.getElementById('onCallAnswerWEB').checked = true;
            megafon.call('callTonePlay', {
                call_session: browser_leg,
                tone_id: '425',
                repeat: false
            });
            document.getElementById('callTonePlay').checked = true;            
        } else {
            // Второе появление onCallAnswer - это GSM-плечо. Также проиграем в него тоновый сигнал
            gsm_leg = event.call_session.toString();
            console.log(`onCallAnswer для телефонного плеча с call_session ${gsm_leg}`);
            megafon.call('callTonePlay', {
                call_session: gsm_leg,
                tone_id: '500',
                repeat: false
            });
            document.getElementById('onCallAnswerPHONE').checked = true;                        
        }
    });

    // После того, как платформа получит callAnswer, она, зная, что этот call_session не простой, а WebRTC'шный (принадлежит браузеру),
    // вернёт также и onCallAnswerRTC, содержащий платформенный SDP, сигнализируя WebRTC-подсистеме браузера, что звонок принят.
    megafon.on('onCallAnswerRTC','pass', event=> {
        console.log('onCallAnswerRTC со следующим SDP_m: ', event);
        // Тут есть нюанс с SDP: браузерное WebRTC API хочет SDP без ICE-кандидатов (их отдельно), а платформа возвращает
        // всё вместе. Оторвём кандидатов в handleSDP()
        handleSDP(event, 'answer');
        document.getElementById('onCallAnswerRTC').checked = true;
    });

    // Слушаем событие onCallTonePlay. Раз проигрывание гудка завершено, смотрим, есть ли у нас уже оба плеча
    megafon.on('onCallTonePlay', 'pass', event => {
        console.log(`Завершено проигрывание для call_session: ${event.call_session.toString()}`);
        if(browser_leg && gsm_leg) {
            // оба плеча есть - свяжем их в один разговор. Получили полноценный звонок из браузера на телефон!!            
            megafon.call('callTrombone', {
                a_session: browser_leg,
                b_session: gsm_leg
            });
            document.getElementById('callTrombone').checked = true;        
        } else if (browser_leg) {
            // есть только браузерное плечо. Это значит, что можно открыть поле ввода номера телефона, чтобы 
            // на него позвонить. Ну, либо позвонят нам (см. onCallIncoming)...
            document.getElementById('onCallTonePlay').checked = true;
            document.getElementById('callMakeText').disabled = false;
            document.getElementById('callMake').disabled = false;
        }
    });

    // Возникает при попытке внешнего webrtc-соединения. В этом примере не используется 
    megafon.on('onCallIncomingRTC', 'pass', event => {
    });

    // Возникает, если соединение возможно (есть деньги на счету и т.п.)
    megafon.on('onCallAccept', 'pass', event => {
    });

    // Возникает, если звонок отклонён
    megafon.on('onCallReject', 'pass', event => {
    });

    // Возникает при обрыве проигрывания тонового сигнала или фала приветствия 
    megafon.on('onCallPlayCancel','pass', event => {
    });

    // Возникает при завершении вызова
    megafon.on('onCallTerminate','pass', event => {
        console.log(`Сессия завершена для call_session: ${event.call_session.toString()}`)
    });
}

function handleSDP(signal, status) {
    // Браузерное WebRTC API хочет SDP без ICE-кандидатов (их отдельно), а платформа возвращает всё целиком
    // Соответственно, необходимо извлечь ICE-кандидатов из SDP
    // Разбиваем на массив строк
    if (signal.sdp) {
        const sdpStrings = signal.sdp.split('\r\n');
        let withoutCandidates = [];
        let candidates = [];

        // Вырываем оттуда ICE-кандидатов
        withoutCandidates = sdpStrings.filter(
            item =>
                !item.includes('a=end-of-candidates') &&
                !item.includes('a=candidate') &&
                item !== ''
        );

        // А самих кандидатов кладём отдельно
        candidates = sdpStrings.filter(item => item.includes('a=candidate'));
        candidates = candidates.map(candidate => candidate.slice(2));

        // Снова собираем SDP из массива строк. ВНИМАНИЕ! Замечено, что при отсутствии '\r\n' в конце собранной 
        // строки, Firefox такой SDP проглатывает, в то время как Chrome генерирует ошибку, что является 
        // более корректной реакцией на ошибочный SDP
        let withoutCandidatesString = withoutCandidates.join('\r\n') + '\r\n';
        let rtcSessionDescription = new RTCSessionDescription({
            sdp: withoutCandidatesString,
            type: status, // ставим type в зависимости от статуса соответственно answer или offer
        });
        // Теперь пришедший от платформы SDP привязываем к RTCPeerConnection-соединению в качетсве удалённого
        // и отдельно привязываем ICE-кандидатов от платформы
        MFserverMedia
            .setRemoteDescription(rtcSessionDescription)
            .then(function() {
                candidates.forEach(candidate => {
                    MFserverMedia
                        .addIceCandidate(new RTCIceCandidate({ sdpMid: '', sdpMLineIndex: '', candidate: candidate }))
                        .catch(errorHandler);
                });
            })
            .catch(errorHandler);
    }
}

function gotRemoteStream(event) {
    console.log('Получил удалённый медиапоток: ', event);
    remoteAudio.srcObject = event.streams[0];
    event.streams[0]
        .getTracks()
        .forEach(track => MFserverMedia.addTrack(track, localStream));
}

function callMake() {
    // Вызываем callMake с номером телефона, на который хотим позвонить
    megafon.call('callMake', {
        bnum: document.getElementById('callMakeText').value
    });
    document.getElementById('callMake_check').checked = true;        
}

function errorHandler(error) {
    console.log(error);
    document.getElementById('status').innerHTML = 'Connection error' + (error.message !== undefined ? ': ' + error.message : '');
}

function disconnect() {
    if (gsm_leg) {
        megafon.call('callTerminate',{
            call_session: gsm_leg
        });
    }
    if(browser_leg) {        
        megafon.call('callTerminate',{
            call_session: browser_leg
        });
    }
    document.getElementById('connect').disabled = false;
    document.getElementById('disconnect').disabled = true;
    document.getElementById('callMake').disabled = true;
    // Выключаем кнопки и чек-боксы
    document.getElementById('callMakeRTC').checked = false;
    document.getElementById('onCallIncoming').checked = false;    
    document.getElementById('onCallAnswerWEB').checked = false;
    document.getElementById('onCallAnswerRTC').checked = false;
    document.getElementById('callTonePlay').checked = false;
    document.getElementById('onCallTonePlay').checked = false;
    document.getElementById('callMake_check').checked = false;    
    document.getElementById('onCallIncoming_check').checked = false;        
    document.getElementById('onCallAnswerPHONE').checked = false;
    document.getElementById('callTrombone').checked = false;        

    MFserverSignaling.close();
}
