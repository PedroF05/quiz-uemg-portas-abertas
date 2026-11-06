# Quiz UEMG de Portas Abertas

## Como usar
1. Extraia o ZIP e abra o `index.html` no navegador (Chrome/Edge). Funciona 100% offline.
2. Projete na tela e aperte **F** para tela cheia.
3. As equipes falam a resposta; quem opera o notebook clica (ou aperta 1 a 4).
4. Acertou em menos de 10s = 15 pontos; depois disso = 10. Errou ou acabou o tempo = 0.
5. O ranking do dia fica salvo no navegador (use sempre o mesmo navegador).

## Editando as perguntas
Abra `perguntas.js` e copie/edite as linhas. Formato:
["Categoria","Pergunta","Resposta certa",["errada 1","errada 2","errada 3"]]

## Sugestão de roteiro para explicar o projeto
- O banco de perguntas foi gerado com uma IA (LLM) e revisado pela equipe.
- A página é HTML + CSS + JavaScript puro, sem internet.
- Mostrar `perguntas.js`: "a IA gera, a gente valida, o sistema sorteia".

## Modo IA ao vivo (opcional, precisa de internet)
1. **Versão gratuita:** crie uma chave em aistudio.google.com (Google AI Studio, plano free, sem cartão) e use a variável `GEMINI_API_KEY`. (Opcional/pago: `ANTHROPIC_API_KEY` com chave de console.anthropic.com.) Não coloque a chave no GitHub nem no HTML.
   Se o modelo padrão não funcionar no seu plano free, defina `MODELO` com outro modelo liberado no AI Studio.
2. No terminal, dentro da pasta:
   - Windows: `set GEMINI_API_KEY=sua_chave` e depois `python server.py`
   - Linux/Mac: `export GEMINI_API_KEY=sua_chave` e depois `python3 server.py`
3. Abra http://localhost:8000 (no Chrome).
4. Dê um nome para a IA, digite o tema (ou clique em 🎤 e diga, por exemplo, "Nina, tema jogos") e clique em Começar.
5. Se o tema ficar vazio, ou se a internet/IA falhar, o quiz usa o banco offline automaticamente.
Dica: antes do evento, teste vários temas e deixe o modo offline como plano B (abrindo o index.html direto).
