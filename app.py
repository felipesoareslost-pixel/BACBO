"""
Aplicação Flask para manter o serviço no Render ativo
e executar o bot do Telegram em background
"""
import os
import asyncio
import threading
import requests
from flask import Flask, jsonify

app = Flask(__name__)

# Variável para controlar se o bot já está rodando
bot_running = False

# URL da API original
ORIGINAL_API_URL = "https://aplicacaohack.com/api_bacbo.php"

@app.route('/')
def home():
    """Rota principal para health check"""
    return {
        'status': 'online',
        'service': 'BACBO Telegram Bot',
        'bot_running': bot_running
    }, 200

@app.route('/health')
def health():
    """Endpoint de health check para o Render"""
    return {'status': 'healthy'}, 200

@app.route('/api_bacbo.php')
def api_proxy():
    """Proxy para a API do BACBO - contorna bloqueio de IP"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://aplicacaohack.com/'
        }
        response = requests.get(ORIGINAL_API_URL, headers=headers, timeout=30)
        response.raise_for_status()
        return jsonify(response.json()), 200
    except requests.Timeout:
        return jsonify({'status': 'error', 'message': 'API timeout'}), 504
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def run_bot():
    """Executa o bot do Telegram em background"""
    global bot_running
    try:
        import bacbo_telegram_bot
        bot_running = True
        # Executa o bot
        asyncio.run(bacbo_telegram_bot.main())
    except Exception as e:
        print(f"Erro ao executar bot: {e}")
        bot_running = False

# Inicia o bot em uma thread separada
def start_bot_thread():
    """Inicia o bot em uma thread separada"""
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

# Inicia o bot quando o app é iniciado
start_bot_thread()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
