# IQ Option Async WebSocket Client

Biblioteca Python 100% assíncrona e orientada a eventos para interação com a plataforma IQ Option via WebSocket.

## Características

- **Não bloqueante** — toda a comunicação é baseada em `asyncio`, nenhuma função pública bloqueia o event loop
- **Protocolo completo** — autenticação, ativos, operações, candles, subscriptions, reconexão
- **Multi-modalidade** — Binary, Turbo, Blitz, Digital (call/put)
- **Clock sync** — sincronização precisa com o relógio do servidor
- **Reconexão automática** — reconecta e restaura subscriptions ao perder conexão
- **Mascaramento de credenciais** — logs nunca expõem SSID, tokens ou senhas

## Instalação

```bash
pip install git+https://github.com/USER/iqoption-client.git
```

Ou instale localmente:

```bash
git clone https://github.com/USER/iqoption-client.git
cd iqoption-client
pip install -e .
```

## Requisitos

- Python ≥ 3.10
- `aiohttp` ≥ 3.9
- `websockets` ≥ 13.0
- `python-dotenv` ≥ 1.0

## Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
IQOPTION_EMAIL=seu@email.com
IQOPTION_PASSWORD=sua_senha
IQOPTION_ACCOUNT_TYPE=demo
IQOPTION_LOG_LEVEL=INFO
```

## Uso Rápido

```python
import asyncio
from iqoption_client import IQOptionClient, OptionType, Direction

async def main():
    client = IQOptionClient()
    await client.connect()

    # Ver saldo
    balance = client.accounts.account.active_balance
    print(f"Saldo: ${balance.amount:.2f}")

    # Listar ativos blitz abertos
    active = client.assets.find_open_active(OptionType.BLITZ)
    print(f"Ativo: {active.id} - {active.name}")

    # Colocar CALL
    option = await client.place_call(
        active_id=active.id,
        amount=1.0,
        option_type=OptionType.BLITZ,
        expiration_size=30,
    )
    print(f"Operação aberta: id={option.id}")

    # Aguardar resultado
    result = await client.wait_for_binary_result(option.id, timeout=60)
    print(f"Resultado: {result.result} (profit: ${result.profit_amount})")

    await client.disconnect()

asyncio.run(main())
```

## Modalidades Suportadas

| Tipo | option_type_id | Expiração | Campos Especiais |
|------|---------------|-----------|------------------|
| **Binary** | 1 | Candle boundary (900s padrão) | — |
| **Turbo** | 3 | Candle boundary (60s padrão) | — |
| **Blitz** | 12 | `server_time + expiration_size` | `expiration_size` obrigatório (30, 45, 60, 120, 180, 300) |
| **Digital** | — | Período do instrumento | `instrument_id`, `instrument_index` via evento `instrument-generated` |

## Arquitetura

```
iqoption_client/
├── client.py                  # IQOptionClient — interface principal
├── configuration.py           # Config — lê .env
├── exceptions.py              # Exceções customizadas
├── logging.py                 # CredentialFilter — mascara logs
├── connection/
│   ├── websocket_manager.py   # WebSocket — connect, send, subscribe
│   ├── event_bus.py           # EventBus — dispatch de mensagens
│   ├── http_auth.py           # HTTPAuth — login REST → SSID
│   ├── heartbeat.py           # HeartbeatManager
│   └── clock_sync.py          # ClockSync — offset com servidor
├── reconnection/
│   └── manager.py             # Reconexão automática + restore subscriptions
├── session/
│   └── manager.py             # Gerencia SSID, token, user_id
├── connection_manager/
│   └── manager.py             # Estado da conexão (state machine)
├── accounts/
│   └── manager.py             # Saldos, seleção de conta, perfil
├── assets/
│   └── manager.py             # Ativos, comissões, payouts
├── candles/
│   └── manager.py             # Histórico e streaming de candles
├── trading/
│   └── manager.py             # Abrir CALL/PUT, aguardar resultado
├── subscriptions/
│   └── manager.py             # Portfolio position-changed, order-changed
├── operations/
│   └── manager.py             # Tracking de operações abertas/fechadas
├── history/
│   └── manager.py             # Histórico de posições
├── events/
│   └── manager.py             # Eventos customizados
└── models/
    ├── enums.py               # OptionType, Direction, InstrumentType
    ├── account.py             # Account, Balance
    ├── asset.py               # Active, OptionInfo, Schedule
    ├── candle.py              # Candle
    ├── option.py              # Option (resposta de abertura)
    ├── position.py            # Position, DigitalPosition
    └── messages.py            # WSMessage, request_id helpers
