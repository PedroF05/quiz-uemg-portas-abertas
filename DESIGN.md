---
name: Quiz UEMG de Portas Abertas
description: Quiz de salão ao vivo da UEMG — host em projetor, jogadores no celular
colors:
  stage-black: "#08101e"
  night-navy: "#0b1329"
  glass-card: "rgba(15, 23, 42, 0.45)"
  glass-border: "rgba(255, 255, 255, 0.08)"
  uemg-gold: "#f59e0b"
  uemg-amber: "#fbbf24"
  gold-glow: "#fde047"
  phone-blue: "#3b82f6"
  steel-text: "#e2e8f0"
  fog-muted: "#94a3b8"
  success-green: "#22c55e"
  danger-red: "#ef4444"
typography:
  display:
    fontFamily: "Outfit, Plus Jakarta Sans, system-ui, sans-serif"
    fontSize: "clamp(2.2rem, 5vw, 3.4rem)"
    fontWeight: 500
    lineHeight: 1.1
  question:
    fontFamily: "Outfit, Plus Jakarta Sans, system-ui, sans-serif"
    fontSize: "clamp(1.5rem, 3vw, 2.2rem)"
    fontWeight: 500
    lineHeight: 1.3
  title:
    fontFamily: "Outfit, Plus Jakarta Sans, system-ui, sans-serif"
    fontSize: "0.98rem"
    fontWeight: 600
  body:
    fontFamily: "Plus Jakarta Sans, system-ui, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 300
    lineHeight: 1.6
  label:
    fontFamily: "Plus Jakarta Sans, system-ui, sans-serif"
    fontSize: "0.62rem"
    fontWeight: 500
    letterSpacing: "0.16em"
    textTransform: "uppercase"
rounded:
  pill: "999px"
  xl: "24px"
  lg: "16px"
  md: "12px"
  sm: "9px"
spacing:
  xs: "4px"
  sm: "10px"
  md: "20px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.uemg-gold}"
    textColor: "#101827"
    rounded: "{rounded.lg}"
    padding: "15px 40px"
  button-ghost:
    backgroundColor: "rgba(30, 41, 59, 0.45)"
    textColor: "#cbd5e1"
    rounded: "{rounded.md}"
    padding: "7px 12px"
  card:
    backgroundColor: "{colors.glass-card}"
    textColor: "{colors.steel-text}"
    rounded: "{rounded.xl}"
    padding: "24px"
  chip:
    backgroundColor: "rgba(30, 41, 59, 0.45)"
    textColor: "#cbd5e1"
    rounded: "{rounded.pill}"
    padding: "7px 13px"
---

# Design System: Quiz UEMG de Portas Abertas

## Overview

**Creative North Star: "Palco de Vidro Noturno"**

O pátio do campus depois que o sol se põe: um céu azul-quase-preto onde flutuam painéis de
vidro escuro, e a única luz saturada é o dourado do letreiro do evento. A interface é um
palco — o fundo é atmosfera (gradientes radiais muito sutis de azul e âmbar sobre navy),
o conteúdo são superfícies translúcidas empilhadas sobre a escuridão, e a ação principal
é sempre um objeto dourado luminoso que parece iluminado por trás.

Duas audiências dividem o mesmo mundo: o operador vê o palco de longe (projetor, tela
cheia, alto contraste), e o jogador segura um fragmento do palco na mão (celular, mesmo
navy e dourado, alvos de toque generosos). O dourado é voz de comando: só aparece em
elementos que pedem ação ou celebram resultado — se tudo brilha, nada ilumina.

Os ícones são objetos 3D renderizados (PNGs locais, 160×160, exibidos entre 16 e 30px),
nunca emojis e nunca glifos de fonte — dão peso físico de troféus e utilidades de
protetor de mesa sobre o vidro.

**Key Characteristics:**
- Fundo navy profundo com 2–3 gradientes radiais atmosféricos (azul em cima, âmbar e azul nos cantos)
- Cards de vidro translúcido com borda branca de 8% e blur de fundo
- Dourado UEMG como único acento saturado; azul `#3b82f6` reservado a interação/seleção
- Tipografia Outfit (display) + Plus Jakarta Sans (corpo), pesos leves no corpo
- Ícones 3D PNG locais com `aria-hidden`, herdados de `icon()` em `core/dom.js`
- Cantos muito arredondados (24px cards, 16px botões, pills completas)

## Colors

Paleta noturna de dois vozes: neutros frios de aço fazem a estrutura, dourado quente faz
o comando. Verde e vermelho existem apenas como veredito, nunca como decoração.

