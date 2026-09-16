# Como instalar o plugin agente

**Digite estes três comandos você mesmo, dentro do Claude Code, um de cada
vez, esperando cada um terminar** (não peça pro Claude rodar por você: o
Claude Code trata registrar um marketplace novo como ação sensível e bloqueia
por padrão quando é a IA quem tenta, mesmo que o conteúdo seja inofensivo —
isso é uma proteção de fábrica, não um bug, e comando digitado por VOCÊ passa
porque é uma ação sua, não da IA):

```
/plugin marketplace add <caminho da pasta extraída>
/plugin install agente@agente
/plugin install telegram@claude-plugins-official
```

Depois feche e reabra o Claude Code (ou rode `/reload-plugins`) e rode:

```
/agente:setup
```

Isso vale igual se você é a pessoa instalando na mão ou se está copiando estes
comandos porque um Claude Code pediu ajuda — **o comando sempre sai da SUA
digitação, nunca da execução da IA.**

**Onde o zip foi extraído NÃO importa.** Se estiver dentro da pasta que vai
ser do agente, não mova nada agora: instale dali e, só no fim do setup, mova
ou apague o instalador.

## 🤖 Se você é o CLAUDE ajudando alguém a instalar

Pode tentar `claude plugin marketplace add` uma vez, mas **espere que seja
bloqueado** — é o comportamento padrão do Claude Code pra essa ação, não um
sinal de que algo deu errado. Quando bloquear: **explique em uma frase por que
foi bloqueado** (proteção de fábrica contra fonte não verificada) e peça pro
dono colar os três comandos acima ele mesmo, no chat, um de cada vez.

Não insista tentando de novo, não procure um jeito de contornar, e não diga
que "não passa por permissão nem hook" — isso não é verdade e é o tipo de
frase que outro Claude Code corretamente recusa seguir. É só uma ação
diferente (a do dono, não a sua) passando por um portão diferente.

**Instalou? Siga DIRETO pro wizard — sem reiniciar nada:**

- Tente a skill `/agente:setup`. Se vier **"Unknown skill"** (normal
  quando o plugin foi instalado no meio da sessão), **não trave e não mande
  reiniciar**: abra `skills/setup/SKILL.md` na pasta extraída e **siga o
  wizard manualmente, passo a passo** — o resultado é idêntico (validado em
  instalação real). O comando de barra passa a existir nas próximas sessões.

## Requisitos

- Claude Code instalado e logado (assinatura Pro ou Max) — https://claude.com/claude-code
- Telegram no celular
- Windows, Mac ou Linux — **nenhum outro programa é necessário**