```

## Protocolo (Baseado em HAR Analysis)

### Fluxo de Conexão

```
1. POST /v2/login          → SSID + token
2. WSS connect             → handshake
3. authenticate            → authenticated + client_session_id
4. setOptions              → ack
5. get-initialization-data → ativos (turbo/binary/blitz)
6. trading-settings.*      → comissões por ativo
7. get-balances            → saldos demo/real
```

### Abertura de Opção (binary-options.open-option v2.0)

```json
{
  "user_balance_id": 1067401182,
  "active_id": 76,
  "option_type_id": 12,
  "direction": "call",
  "expired": 1787795712,
  "refund_value": 0,
  "price": 1.0,
  "value": 1000000,
  "profit_percent": 82,
  "expiration_size": 120
}
```

Resposta: `{"name": "option", "msg": {"id": ..., "exp": ..., ...}}`

### Digital Options (digital-options.place-digital-option v3.0)

```json
{
  "user_balance_id": 1067401182,
  "instrument_id": "do1861A20260827D020200T1MC1F165852",
  "amount": "1",
  "instrument_index": 855584,
  "asset_id": 1861
}
```

O `instrument_id` e `instrument_index` vêm do evento `instrument-generated`.

### Subscriptions (subscribeMessage)

```json
{
  "name": "portfolio.position-changed",
  "version": "3.0",
  "params": {
    "routingFilters": {
      "user_id": 136879853,
      "user_balance_id": 1067401182,
      "instrument_type": "blitz-option"
    }
  }
}
```

Tipos: `blitz-option`, `turbo-option`, `binary-option`, `digital-option`

### Dispatch de Mensagens

O servidor retorna **duas respostas** para cada `sendMessage`:

1. `{"name": "result", "msg": {"success": true}}` — ack (ignorado)
2. `{"name": "<nome_real>", "msg": {...}}` — dados reais (resolvido)

### Heartbeat

O servidor envia `timeSync` a cada ~10s. A biblioteca usa isso para manter o clock sincronizado. Não é necessário enviar heartbeat de volta.

## API Completa

### IQOptionClient

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| `user_id` | `int` | ID do usuário |
| `balance_id` | `int \| None` | ID da conta selecionada |
| `server_time` | `int` | Tempo do servidor (ms) |
| `clock_offset` | `int` | Offset local↔servidor (ms) |
| `assets` | `AssetsManager` | Gerenciador de ativos |
| `trading` | `TradingManager` | Gerenciador de operações |
| `candles` | `CandlesManager` | Gerenciador de candles |
| `accounts` | `AccountsManager` | Gerenciador de contas |
| `subscriptions` | `SubscriptionsManager` | Subscriptions |
| `history` | `HistoryManager` | Histórico de posições |
| `events` | `EventsManager` | Eventos customizados |
| `reconnection` | `ReconnectionManager` | Reconexão automática |
| `session` | `SessionManager` | Dados da sessão |
| `connection_manager` | `ConnectionManager` | Estado da conexão |
| `operations` | `OperationsManager` | Tracking de operações |

### Métodos Principais

```python
# Conexão
await client.connect()
await client.disconnect()

# Operações
option = await client.place_call(active_id, amount, option_type, expiration_size=None)
option = await client.place_put(active_id, amount, option_type, expiration_size=None)
result = await client.wait_for_binary_result(option_id, timeout=300)
result = await client.wait_for_digital_result(digital_id, timeout=300)

# Digital
result = await client.trading.open_digital_option(
    asset_id=1861, direction=Direction.CALL, amount="1",
    instrument_id="do...", instrument_index=854712
)

# Candles
candles = await client.candles.get_history(active_id, period=60, count=100)
await client.candles.subscribe(active_id, period=60)
await client.candles.unsubscribe(active_id, period=60)

# Subscriptions
await client.subscribe_positions(InstrumentType.BLITZ_OPTION)

# Eventos
client.on_position_changed(callback)
client.events.on("event-name", callback)
```

## Exemplo Completo

```python
import asyncio
from iqoption_client import (
    IQOptionClient, Config, OptionType, Direction, InstrumentType
)

async def main():
    client = IQOptionClient()
    await client.connect()

    # --- Blitz (24h OTC) ---
    blitz = client.assets.find_open_active(OptionType.BLITZ)
    payout = client.assets.get_payout(blitz.id, OptionType.BLITZ)
    print(f"Blitz {blitz.id}: payout={payout}%")

    await client.subscribe_positions(InstrumentType.BLITZ_OPTION)

    call = await client.place_call(
        blitz.id, 1.0, OptionType.BLITZ, expiration_size=30
    )
    put = await client.place_put(
        blitz.id, 1.0, OptionType.BLITZ, expiration_size=30
    )
    print(f"CALL {call.id}, PUT {put.id}")

    # Aguardar expiry (30s + margem)
    await asyncio.sleep(50)

    await client.accounts.get_balances()
    print(f"Saldo: ${client.accounts.account.active_balance.amount:.2f}")

    # --- Turbo ---
    turbo = client.assets.find_open_active(OptionType.TURBO)
    call = await client.place_call(turbo.id, 1.0, OptionType.TURBO)
    result = await client.wait_for_binary_result(call.id, timeout=120)
    print(f"Turbo resultado: {result.result}")

    # --- Digital ---
    asset_id = 1861
    await client.subscribe_positions(InstrumentType.DIGITAL_OPTION)

    instrument_event = {"data": None}
    async def on_instrument(msg):
        inner = msg.get("msg", msg)
        if isinstance(inner, dict) and inner.get("asset_id") == asset_id:
            instrument_event["data"] = inner

    client.events.on("instrument-generated", on_instrument)
    await client._ws.subscribe(
        "digital-option-instruments.instrument-generated", "3.0",
        params={"routingFilters": {"instrument_type": "digital-option", "asset_id": asset_id}},
    )

    for _ in range(120):
        if instrument_event["data"]:
            break
        await asyncio.sleep(0.5)

    if instrument_event["data"]:
        evt = instrument_event["data"]
        call_items = [d for d in evt.get("data", []) if d.get("direction") == "call"]
        if call_items:
            pick = call_items[len(call_items) // 2]
            result = await client.trading.open_digital_option(
                asset_id=asset_id, direction=Direction.CALL, amount="1",
                instrument_id=pick["symbol"], instrument_index=evt["index"],
            )
            print(f"Digital: {result}")

    await client.disconnect()

asyncio.run(main())
```

## Licença

MIT
