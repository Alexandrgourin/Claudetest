const WebSocket = require('ws');

const WS_URL = 'ws://80.209.241.37:8546'; // Стандартный WebSocket порт для reth

console.log(`Подключение к WebSocket: ${WS_URL}`);

const ws = new WebSocket(WS_URL, {
    handshakeTimeout: 10000
});

ws.on('open', function open() {
    console.log('✅ WebSocket соединение установлено');

    // Подписка на новые блоки
    const subscribeNewHeads = {
        jsonrpc: '2.0',
        id: 1,
        method: 'eth_subscribe',
        params: ['newHeads']
    };

    console.log('\nОтправка запроса на подписку newHeads...');
    ws.send(JSON.stringify(subscribeNewHeads));

    // Также попробуем подписаться на логи
    setTimeout(() => {
        const subscribeLogs = {
            jsonrpc: '2.0',
            id: 2,
            method: 'eth_subscribe',
            params: ['logs', {}]
        };
        console.log('Отправка запроса на подписку logs...');
        ws.send(JSON.stringify(subscribeLogs));
    }, 1000);
});

ws.on('message', function incoming(data) {
    try {
        const response = JSON.parse(data);
        console.log('\n📨 Получен ответ:');
        console.log(JSON.stringify(response, null, 2));

        if (response.result && response.id) {
            console.log(`✅ Подписка создана. Subscription ID: ${response.result}`);
        }

        if (response.method === 'eth_subscription') {
            console.log('🎉 Получено событие подписки!');
            if (response.params?.result?.number) {
                console.log(`   Новый блок: ${parseInt(response.params.result.number, 16)}`);
            }
        }
    } catch (e) {
        console.error('Ошибка парсинга ответа:', e.message);
        console.log('Сырые данные:', data.toString());
    }
});

ws.on('error', function error(err) {
    console.error('❌ WebSocket ошибка:', err.message);
});

ws.on('close', function close(code, reason) {
    console.log(`\n🔌 WebSocket соединение закрыто. Код: ${code}, Причина: ${reason || 'не указана'}`);
});

// Тест будет работать 30 секунд
setTimeout(() => {
    console.log('\n⏱️  Тест завершен (30 секунд прошло)');
    ws.close();
    process.exit(0);
}, 30000);
