# Guia de Operação — Quiz UEMG de Portas Abertas

Manual operacional e prático para a equipe responsável por rodar o quiz no dia do evento.

---

## 1. Antes do evento (preparação prévia)

Realize estes passos antes de ir para o local da apresentação:

1. **Sincronizar dependências:**
   No diretório do projeto, garanta o ambiente pronto:
   ```bash
   uv sync
   ```
   Caso utilize Docker no dia, faça o pré-build da imagem com antecedência:
   ```bash
   docker compose build
   ```

2. **Configurar o arquivo `.env`:**
   Copie `.env.example` para `.env` se ainda não existir:
   ```bash
   cp .env.example .env
   ```
   Defina o provedor em `LLM_PROVIDER`:
   - `offline`: recomendado para estabilidade total, sem necessidade de internet ou chaves de API.
   - `gemini`: requer `GEMINI_API_KEY` válida do Google AI Studio. No plano gratuito a cota é de 20 requisições/dia por modelo; cota esgotada devolve `429 RESOURCE_EXHAUSTED`.
   - `local`: recomendado para o evento. Requer Ollama em execução (`ollama serve`) com o modelo baixado (ex.: `qwen3:4b`, 2,5 GB, ou `qwen2.5:3b-instruct`, 1,9 GB). `OLLAMA_THINK=false` desliga o raciocínio do Qwen3 e acelera a resposta.
   - `hf`: requer `HF_TOKEN`, créditos no Inference Providers e um modelo disponível na conta; sem crédito devolve `402 Payment Required`.

   Variáveis do modelo local:

   | Variável | Recomendado | Efeito |
   |---|---|---|
   | `OLLAMA_MODEL` | `qwen3:4b` | melhor qualidade; ~4,5 tok/s em CPU (Ryzen 7 5700U) |
   | `OLLAMA_TIMEOUT` | `420` | geração de 14 perguntas pode levar ~4 min; 180 s cortaria no meio |
   | `OLLAMA_NUM_CTX` | `4096` | 2048 fica apertado acima de 10 perguntas |
   | `OLLAMA_THINK` | `false` | desativa o modo thinking do Qwen3 antes da saída estruturada |

3. **Pré-gerar temas para contingência offline:**
   Gere previamente os temas desejados para que fiquem salvos em `data/temas/`. Isso evita lentidão e elimina o risco de falhas de rede no evento:
   ```bash
   uv run python scripts/gerar_temas.py --tema "Tecnologia e Inovação" --n 10 --provider local
   uv run python scripts/gerar_temas.py --tema "História da Computação" --n 10 --provider local
   uv run python scripts/gerar_temas.py --tema "Cultura Pop e Jogos" --n 10 --provider local
   ```
   Com `qwen3:4b` em CPU, cada tema de 10 perguntas leva cerca de 2,5 a 3 minutos — prefira gerar na véspera, nunca durante o evento. O script imprime o erro real e **não grava arquivo** se o provedor pedido cair para offline (comportamento esperado). No dia, os temas pré-gerados aparecem na lista do host com zero espera.

4. **Testar detecção de IP e QR Code:**
   Inicie o servidor e acerte a variável `PUBLIC_URL` no `.env` apenas se o IP da LAN não for detectado automaticamente ou se for usar uma rede com proxy/túnel.

5. **Equipamentos essenciais:**
   - Notebook com bateria 100% carregada.
   - Carregador/fonte do notebook.
   - Cabo de vídeo compatível com o projetor (HDMI ou VGA) e adaptadores se necessário.
   - Smartphone com plano de dados habilitado para roteamento (hotspot Wi-Fi).

6. **Plano B de rede (hotspot móvel):**
   Deixe configurado um ponto de acesso Wi-Fi (hotspot) no smartphone ou notebook. Wi-Fi institucional de campus frequentemente possui isolamento de clientes (client isolation), o que impede celulares de conversarem com o notebook.

---

## 2. Montagem e projeção no local

1. **Conexão física:**
   Conecte o notebook à tomada e plugue o cabo de vídeo no projetor.
2. **Resolução de tela:**
   Configure a saída de vídeo do sistema operacional em modo duplicar ou estender na resolução recomendada de 1920x1080 (Full HD) ou resolução nativa do projetor.
3. **Modo tela cheia:**
   No navegador com a tela do host aberta, pressione a tecla `F` para alternar para tela cheia e ocultar abas e barras do navegador.
4. **Áudio:**
   O sistema não emite efeitos sonoros obrigatórios. O foco é visual com timer sincronizado na tela.

---

## 3. Início do serviço

1. **Subir a aplicação:**
   No Linux/macOS:
   ```bash
   ./run.sh
   ```
   No Windows:
   ```cmd
   run.bat
   ```
   Via Docker Compose:
   ```bash
   docker compose up
   ```
   Ou com o perfil de modelo local Ollama:
   ```bash
   docker compose --profile local-llm up
   ```

