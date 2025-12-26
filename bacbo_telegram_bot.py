import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configurar encoding UTF-8 para Windows
if sys.platform == "win32":
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

import aiohttp

API_URL = os.getenv("BACBO_API_URL", "https://aplicacaohack.com/api_bacbo.php")
BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8440000433:AAEgTueQUeWHD94uN7th3deXb6Pje_7x7I4",
)
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "-1003234908578"))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "6"))

# Configurar logging com mais detalhes e encoding UTF-8
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot_detailed.log", encoding='utf-8')
    ],
)

logger = logging.getLogger("bacbo_bot")

# Arquivo para persistência de estatísticas
STATS_FILE = Path("bot_stats.json")


class BotStats:
    def __init__(self):
        self.total_signals = 0
        self.wins = 0
        self.losses = 0
        self.current_streak = 0
        self.best_streak = 0
        self.last_signal = None
        self.last_result = None
        self.protection_active = False
        self.load()

    def load(self):
        if STATS_FILE.exists():
            try:
                data = json.loads(STATS_FILE.read_text())
                self.total_signals = data.get("total_signals", 0)
                self.wins = data.get("wins", 0)
                self.losses = data.get("losses", 0)
                self.current_streak = data.get("current_streak", 0)
                self.best_streak = data.get("best_streak", 0)
                self.last_signal = data.get("last_signal")
                self.last_result = data.get("last_result")
                logger.info("Estatísticas carregadas: %d sinais, %d wins, %d losses", 
                           self.total_signals, self.wins, self.losses)
            except Exception as e:
                logger.error("Erro ao carregar estatísticas: %s", e)

    def save(self):
        try:
            data = {
                "total_signals": self.total_signals,
                "wins": self.wins,
                "losses": self.losses,
                "current_streak": self.current_streak,
                "best_streak": self.best_streak,
                "last_signal": self.last_signal,
                "last_result": self.last_result,
            }
            STATS_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error("Erro ao salvar estatísticas: %s", e)

    def add_win(self):
        self.wins += 1
        self.current_streak += 1
        if self.current_streak > self.best_streak:
            self.best_streak = self.current_streak
        self.protection_active = False
        self.save()

    def add_loss(self):
        self.losses += 1
        self.current_streak = 0
        self.save()

    def get_accuracy(self) -> float:
        total = self.wins + self.losses
        if total == 0:
            return 0.0
        return (self.wins / total) * 100

    def register_signal(self, bet: str):
        self.total_signals += 1
        self.last_signal = bet
        self.last_result = None
        self.save()


stats = BotStats()


def map_result(resultado: str) -> str:
    if resultado in {"Player", "Banker", "Tie"}:
        return resultado
    return resultado.title()


def detect_signal(rounds: List[Dict]) -> Optional[Dict[str, str]]:
    filtered = [r for r in rounds if r["resultado"] in ("Player", "Banker")]
    if len(filtered) < 3:
        return None

    recent = filtered[:6]
    seq = [r["resultado"] for r in recent]

    if seq[0] == seq[1] == seq[2]:
        bet = "BANKER" if seq[0] == "Player" else "PLAYER"
        return {
            "bet": bet,
            "pattern": "3x sequência",
            "confidence": "Alta",
        }

    if len(seq) >= 4 and seq[0] == seq[1] == seq[2] == seq[3]:
        bet = "BANKER" if seq[0] == "Player" else "PLAYER"
        return {
            "bet": bet,
            "pattern": "4x sequência",
            "confidence": "Muito alta",
        }

    if (
        len(seq) >= 4
        and seq[0] != seq[1]
        and seq[1] != seq[2]
        and seq[2] != seq[3]
    ):
        bet = "BANKER" if seq[3] == "Player" else "PLAYER"
        return {
            "bet": bet,
            "pattern": "Alternância",
            "confidence": "Média",
        }

    return None


async def fetch_rounds(session: aiohttp.ClientSession) -> List[Dict]:
    try:
        async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            payload = await resp.json()
            if isinstance(payload, dict) and payload.get("status") == "success":
                data = payload.get("data", [])
            elif isinstance(payload, list):
                data = payload
            else:
                logger.warning("Formato inesperado da API: %s", payload)
                return []

            rounds = [
                {
                    "id": item.get("id"),
                    "hash": item.get("hash"),
                    "data_hora": item.get("data_hora"),
                    "resultado": map_result(item.get("resultado", "")),
                }
                for item in data
            ]
            logger.debug("Rounds obtidos: %d", len(rounds))
            return rounds
    except asyncio.TimeoutError:
        logger.error("Timeout ao buscar rounds da API")
        return []
    except aiohttp.ClientError as e:
        logger.error("Erro de conexão com a API: %s", e)
        return []
    except Exception as e:
        logger.error("Erro inesperado ao buscar rounds: %s", e)
        return []


