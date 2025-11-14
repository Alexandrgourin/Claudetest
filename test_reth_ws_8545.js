const WebSocket = require('ws');

const WS_URL = 'ws://80.209.241.37:8545';

console.log(`Попытка подключения к WebSocket: ${WS_URL}`);
console.log('Проверяем поддержку WebSocket на порту 8545 (HTTP RPC порт)\n');

const ws = new WebSocket(WS_URL, {
    handshakeTimeout: 10000
});

let subscriptionId = null;
let receivedEvents = 0;

ws.on('open', function open() {
    console.log('✅ WebSocket соединение установлено!');

    // Подписка на новые блоки (newHeads)
    const subscribeNewHeads = {
        jsonrpc: '2.0',
        id: 1,
        method: 'eth_subscribe',
        params: ['newHeads']
    };

    console.log('\n📤 Отправка запроса на подписку newHeads...');
    console.log(JSON.stringify(subscribeNewHeads, null, 2));
    ws.send(JSON.stringify(subscribeNewHeads));
});

ws.on('message', function incoming(data) {
    try {
        const response = JSON.parse(data);

        if (response.error) {
            console.error('\n❌ Ошибка от сервера:', JSON.stringify(response.error, null, 2));
            return;
        }

        // Ответ на запрос подписки
        if (response.result && response.id === 1) {
            subscriptionId = response.result;
            console.log('\n✅ Подписка успешно создана!');
            console.log(`   Subscription ID: ${subscriptionId}`);
            console.log('\n⏳ Ожидание новых блоков...');
            return;
        }

        // События подписки
        if (response.method === 'eth_subscription') {
            receivedEvents++;
            console.log(`\n🎉 Событие #${receivedEvents} получено!`);

            if (response.params?.subscription) {
                console.log(`   Subscription: ${response.params.subscription}`);
            }

            if (response.params?.result) {
                const result = response.params.result;

                if (result.number) {
                    const blockNumber = parseInt(result.number, 16);
                    console.log(`   📦 Блок #${blockNumber}`);
                }

                if (result.hash) {
                    console.log(`   🔗 Hash: ${result.hash}`);
                }

                if (result.timestamp) {
                    const timestamp = parseInt(result.timestamp, 16);
                    const date = new Date(timestamp * 1000);
                    console.log(`   ⏰ Время: ${date.toISOString()}`);
                }

                if (result.miner) {
                    console.log(`   ⛏️  Miner: ${result.miner}`);
                }
            }
        }
    } catch (e) {
        console.error('\n⚠️  Ошибка парсинга ответа:', e.message);
        console.log('Сырые данные:', data.toString());
    }
});

ws.on('error', function error(err) {
    console.error('\n❌ WebSocket ошибка:', err.message);
    console.error('Детали:', err);
});

ws.on('close', function close(code, reason) {
    console.log(`\n🔌 WebSocket соединение закрыто`);
    console.log(`   Код: ${code}`);
    console.log(`   Причина: ${reason || 'не указана'}`);
    console.log(`   Всего получено событий: ${receivedEvents}`);
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n\n⏹️  Остановка теста...');

    if (subscriptionId && ws.readyState === WebSocket.OPEN) {
        const unsubscribe = {
            jsonrpc: '2.0',
            id: 999,
            method: 'eth_unsubscribe',
            params: [subscriptionId]
        };
        console.log('Отписываемся от событий...');
        ws.send(JSON.stringify(unsubscribe));

        setTimeout(() => {
            ws.close();
            process.exit(0);
        }, 1000);
    } else {
        ws.close();
        process.exit(0);
    }
});

// Автоматическое завершение через 60 секунд
setTimeout(() => {
    console.log('\n\n⏱️  Время теста истекло (60 секунд)');

    if (subscriptionId && ws.readyState === WebSocket.OPEN) {
        const unsubscribe = {
            jsonrpc: '2.0',
            id: 999,
            method: 'eth_unsubscribe',
            params: [subscriptionId]
        };
        ws.send(JSON.stringify(unsubscribe));
    }

    setTimeout(() => {
        ws.close();
        process.exit(0);
    }, 1000);
}, 60000);

console.log('ℹ️  Нажмите Ctrl+C для остановки теста');