2. **Conferir integridade:**
   Verifique se o serviço respondeu com status ok acessando pelo navegador ou terminal:
   ```bash
   curl -fsS http://localhost:8000/api/health
   ```
   A resposta esperada indica `status: "ok"` e `database: true`.

3. **Abrir a interface do apresentador (Host):**
   No notebook, abra o navegador em:
   ```
   http://localhost:8000
   ```

---

## 4. Conduzindo a partida (sessão)

1. **Criar a sessão:**
   Na tela inicial do host, clique para criar uma nova sessão.
2. **Exibição do QR Code:**
   O projetor exibirá o QR Code grande contendo a URL de acesso (`/play?room=CODIGO`) e o código alfanumérico de 6 caracteres da sala.
3. **Ingresso dos participantes:**
   - Até 2 equipes de até 3 participantes cada (máximo de 6 jogadores por sessão).
   - Cada jogador entra em `/play` de duas formas: escaneando o QR Code com a câmera do celular **ou** digitando o código da sala na tela inicial, no celular ou no PC.
   - Na tela do jogador (`play.html`), o participante escolhe sua equipe (Equipe A ou Equipe B) e informa seu nome/apelido.
   - O host acompanha na tela principal os nomes dos membros entrando em cada time.
4. **Iniciar a partida:**
   Com os times preenchidos, o host clica em "Começar".
5. **Dinâmica das perguntas:**
   - Cada pergunta tem 20 segundos de duração contados no servidor.
   - Ambas as equipes respondem simultaneamente.
   - A resposta é por equipe: o primeiro membro do time a tocar na alternativa trava a resposta daquela equipe na rodada.
   - Acerto vale 10 pontos base, com bônus de 5 pontos extras se responder na primeira metade do tempo (primeiros 10 segundos).
   - Ao fim dos 20 segundos ou após ambas as equipes responderem, o gabarito é revelado na tela do projetor e nos aparelhos dos jogadores.

---

## 5. Contingência e resiliência

### Falha 1: Client isolation no Wi-Fi do campus
- **Sintoma:** Os celulares conectam ao Wi-Fi da universidade, mas ao ler o QR Code a página não carrega (timeout ou conexão recusada).
- **Solução:**
  1. Desconecte o notebook do Wi-Fi do campus.
  2. Ative o Hotspot Wi-Fi (ponto de acesso pessoal) do notebook ou do smartphone de apoio.
  3. Conecte o notebook e os celulares de todos os jogadores a essa mesma rede hotspot.
  4. Reinicie o `./run.sh` para que o novo IP da LAN seja exibido no terminal e no QR Code, ou informe o IP explicitamente no `.env` em `PUBLIC_URL=http://<NOVO_IP>:8000`.

### Falha 2: Provedor de IA fora do ar, cota esgotada ou sem internet
- **Sintoma:** Erro ou demora excessiva ao tentar gerar tema customizado no lobby. O motivo real aparece na própria mensagem do host (o `detail` da geração), por exemplo:
  - `429 RESOURCE_EXHAUSTED` = cota gratuita do Gemini esgotada (20 requisições/dia por modelo);
  - `402 Payment Required` = conta Hugging Face sem créditos no Inference Providers;
  - `local: [Errno 111] Connection refused` = Ollama não está rodando ou `OLLAMA_BASE_URL` aponta para outro endereço;
  - `TimeoutError` = a geração passou do tempo limite do provedor.
- **Solução:**
  1. Na tela do host, selecione um tema pronto do banco curado ou temas pré-gerados em `data/temas/`.
  2. Se necessário, altere no `.env` a variável `LLM_PROVIDER=offline` para desativar chamadas remotas.
  3. O jogo funciona 100% autônomo sem internet.

### Falha 3: Desconexão ou queda de celular/PC de jogador
- **Sintoma:** Aparelho do participante travou, bloqueou a tela ou recarregou.
- **Solução:**
  1. O participante deve simplesmente reabrir o navegador e recarregar a página (F5/refresh).
  2. A URL mantém `?room=CODIGO` e o token de sessão salvo localmente no aparelho restabelece a conexão via WebSocket (`rejoin`) e recupera o estado da rodada com o tempo restante.
  3. Caso um time tenha outros membros ativos, os demais continuam podendo responder normalmente pela equipe.

---

## 6. O que fazer durante a partida

1. **Se a rede oscilar momentaneamente:**
   O motor do jogo e a contagem de tempo são mantidos no servidor (relógio monotônico). Quando os sockets reconectarem, o estado sincroniza automaticamente.
2. **Se o timer parecer congelado:**
   A contagem é feita no servidor; se a barra do navegador não animar, aguarde o reveal automático. O botão de próxima pergunta e a tecla `Espaço` só funcionam depois que o reveal é exibido.
3. **Se a aba do host for fechada ou recarregada por engano:**
   **Não recarregue a aba do host durante a partida.** O token do host fica apenas na memória daquela aba; ao recarregar, o vínculo com a sala é perdido e não há como retomá-la pela interface. Se acontecer, crie uma nova sessão, projete o novo QR Code e peça aos jogadores para entrar de novo. O histórico já persistido continua no SQLite.