async def send_message(session: aiohttp.ClientSession, text: str) -> None:
    if not CHAT_ID:
        logger.error("CHAT_ID não configurado. Exporte TELEGRAM_CHAT_ID antes de iniciar.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error("Falha ao enviar mensagem (status %d): %s", resp.status, body)
            else:
                logger.info("✅ Mensagem enviada: %s", text.replace("\n", " | ")[:100])
    except asyncio.TimeoutError:
        logger.error("Timeout ao enviar mensagem para o Telegram")
    except aiohttp.ClientError as e:
        logger.error("Erro de conexão com Telegram: %s", e)
    except Exception as e:
        logger.error("Erro inesperado ao enviar mensagem: %s", e)


def format_signal_message(signal: Dict[str, str], round_info: Dict[str, str]) -> str:
    bet = signal["bet"]
    
    # Emojis e cores
    if bet == "PLAYER":
        emoji = "🔵"
        cor = "azul"
    elif bet == "BANKER":
        emoji = "🔴"
        cor = "vermelho"
    else:
        emoji = "🟠"
        cor = "empate"
    
    # Mensagem no formato da imagem
    message = f"✅ Entrada Confirmada ✅\n\n"
    message += f"🟠 Proteção no Empate\n\n"
    message += f"{emoji} Apostar no {cor}"
    
    return message


async def run_bot() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN não definido. Configure TELEGRAM_BOT_TOKEN.")

    logger.info("=" * 50)
    logger.info("🚀 Bot Bacbo iniciado!")
    logger.info("API URL: %s", API_URL)
    logger.info("Chat ID: %s", CHAT_ID)
    logger.info("Intervalo de polling: %d segundos", POLL_INTERVAL_SECONDS)
    logger.info("=" * 50)

    last_hash = None
    waiting_result = False
    signal_bet = None
    error_count = 0
    max_errors = 5

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                rounds = await fetch_rounds(session)
                if not rounds:
                    logger.debug("Nenhum round recebido, aguardando...")
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue

                # Resetar contador de erros em caso de sucesso
                error_count = 0

                latest = rounds[0]
                current_hash = latest.get("hash")

                # Verificar resultado da última aposta
                if waiting_result and current_hash and current_hash != last_hash:
                    resultado = latest.get("resultado")
                    logger.info("🎲 Novo resultado: %s (Aguardando: %s)", resultado, signal_bet)
                    
                    # Caso seja empate (Tie), sempre ganhamos
                    if resultado == "Tie":
                        stats.add_win()
                        win_msg = (
                            f"✅ WIN NO EMPATE ✅\n\n"
                            f"✅ {stats.wins} ⛔ {stats.losses} 🎯 Acertamos {stats.get_accuracy():.2f}%\n\n"
                            f"🚀 ESTAMOS A {stats.current_streak} GREENS SEGUIDOS 🚀"
                        )
                        await send_message(session, win_msg)
                        waiting_result = False
                        signal_bet = None
                        stats.protection_active = False
                    # Lógica de verificação de vitória/derrota
                    elif resultado in ("Player", "Banker"):
                        if (signal_bet == "PLAYER" and resultado == "Player") or \
                           (signal_bet == "BANKER" and resultado == "Banker"):
                            # WIN
                            stats.add_win()
                            win_msg = (
                                f"✅ WIN ✅\n\n"
                                f"✅ {stats.wins} ⛔ {stats.losses} 🎯 Acertamos {stats.get_accuracy():.2f}%\n\n"
                                f"🚀 ESTAMOS A {stats.current_streak} GREENS SEGUIDOS 🚀"
                            )
                            await send_message(session, win_msg)
                            waiting_result = False
                            signal_bet = None
                            stats.protection_active = False
                        elif not stats.protection_active:
                            # Ativar proteção
                            logger.info("🛡️ Ativando proteção...")
                            stats.protection_active = True
                            protection_msg = (
                                f"✅ Proteção Confirmada ✅\n\n"
                                f"🟠 Proteção no Empate\n\n"
                                f"{'🔴 Apostar no vermelho' if signal_bet == 'BANKER' else '🔵 Apostar no azul'}"
                            )
                            await send_message(session, protection_msg)
                        else:
                            # Perda após proteção
                            logger.warning("❌ Loss registrado")
                            stats.add_loss()
                            stats.protection_active = False
                            loss_msg = (
                                f"❌ LOSS ❌\n\n"
                                f"✅ {stats.wins} ⛔ {stats.losses} 🎯 Acertamos {stats.get_accuracy():.2f}%"
                            )
                            await send_message(session, loss_msg)
                            waiting_result = False
                            signal_bet = None

                # Detectar novo sinal
                if not waiting_result and current_hash and current_hash != last_hash:
                    signal = detect_signal(rounds)
                    if signal:
                        logger.info("🎯 Novo sinal detectado: %s (%s)", signal["bet"], signal["pattern"])
                        stats.register_signal(signal["bet"])
                        message = format_signal_message(signal, latest)
                        await send_message(session, message)
                        waiting_result = True
                        signal_bet = signal["bet"]
                    
                    last_hash = current_hash

            except KeyboardInterrupt:
                logger.info("Bot interrompido pelo usuário")
                raise
            except Exception as exc:
                error_count += 1
                logger.exception("❌ Erro no loop principal (%d/%d): %s", error_count, max_errors, exc)
                
                if error_count >= max_errors:
                    logger.critical("Muitos erros consecutivos! Encerrando bot.")
                    raise

            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot finalizado pelo usuário.")
