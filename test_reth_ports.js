const WebSocket = require('ws');
const net = require('net');

const HOST = '80.209.241.37';
const PORTS_TO_TEST = [8545, 8546, 8547, 3000, 9001, 80, 443];

console.log(`Проверка доступности портов на ${HOST}...\n`);

// Функция для проверки TCP порта
function checkPort(host, port, timeout = 5000) {
    return new Promise((resolve) => {
        const socket = new net.Socket();

        socket.setTimeout(timeout);

        socket.on('connect', () => {
            socket.destroy();
            resolve({ port, open: true });
        });

        socket.on('timeout', () => {
            socket.destroy();
            resolve({ port, open: false, reason: 'timeout' });
        });

        socket.on('error', (err) => {
            resolve({ port, open: false, reason: err.code });
        });

        socket.connect(port, host);
    });
}

// Функция для проверки WebSocket
function checkWebSocket(url, timeout = 5000) {
    return new Promise((resolve) => {
        const ws = new WebSocket(url, { handshakeTimeout: timeout });

        ws.on('open', () => {
            ws.close();
            resolve({ success: true });
        });

        ws.on('error', (err) => {
            resolve({ success: false, error: err.message });
        });
    });
}

async function main() {
    // Проверяем TCP порты
    for (const port of PORTS_TO_TEST) {
        const result = await checkPort(HOST, port);
        if (result.open) {
            console.log(`✅ Порт ${port} ОТКРЫТ`);

            // Если порт открыт, пробуем WebSocket
            const wsResult = await checkWebSocket(`ws://${HOST}:${port}`);
            if (wsResult.success) {
                console.log(`   🎉 WebSocket работает на порту ${port}!`);
            } else {
                console.log(`   ℹ️  WebSocket недоступен: ${wsResult.error}`);
            }
        } else {
            console.log(`❌ Порт ${port} закрыт или недоступен (${result.reason})`);
        }
    }

    console.log('\n✅ Проверка завершена');
}

main().catch(console.error);