---

## 7. Procedimentos após o evento

1. **Backup do banco de dados:**
   O arquivo SQLite em `data/quiz.db` contém todo o histórico de partidas e pontuações do evento. Faça uma cópia de segurança:
   ```bash
   cp data/quiz.db "data/backup_quiz_$(date +%Y%m%d_%H%M%S).db"
   ```
2. **Exportar o ranking final:**
   Consulte os melhores desempenhos diretamente pela API para premiação ou registro acadêmico:
   ```bash
   curl -fsS "http://localhost:8000/api/ranking?limit=50" > ranking_final.json
   ```
3. **Encerrar o servidor:**
   - Se estiver rodando via terminal (`./run.sh` ou `run.bat`): pressione `Ctrl+C`.
   - Se estiver rodando via Docker:
     ```bash
     docker compose down
     ```

---

## 8. Checklist operacional

### Pré-evento
- [ ] Dependências sincronizadas (`uv sync` executado com sucesso).
- [ ] Arquivo `.env` configurado com `LLM_PROVIDER` definido.
- [ ] Ollama em execução com o modelo baixado e testado (se `LLM_PROVIDER=local`).
- [ ] Temas curados pré-gerados com `scripts/gerar_temas.py` em `data/temas/`.
- [ ] Teste de leitura de QR Code efetuado com celular teste.
- [ ] Bateria do notebook 100% carregada e fonte na bolsa.
- [ ] Hotspot 4G/5G do celular testado como plano de contingência.

### Montagem
- [ ] Notebook ligado à tomada no local do evento.
- [ ] Cabo de vídeo conectado ao projetor e tela configurada em 1080p.
- [ ] Servidor iniciado via `./run.sh`, `run.bat` ou `docker compose up`.
- [ ] Verificação em `/api/health` retornando status ok.
- [ ] Interface do host aberta e modo tela cheia testado com a tecla `F`.

### Durante o evento
- [ ] QR Code projetado e visível para a plateia e equipes.
- [ ] Até 3 jogadores conectados por equipe confirmados no painel.
- [ ] Tecla `Espaço` ou clique do host utilizado para avançar as perguntas.
- [ ] Placar final apresentado na tela do projetor ao término de cada confronto.

### Pós-evento
- [ ] Cópia de backup criada para `data/quiz.db`.
- [ ] Dados de pontuação exportados via `/api/ranking`.
- [ ] Servidor encerrado de forma limpa.

---

## 9. Troubleshooting

| Sintoma | Causa provável | Ação recomendada |
|---|---|---|
| Celular lê o QR Code mas a página não carrega | Wi-Fi do campus com isolamento de clientes (client isolation) | Ligar o hotspot do notebook ou celular, conectar ambos nele e reiniciar o serviço |
| Erro `connection refused` ao tentar acessar `http://localhost:8000` | Servidor não foi iniciado ou a porta 8000 está ocupada | Rodar `./run.sh` e checar se outro processo usa a porta 8000 |
| Falha ao gerar perguntas ou demora excessiva | API externa com timeout, sem internet ou sem chave configurada | Mudar no `.env` para `LLM_PROVIDER=offline` e usar temas prontos; o motivo exato aparece na mensagem do host |
| Mensagem `429 RESOURCE_EXHAUSTED` na geração | Cota gratuita do Gemini esgotada (20 requisições/dia por modelo) | Trocar de chave/projeto, aguardar o reset da cota ou usar tema pronto/offline |
| Mensagem `402 Payment Required` na geração | Conta Hugging Face sem créditos no Inference Providers | Adicionar créditos, trocar o `HF_MODEL` para um modelo servido na conta ou usar `local`/`offline` |
| Detalhe mostra `local: [Errno 111] Connection refused` | Ollama não está rodando ou `OLLAMA_BASE_URL` aponta para outro endereço | Iniciar com `ollama serve` e conferir a porta 11434; depois reiniciar o servidor |
| Mensagem de erro de limite ao tentar entrar na equipe | Já existem 3 participantes na equipe escolhida | Orientar participantes extras a aguardar a próxima partida |
| Jogador desconectou durante a contagem | Celular bloqueou a tela, PC recarregou ou perdeu sinal temporariamente | Reabrir a página no navegador do aparelho; a URL mantém `?room=CODIGO` e o estado restaura automaticamente |
| Projeção no projetor com bordas cortadas | Resolução do monitor incompatível com o projetor | Ajustar a resolução no sistema operacional para 1080p e pressionar `F` |
| Resposta do time não foi aceita | Outro membro da mesma equipe já respondeu antes | Orientar a equipe que a primeira resposta enviada trava a rodada do time |
| Banco de dados corrompido ou inacessível | Falha de permissão no arquivo `data/quiz.db` | Verificar permissões de gravação da pasta `data/` |
