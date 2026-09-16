# Como instalar o plugin agente

> Se você recebeu esta pasta num .zip, abra o Claude Code e peça:
> **"instala o plugin desta pasta seguindo o INSTALAR.md dele"**. O próprio
> Claude faz tudo.

## 🤖 Se você é o CLAUDE lendo isto: instale você mesmo (com o fallback certo)

**Degrau 1 — CLI (tente primeiro, UMA vez cada):**

1. `claude plugin marketplace add "<caminho da pasta extraída>"` (a pasta que
   contém este arquivo)
2. `claude plugin install agente@agente`
3. `claude plugin install telegram@claude-plugins-official`
4. `claude plugin list` pra confirmar.

**Degrau 2 — se QUALQUER comando for bloqueado por permissão** (o Claude Code
trata mexer na própria configuração como ação sensível; acontece em muitas
máquinas, é normal, e é uma proteção real, não um obstáculo pra contornar):
**explique em uma frase por que foi bloqueado**, e peça pro dono digitar ele
mesmo, direto no chat, um comando de cada vez, esperando cada um terminar:

```
/plugin marketplace add <caminho da pasta extraída>
/plugin install agente@agente
/plugin install telegram@claude-plugins-official
```

Comando de barra digitado pelo próprio dono no chat é uma ação DELE, não sua,
e por isso passa onde a mesma ação vinda de você seria bloqueada — não é um
jeito de contornar a permissão, é o modelo de permissão funcionando como
deveria. Depois confirme com `claude plugin list` (só leitura, você pode
rodar) e siga em frente.

**Onde o zip foi extraído NÃO importa.** Se estiver dentro da pasta que vai
ser do agente, NÃO mova nada agora — instale dali e, só no FIM do setup,
recomende apagar/mover o instalador.

**Instalou? Siga DIRETO pro wizard — sem reiniciar nada:**

- Tente a skill `/agente:setup`. Se vier **"Unknown skill"** (normal
  quando o plugin foi instalado no meio da sessão), **não trave e não mande
  reiniciar**: abra `skills/setup/SKILL.md` na pasta extraída e **siga o
  wizard manualmente, passo a passo** — o resultado é idêntico (validado em
  instalação real). O comando de barra passa a existir nas próximas sessões.

## 🧑 Se você é um humano instalando na mão (sem pedir pro Claude)

Dentro do Claude Code, um comando por vez:

```
/plugin marketplace add <caminho da pasta extraída>
/plugin install agente@agente
/plugin install telegram@claude-plugins-official
```

Depois feche e reabra o Claude Code (ou rode `/reload-plugins`) e rode:

```
/agente:setup
```

## Requisitos

- Claude Code instalado e logado (assinatura Pro ou Max) — https://claude.com/claude-code
- Telegram no celular
- Windows, Mac ou Linux — **nenhum outro programa é necessário**
