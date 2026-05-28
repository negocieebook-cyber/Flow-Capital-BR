# Flow Map Brasil

Flow Map Brasil é uma aplicação local para Windows que gera um PDF semanal sobre rotação setorial da bolsa brasileira e pode enviar o relatório pelo Telegram.

O relatório é educacional e informativo. Ele não recomenda compra ou venda de ativos. A análise por ação existe para explicar a rotação dos setores, mostrando confirmação interna, divergências, volume incomum e pontos de atenção.

## O que o sistema faz

- Baixa dados de ações brasileiras pela brapi.
- Usa yfinance como fallback quando a brapi falha.
- Calcula retorno semanal, força relativa, RS Ratio, RS Momentum, volume relativo, score e quadrantes RRG.
- Agrega ações por setor com confirmação interna.
- Gera narrativas automáticas sem linguagem de recomendação.
- Cria gráficos RRG setorial e RRG dos setores líderes.
- Gera PDF em `reports/`.
- Envia o PDF pelo Telegram, se configurado.
- Pode ser agendado no Agendador de Tarefas do Windows para sábado às 08:00.

## Instalar Python

Instale Python 3.11 ou superior em https://www.python.org/downloads/windows/.

Durante a instalação, marque a opção para adicionar Python ao PATH.

## Criar ambiente virtual

No PowerShell ou Prompt de Comando, dentro da pasta do projeto:

```powershell
python -m venv .venv
```

Ative no Windows:

```powershell
.venv\Scripts\activate
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

Instale o Chromium usado pelo Playwright para gerar PDF:

```powershell
python -m playwright install chromium
```

## Configurar Telegram

1. Abra o Telegram e procure por `@BotFather`.
2. Envie `/newbot`.
3. Escolha nome e usuário do bot.
4. Copie o `TELEGRAM_BOT_TOKEN`.
5. Cada pessoa que vai receber o relatório precisa enviar uma mensagem qualquer para o seu bot.
6. Para descobrir o `TELEGRAM_CHAT_ID` de cada pessoa, acesse no navegador:

```text
https://api.telegram.org/botSEU_TOKEN/getUpdates
```

Procure pelo campo `chat` e copie o `id`. Para enviar para mais de uma pessoa, use `TELEGRAM_CHAT_IDS` com os IDs separados por vírgula.

## Preencher .env

Crie um arquivo `.env` a partir de `.env.example`:

```text
BRAPI_TOKEN=
TELEGRAM_BOT_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui
TELEGRAM_CHAT_IDS=primeiro_chat_id,segundo_chat_id
DATABASE_URL=sqlite:///data/flow_map_brasil.db
```

O token da brapi é opcional, mas pode melhorar o acesso aos dados.

## Inicializar banco

```powershell
python -m app.main --mode init-db
```

Isso cria `data/flow_map_brasil.db` e as tabelas SQLite.

## Testar Telegram

```powershell
python -m app.main --mode test-telegram
```

Se estiver configurado corretamente, você receberá:

```text
Teste do Flow Map Brasil: integração com Telegram funcionando.
```

## Testar brapi

Depois de preencher `BRAPI_TOKEN` no `.env`, rode:

```powershell
python -m app.main --mode test-brapi
```

O teste consulta `BOVA11`, `PETR4`, `VALE3` e `ITUB4`, mostrando status, quantidade de linhas, datas disponíveis e colunas retornadas. Se algum ticker falhar, o teste continua nos demais e mostra o endpoint sem expor o token completo.

## Rodar relatório manualmente

```powershell
python -m app.main --mode weekly
```

O PDF será salvo em `reports/flow_map_brasil_YYYY-MM-DD.pdf`.

## Ativar Agendador de Tarefas

Os scripts detectam automaticamente a pasta do projeto a partir de `app\scheduler`.

Depois abra o PowerShell como administrador e rode:

```powershell
powershell -ExecutionPolicy Bypass -File app\scheduler\create_windows_task.ps1
```

Se preferir criar a tarefa pelo Prompt de Comando, rode como administrador:

```cmd
app\scheduler\create_windows_task.cmd
```

A tarefa será criada para rodar todo sábado às 08:00.

## Ver logs

```text
logs\weekly_report.log
```

Os logs mostram início da execução, tickers carregados, fonte usada, falhas por ticker, ativos válidos, setores válidos, caminho do PDF e status do Telegram.

## Editar setores e tickers

Edite diretamente:

```text
config/sectors_brazil.yml
```

Use tickers brasileiros sem `.SA`, por exemplo `PETR4`, `VALE3`, `BOVA11`.

## Alterar benchmark

Edite:

```text
config/user_settings.yml
```

Campo:

```yaml
market:
  benchmark: "BOVA11"
```

## Como interpretar o PDF

- `Leading`: força relativa e momentum acima de 100.
- `Weakening`: força relativa ainda alta, mas momentum abaixo de 100.
- `Lagging`: força relativa e momentum abaixo de 100.
- `Improving`: momentum acima de 100, mas força relativa ainda abaixo de 100.
- `Volume relativo`: volume financeiro da semana dividido pela média das últimas semanas.
- `Confirmação interna`: percentual de ações do setor com retorno relativo positivo e score acima de 60.
- `Score`: leitura de 0 a 100 que combina força relativa, momentum, volume e confirmação.
- `Narrativa`: explicação automática do movimento setorial, sem recomendação de investimento.

## Limitações das fontes gratuitas

Fontes gratuitas podem ter atrasos, indisponibilidade temporária, ajustes corporativos incompletos ou diferenças de volume. O sistema tenta brapi primeiro e yfinance depois, mas não interrompe o relatório inteiro por falha de um ticker.

Dados macro do Banco Central/SGS também podem ficar indisponíveis momentaneamente. Quando isso acontece, o PDF registra aviso e continua.

## Testes

```powershell
python -m pytest
```

Se `pytest` não estiver instalado:

```powershell
pip install pytest
```

## Disclaimer

Este relatório tem finalidade educacional e informativa. Não constitui recomendação de investimento, oferta de compra ou venda de ativos, nem substitui análise individual de risco. Dados podem conter atrasos, falhas ou inconsistências dependendo das fontes utilizadas.