### Primary
- **Dourado UEMG** (#f59e0b): a voz de comando do sistema. Botão primário, selo da marca,
  barra do relógio, foco de teclado, contagem de pontos. Nunca em fundos largos.
- **Âmbar Luz** (#fbbf24): dourado em texto sobre navy — nomes de equipe, valores, texto
  sobre elementos dourados escuros. Legibilidade do dourado quando ele precisa ser lido.

### Secondary
- **Azul Celular** (#3b82f6): interação e seleção — hover de opção, foco de input da
  equipe azul, links de estado. Frio para não brigar com o dourado.

### Tertiary
- **Verde Acerto** (#22c55e): exclusivamente veredito de acerto, em fundo translúcido
  (18%) com borda e texto verde-claro — nunca bloco sólido com texto branco.
- **Vermelho Erro** (#ef4444): exclusivamente veredito de erro, mesmo tratamento translúcido.

### Neutral
- **Preto Palco** (#08101e): fundo mais profundo — header, superposições, entradas de contraste.
- **Azul-Noite** (#0b1329): fundo da página, a base de toda a atmosfera.
- **Vidro Card** (rgba(15,23,42,0.45)): superfície translúcida padrão de cards.
- **Borda Vidro** (rgba(255,255,255,0.08)): todas as bordas de superfície; 6% em divisores internos.
- **Texto Aço** (#e2e8f0): corpo de texto padrão.
- **Cinza Neblina** (#94a3b8): texto funcional secundário (mínimo aceitável de contraste sobre navy).

### Named Rules
**The Dourado é Comando Rule.** O dourado saturado nunca passa de ~10% de qualquer tela.
Fundo dourado existe só no botão primário e no item ativo de segmentação; no resto, é
texto, borda ou barra.

**The Veredito Translúcido Rule.** Verde e vermelho aparecem como fundo translúcido (16–18%)
+ borda colorida + texto na família clara do próprio matiz (ex.: `#bbf7d0`, `#fecaca`) —
nunca bloco sólido com texto branco.

**The Fica no Navy Rule.** Nenhum azul claro de protótipo (#0b2a5b e vizinhos) em fundo,
botão ou detalhe. O mundo é escuro por decisão, não por falta de opção.

## Typography

**Display Font:** Outfit (fallback Plus Jakarta Sans, system-ui) — carregada localmente em
`/css/fonts/outfit-latin.woff2`, peso variável 300–700.
**Body Font:** Plus Jakarta Sans (fallback system-ui) — carregada localmente em
`/css/fonts/plus-jakarta-sans-latin.woff2`.

**Character:** Outfit dá o tom geométrico e de placar; Plus Jakarta Sans no peso 300 dá
calma e leitura confortável nos textos de apoio. A hierarquia vem do peso e da caixa
mais do que do tamanho.

### Hierarchy
- **Display** (500, até 3.4rem, lh 1.1): título do hero e telas de resultado.
- **Question** (500, clamp(1.5rem, 3vw, 2.2rem), lh 1.3): o texto da pergunta — o
  elemento mais lido do produto, sempre branco puro.
- **Title** (600, 0.98rem): títulos de card, cabeçalhos de seção.
- **Body** (300–400, 0.75–1.05rem, lh 1.5–1.6): tudo que explica, lista ou status.
- **Label** (500, 0.62–0.7rem, tracking 0.16em, uppercase): selos e badges — nunca
  abaixo de 11px de altura efetiva.

### Named Rules
**The Question é Branca Rule.** O texto da pergunta é `#fff` puro em Outfit — é a leitura
crítica do evento, não compete com acentos.

## Layout

Uma coluna central por tela, densidade calma. O host usa container até ~1100px (tela de
jogo) com grids 50/50 no lobby (equipes | temas+IA, depois configs | ação). O jogador
usa container até 540px em coluna única, tudo centrado, com ritmo de 16px entre blocos.

Espaçamento: ritmo base de 10px (compacto) e 20px (entre cards); cards com padding 24px;
gap 12px em grids de opções. Breakpoints do host: 960px (grids → 1 coluna) e 640px
(header empilha, opções → coluna única). O jogador é mobile-first e não precisa de
breakpoints — o container limita o resto.

## Elevation & Depth

**Vidro sobre escuridão.** A profundidade é construída em três camadas: a atmosfera de
gradientes no fundo (camada 0), o vidro translúcido com `backdrop-filter: blur(18–20px)`
(camada 1), e o objeto de ação com sombra dourada projetada (camada 2). As sombras dos
cards são neutras e profundas; o brilho dourado é privilégio de elementos de comando.

### Shadow Vocabulary
- **Elevação de card** (`0 20px 40px -24px rgba(0,0,0,0.7)` + `inset 0 1px 0 rgba(255,255,255,0.05)`): todo card de vidro; o inset simula a luz da borda do vidro.
- **Luz de comando** (`0 10px 24px -8px rgba(245,158,11,0.5)`): sob botão primário e pill ativo — o objeto parece retroiluminado.
- **Foco de proximidade** (`0 0 0 3px rgba(59,130,246,0.15)`): anel translúcido em foco de input.

### Named Rules
**The Glow é Privilégio Rule.** Sombra colorida dourada só em elemento de ação primária
ou estado ativo de segmentação. Cards e textos nunca brilham.

## Shapes

Vocabulário de cantos: 24px em cards (vidro grande), 16px em botões e opções, 12px em
elementos internos compactos, 9–10px em badges internos e inputs, 999px em pills.
Bordas de 1px na Borda Vidro fazem o papel de "corte do vidro"; elementos destacados
ganham borda colorida translúcida (55%) quando assumem estado. Nenhum canto reto no
sistema inteiro — o raio mínimo é 9px.

## Components

### Buttons
- **Shape:** retângulo 16px, altura ~48–54px no primário.
- **Primary:** gradiente horizontal dourado (#fbbf24 → #f59e0b 60% → #eab308), texto
  #101827 em Outfit 600, luz de comando sob o objeto, hover eleva +2px e intensifica a luz.
- **Ghost:** vidro translúcido (rgba(30,41,59,0.45)), borda vidro, texto #cbd5e1, hover
  clareia o vidro. Usado para ações de apoio (tela cheia, voltar).
- **Secundária (sec):** navy translúcido com borda vidro, texto aço — ações de fluxo
  ("Próxima", "Nova partida").
- **Focus:** outline 2px em Âmbar Luz com offset 3px.

### Cards / Containers
- **Corner Style:** 24px.
- **Background:** Vidro Card + blur 18–20px.
- **Border:** 1px Borda Vidro; sombra de elevação + inset de luz.
- **Internal Padding:** 24px (18px em telas estreitas).

### Chips
- **Style:** pill completa, vidro translúcido, texto #cbd5e1, ícone 3D de 24px dentro.
- **State:** ativo troca para fundo dourado com texto #101827 e luz de comando.

### Inputs / Fields
- **Style:** fundo rgba(8,16,30,0.75), borda rgba(51,65,85,0.7), raio 10–12px, texto
  Âmbar Luz nos valores, texto aço na digitação.
- **Focus:** borda azul (#60a5fa) + anel translúcido 3px; select customizado com seta
  SVG dourada a 15px da borda direita.

### Navigation
- Header sticky do host: marca (ícone 3D + logotipo + selo) à esquerda, ações ghost à
  direita; footer com atalhos de teclado em `kbd`. No jogador, header simples em Preto
  Palco com a mesma marca.

### Signature Component: Option do Jogo
A alternativa é a unidade visual mais importante: linha de vidro 16px com badge de letra
(32px, raio 9px, fundo rgba(8,16,30,0.75), letra em Âmbar Luz 600), texto aço à esquerda.
Estados: hover azula o vidro; acerto aplica o Veredito Translúcido verde; erro, vermelho;
eliminadas caem para 45% de opacidade. No celular, min-height 64px e fonte 1.25rem.

## Do's and Don'ts

### Do:
- **Do** usar `icon()` (PNGs 3D locais) com `aria-hidden` — nunca emoji.
- **Do** manter textos funcionais ≥ 11px e com contraste ≥ 4.5:1 sobre navy (Cinza
  Neblina #94a3b8 é o piso, nunca #64748b).
- **Do** reservar dourado para comando e veredito verde/vermelho para feedback de resultado.
- **Do** carregar fontes e ícones localmente — o sistema precisa funcionar sem internet.

### Don't:
- **Don't** usar o azul claro do protótipo (#0b2a5b e tons próximos) em fundos, botões ou detalhes — é a anti-referência do sistema.
- **Don't** usar texto branco sobre verde ou vermelho sólidos — veredito é translúcido com texto da família clara do matiz.
- **Don't** aplicar sombra dourada (glow) em cards, textos ou elementos de apoio.
- **Don't** usar gradient text ou fontes importadas de CDN.
