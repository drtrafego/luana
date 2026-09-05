# Agente

Monte um agente com nome, personalidade e memória, que conversa por Telegram e
usa **o que o Claude Code já faz de fábrica**. A pasta é o agente. A sessão viva
é a vida dele.

O agente que você vai criar tem o nome que **você** escolher. Neste manual ele
aparece como `<Nome>` (o nome de exibição, por exemplo `Maria`) e `<nome>` (a
versão técnica, por exemplo `maria`). O plugin, que é a ferramenta que constrói,
se chama `agente` e não muda: por isso os comandos são `/agente:setup`,
`/agente:connect` e `/agente:doctor`, sejam quantos agentes forem.

**Este manual assume que o destino é um servidor.** Um agente que só existe
enquanto uma janela está aberta no seu computador serve para aprender e para
testar, mas não é funcionário de ninguém. A Parte 2 é o coração daqui.

---

## Índice

- [Parte 0, antes de começar](#parte-0-antes-de-começar)
- [Parte 1, o núcleo (todo mundo faz)](#parte-1-o-núcleo-todo-mundo-faz)
- [Parte 2, colocar no ar 24 horas](#parte-2-colocar-no-ar-24-horas-o-caminho-padrão)
- [Parte 3, a memória (é o que faz durar)](#parte-3-a-memória-é-o-que-faz-durar)
- [Parte 4, a disciplina que faz o agente confiável](#parte-4-a-disciplina-que-faz-o-agente-confiável)
- [Parte 5, os opcionais](#parte-5-os-opcionais)
- [Parte 6, quando dá errado](#parte-6-quando-dá-errado)
- [Parte 7, o que este repositório não resolve](#parte-7-o-que-este-repositório-não-resolve)
- [Parte 8, como saber que ficou igual](#parte-8-como-saber-que-ficou-igual)

---

# Parte 0, antes de começar

## 0.1 O que você vai construir

| | **Modo Servidor (o padrão)** | Modo Pessoal |
|---|---|---|
| Onde roda | num servidor Linux, 24 horas | no seu computador |
| O que segura de pé | serviço do systemd | uma janela de terminal aberta |
| No ar com a sua máquina desligada? | **sim** | não, computador dormindo é agente dormindo |
| Para quem | operação de trabalho, agente que atende gente | experimentar, aprender, aula |
| O que instala | este plugin, mais a unidade do systemd | só este plugin |

**O Modo Servidor é o caminho principal**, e é o que este manual detalha. O Modo
Pessoal continua aqui por um bom motivo: **é a forma mais rápida de provar que a
peça funciona antes de você mexer em systemd**. Depurar identidade, Telegram e
serviço ao mesmo tempo é o caminho mais longo que existe.

A recomendação prática: faça a Parte 1 inteira (vinte minutos, com a janela
aberta), veja o agente responder, e só então promova para serviço na Parte 2. O
núcleo é o mesmo nos dois, então nada do que você fizer na Parte 1 se perde.

## 0.2 Pré-requisitos

**Para todo mundo:**

| O que | Como conferir | Se faltar |
|---|---|---|
| Claude Code instalado e logado | `claude --version` | https://claude.com/claude-code |
| Assinatura Pro ou Max | esta sessão responde | sem login o agente não roda |
| Telegram no celular | você abre o app | é o canal de conversa |
| `git` | `git --version` | para clonar |

Referência conhecida boa do Claude Code: `2.1.251`. Mais antigo que isso, rode
`claude update` antes de começar.

**Para o Modo Servidor, acrescente:**

| O que | Como conferir | Por quê |
|---|---|---|
| Linux com systemd | `systemctl --version` | é ele que segura a sessão viva |
| Acesso `sudo` | `sudo -v` | a unidade vive em `/etc/systemd/system/` |
| O comando `script` | `which script` | o Claude Code precisa de terminal de verdade (Passo 9) |
| `curl` | `which curl` | é como a tarefa agendada entrega |
| Disco com folga | `df -h /home` | o canal acumula anexo (Passo 11) |

Faltando o `script`, instale o pacote `util-linux` (`sudo apt install util-linux`
ou `sudo dnf install util-linux`). Ele não é opcional, e o Passo 9 explica por
quê.

**Você não precisa ser administrador de sistemas.** Todo comando da Parte 2 vem
com o que ele faz, o que deve aparecer, e o que fazer quando não aparece. Se
alguma saída não bater com o descrito, pare ali e vá na Parte 6 em vez de
seguir.

## 0.3 As três perguntas que definem sua instalação

Responda antes de rodar qualquer coisa:

1. **Qual o nome do seu agente?** Passo 1.
2. **Servidor ou pessoal?** Se o agente vai trabalhar, é servidor: Parte 1 e
   depois Parte 2. Se é para experimentar, Parte 1 só.
3. **Vai querer algum opcional?** Áudio, Google, Google Ads, Meta. Todos ficam
   para a Parte 5, e nenhum é necessário para o agente funcionar. Se você não
   sabe, a resposta é não: dá para ligar depois, a qualquer momento.

---

# Parte 1, o núcleo (todo mundo faz)

Se o destino é o servidor, **faça esta parte já dentro dele**, conectado por SSH.
Assim a pasta, o login e o canal do Telegram nascem no lugar definitivo, e você
não precisa migrar nada depois.

## Passo 1, escolher o nome

**O que faz:** define como o agente se chama. Esse nome vai para a pasta, os
arquivos, o serviço e o jeito dele se apresentar. Trocar depois é chato, então
escolha com calma agora.

Você precisa de **duas versões do mesmo nome**:

- **Nome de exibição**, como ele se apresenta: `Maria`, `Tico`, `Jarvis`. Pode
  ter acento e maiúscula.
- **Nome técnico**, para pasta e serviço: `maria`, `tico`, `jarvis`. Precisa
  começar com letra minúscula e ter só letra minúscula, número, hífen e
  sublinhado. Sem acento, sem espaço.

**Comando** (confere formato e colisão de uma vez, trocando `maria` pelo seu):

```bash
NOME=maria
echo "$NOME" | grep -qE '^[a-z][a-z0-9_-]{1,30}$' && echo "formato ok" || echo "FORMATO INVALIDO"
systemctl list-unit-files 2>/dev/null | grep -q "^$NOME.service" && echo "JA EXISTE UM SERVICO COM ESSE NOME" || echo "nome livre"
id "$NOME" >/dev/null 2>&1 && echo "JA EXISTE UM USUARIO COM ESSE NOME" || echo "usuario livre"
```

**Deu certo se:** saiu `formato ok`, `nome livre` e `usuario livre`.

**Deu errado?** Formato inválido quer dizer acento, maiúscula ou espaço: escolha
outro. Nome já usado por serviço ou usuário quer dizer colisão: escolha outro, ou
seu agente vai brigar com algo que já existe. Evite também `claude`, `telegram`,
`network` e `systemd`, que confundem na hora de depurar.

## Passo 2, clonar o repositório

**O que faz:** traz o plugin para a máquina onde o agente vai viver.

**Comando:**

```bash
git clone https://github.com/drtrafego/luana.git ~/plugin-agente
ls ~/plugin-agente
```

**Deu certo se:** o `ls` mostra `skills`, `templates`, `.claude-plugin`,
`instalar.sh` e este `README.md`.

**Deu errado?** `git: command not found` quer dizer que falta o git. Erro de
permissão quer dizer que você não escreve em `~`: escolha outro destino.

**Atenção, e isso evita uma dor de cabeça no Passo 5:** esta pasta do plugin
**não é** a pasta do agente. São duas coisas separadas, e misturar as duas causa
o problema descrito lá. Recebeu isto num `.zip` em vez de clonar? Descompacte
numa pasta neutra e leia o `INSTALAR.md`.

## Passo 3, instalar o plugin no Claude Code

**O que faz:** registra o plugin, que traz os comandos `/agente:setup`,
`/agente:connect` e `/agente:doctor`.

**Comando**, dentro do Claude Code, **um por vez**, esperando cada um terminar:

```
/plugin marketplace add ~/plugin-agente
/plugin install agente@agente
/plugin install telegram@claude-plugins-official
```

Depois **feche e reabra o Claude Code**, ou rode `/reload-plugins`.

**Deu certo se:** `claude plugin list` mostra os dois plugins, e digitar
`/agente:` oferece as três skills.

**Deu errado?** Duas falhas são comuns e nenhuma é grave:

- **"Unknown skill"** quer dizer que o plugin entrou no meio da sessão. Feche e
  reabra o Claude Code. Com pressa? Abra `skills/setup/SKILL.md` na pasta do
  plugin e siga o wizard na mão: o resultado é idêntico.
- **Comando bloqueado por permissão.** O Claude Code trata mexer na própria
  configuração como ação sensível, e isso é normal. Comando de barra digitado por
  você no chat sempre funciona: digite você mesmo em vez de pedir para o
  assistente rodar.

## Passo 4, criar o bot no Telegram

**O que faz:** cria o bot que é a porta de entrada do agente, e devolve o token
que autoriza falar por ele.

**Comando:** no Telegram, procure **@BotFather** (o com selo azul) e:

1. Mande `/newbot`.
2. Informe o **nome de exibição**. Pode ter acento.
3. Informe o **@username**, único no Telegram inteiro e terminando em `bot`, por
   exemplo `maria_do_fulano_bot`.
4. Copie o **token**, no formato `123456789:AAH...`.

**Deu certo se:** você tem o token copiado e consegue abrir a conversa do bot
pelo @username.

**Deu errado?** "Username is already taken" quer dizer que alguém no mundo já
usou aquele nome: invente outro, o `@` não precisa ser bonito.

**O token é a chave do bot.** Quem tem ele fala pelo seu agente: não mande para
ninguém, não poste em grupo, não coloque em print. Vazou? No BotFather,
`/revoke` gera um token novo e mata o antigo na hora. Revogue primeiro, conserte
depois.

## Passo 5, criar o agente

**O que faz:** cria a pasta do agente e escreve os arquivos de identidade,
memória e socorro, com o nome que você escolheu.

Dois caminhos, mesmo resultado:

**Caminho A, o script** (recomendado no servidor):

```bash
bash ~/plugin-agente/instalar.sh
```

Ele pergunta o nome de exibição, o nome técnico e a pasta, valida tudo, escreve
os arquivos e, se você disser que é servidor, **gera o `<nome>.service` pronto**
para conferir e copiar no Passo 9. O script **não escreve em `/etc`**: essa parte
fica na sua mão, de propósito, porque ninguém deveria rodar de olhos fechados um
script que mexe na configuração do sistema.

**Caminho B, o wizard** (recomendado no Windows e para quem está começando):

```
/agente:setup
```

Ele conduz passo a passo, pergunta nome e personalidade, escreve os arquivos e
emenda no pareamento do Telegram.

**Deu certo se:** a pasta do agente tem esta cara:

```
<pasta do agente>/
├── CLAUDE.md              identidade: quem ele é, como fala, as regras dele
├── working-memory.md      o caderno do agora
├── TROUBLESHOOTING.md     guia de socorro, em português, para leigo
├── memoria/
│   └── MEMORY.md          o sumário do livro (só índice)
└── diario/                um arquivo por dia, AAAA-MM-DD.md
```

**Deu errado?** Wizard travado no meio deixa os arquivos já escritos: rode de
novo e diga o que já existe. Script reclamando do nome: volte ao Passo 1.

**Duas regras da pasta, e as duas já causaram problema real:**

1. **A pasta é só do agente.** Nada de zip do instalador, nada da pasta do
   plugin, nada de outro projeto dentro dela.
2. **Não abra sessões avulsas do Claude Code dentro dela.** O religar usa
   `--continue`, que retoma a sessão **mais recente** daquela pasta. Uma sessão
   solta ali é retomada no lugar do agente, e a conversa dele fica para trás.

## Passo 6, primeira partida, parear e trancar a porta

**O que faz:** acorda o agente pela primeira vez, autoriza o seu Telegram e fecha
a porta para o resto do mundo, na mesma ação.

**6.1 Grave o token.** Dentro do Claude Code:

```
/telegram:configure
```

O token vai para `~/.claude/channels/telegram/.env`, assim:

```
TELEGRAM_BOT_TOKEN=<COLE AQUI O TOKEN DO BOTFATHER>
```

**6.2 Acorde o agente**, uma linha só, num terminal novo:

```bash
cd "<pasta do agente>" && claude --channels plugin:telegram@claude-plugins-official
```

No Windows, o terminal é o Prompt de Comando (tecla Windows, `cmd`, Enter) e a
linha leva `/d`: `cd /d "<pasta>" && claude --channels ...`.

Essa janela **é** o agente acordado. Enquanto ela estiver aberta, ele está vivo.

**6.3 Pareie.** Mande qualquer mensagem para o seu bot pelo Telegram. Um código
de pareamento aparece na janela. Aprove com:

```
/telegram:access
```

**6.4 Tranque, agora e não depois.** O arquivo
`~/.claude/channels/telegram/access.json` precisa terminar assim:

```json
{
  "dmPolicy": "allowlist",
  "allowFrom": ["<SEU CHAT ID NUMÉRICO>"],
  "groups": {},
  "pending": {}
}
```

Com `dmPolicy` em `allowlist`, ninguém mais gera código de pareamento e só o seu
Telegram fala com o agente. Para liberar outra pessoa depois: destranque, pareie,
tranque de novo.

**Deu certo se:** você mandou "oi", ele respondeu, e o `access.json` tem o seu
chat id em `allowFrom` com a política em `allowlist`.

**Deu errado?** Nada acontecendo, confira se o comando tinha o pedaço
`--channels`. No Windows, pode aparecer aviso do Defender ou do firewall: é
**Permitir acesso**, e sem isso o bot não fala com o Telegram.

**Onde achar o seu chat id, e uma armadilha real.** Documentação antiga manda ler
o nome do arquivo dentro de `~/.claude/channels/telegram/approved/`. Esse
diretório é transitório e **pode estar vazio com tudo funcionando**: é o caso da
instalação de referência, `approved/` vazio e o agente no ar há meses. A fonte
confiável é o `allowFrom` do `access.json`:

```bash
python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.claude/channels/telegram/access.json')))['allowFrom'][0])"
```

Guarde esse número. Ele volta na Parte 3, e é lá que ler do lugar errado quebra
sem dar erro.

## Passo 7, as três provas

**O que faz:** prova que funciona de verdade. Não confie no comando que você
rodou, abra o resultado.

**Prova 1, a personalidade certa.** Mande "oi" pelo Telegram.

- **Deu certo se:** a resposta chega **e soa como a personalidade escolhida**.
- **Deu errado?** Resposta genérica quer dizer que o `CLAUDE.md` não foi lido:
  confira se ele está na pasta certa e reinicie a janela.

**Prova 2, é a mesma conversa nos dois lugares.** Digite na janela do terminal:
"de que a gente estava falando?".

- **Deu certo se:** ele responde lembrando do "oi" do Telegram. São a mesma
  cabeça, muda só a porta de entrada.
- **Deu errado?** Ele não lembrar quer dizer janela em outra pasta, ou mais de
  uma sessão na mesma pasta.

**Prova 3, ele anota o que importa.** Conte um fato pelo Telegram ("meu cachorro
chama Bidu") e abra o `working-memory.md`.

- **Deu certo se:** o fato está lá, escrito por ele.
- **Deu errado?** A seção de memória do `CLAUDE.md` não pegou. Rode
  `/agente:doctor`.

Passou nas três? **O núcleo está pronto.** Se o destino é o servidor, **feche
esta janela agora** e siga para a Parte 2: deixar a janela aberta enquanto o
serviço sobe é exatamente como se cria o erro 409.

Se você vai ficar no Modo Pessoal, guarde o comando de religar, que é o que você
vai usar todo dia:

```bash
cd "<pasta do agente>" && claude --continue --channels plugin:telegram@claude-plugins-official
```

Quer dois cliques em vez de comando? Peça ao próprio agente: "cria um atalho na
minha área de trabalho pra te acordar". Ele escreve o arquivo para você.

---

# Parte 2, colocar no ar 24 horas (o caminho padrão)

Aqui o agente deixa de depender de uma janela aberta. O systemd passa a segurar a
sessão: sobe sozinho no boot, levanta quando cai, e continua a mesma conversa.

Faça esta parte depois que as três provas do Passo 7 passaram.

## Passo 8, onde o agente vive: usuário, pasta e permissão

**O que faz:** cria uma conta dedicada só para o agente.

**Isto não é formalidade, e é o passo de segurança do manual.** No Passo 9 o
agente roda com `--dangerously-skip-permissions`, ou seja: **executa comando e
escreve arquivo sem pedir licença a ninguém**. Num servidor não há quem clique
"permitir", então essa flag é obrigatória. A consequência é direta: **o agente
pode fazer tudo o que o usuário dele pode fazer.**

**Por que não rodar como root**, dito sem rodeio: como root, "tudo o que o
usuário pode fazer" inclui apagar o sistema, ler as credenciais de todos os
outros serviços da máquina, e derrubar coisas que não têm nada a ver com ele. Um
comando mal formado deixa de ser um erro e vira um incidente. Com um usuário
comum, o estrago fica dentro da pasta dele.

**A armadilha que faz isso acontecer por acidente:** se você **esquecer a linha
`User=` no arquivo do serviço, o systemd roda como root**. Não avisa, não
reclama, e o agente funciona igual. Confira essa linha antes de ativar.

**Comando:**

```bash
sudo useradd -m -s /bin/bash <nome>          # usuário dedicado, com HOME próprio
sudo mkdir -p /opt/agentes/<nome>
sudo chown -R <nome>:<nome> /opt/agentes/<nome>
sudo chmod 700 /opt/agentes/<nome>           # só o agente lê a própria memória
```

Agora confirme o ambiente **do usuário novo**, que é o que o serviço vai usar:

```bash
sudo -u <nome> bash -lc 'which claude; echo $HOME; claude --version'
```

**Deu certo se:** as três linhas respondem: o caminho do binário (costuma ser
`/usr/local/bin/claude`), o HOME do usuário novo, e a versão. Anote os dois
primeiros, porque entram no serviço.

**Deu errado?**

- `which claude` não acha nada: o binário está instalado só no seu login.
  Descubra o caminho real com `which claude` no seu usuário e use o caminho
  absoluto no Passo 9.
- `claude --version` pede login: o Claude Code precisa estar logado **para esse
  usuário**. Entre com `sudo -u <nome> -i`, faça o login uma vez, e saia. Sem
  isso o serviço sobe e para pedindo autenticação, num laço.

**Atenção:** esse usuário **não deve ter `sudo`**. Se você criou e depois
adicionou ao grupo de administradores "para facilitar", desfaça: você acabou de
transformar o agente em root com passos extras.

**A pasta do agente e o HOME do usuário precisam bater com o que o Passo 5
criou.** Se você fez a Parte 1 logado como você mesmo, mova a pasta para
`/opt/agentes/<nome>` e ajuste o dono com o `chown` acima. E copie a configuração
do canal, que mora no HOME:

```bash
sudo cp -r ~/.claude/channels /home/<nome>/.claude/
sudo chown -R <nome>:<nome> /home/<nome>/.claude
sudo chmod 600 /home/<nome>/.claude/channels/telegram/.env
```

## Passo 9, escrever o `<nome>.service`

**O que faz:** ensina o systemd a manter o agente vivo.

**Comando:** crie `/etc/systemd/system/<nome>.service`, trocando os
placeholders. Se você usou o `instalar.sh`, o arquivo já está gerado: confira e
copie.

```ini
[Unit]
Description=Agente <Nome> - Claude Code Telegram
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<nome>
WorkingDirectory=/opt/agentes/<nome>
ExecStart=/usr/bin/script -qfec "/usr/local/bin/claude --continue --channels plugin:telegram@claude-plugins-official --dangerously-skip-permissions" /home/<nome>/<nome>-tty.log
Restart=always
RestartSec=10
Environment=HOME=/home/<nome>
Environment=PATH=/home/<nome>/.bun/bin:/home/<nome>/.local/bin:/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin

[Install]
WantedBy=multi-user.target
```

**Deu certo se:** `sudo systemd-analyze verify /etc/systemd/system/<nome>.service`
não reclama de nada.

**Deu errado?** Erro de sintaxe quase sempre é aspas do `ExecStart`: o comando
inteiro do Claude fica **dentro** das aspas duplas, e o arquivo de log fica fora.

### Cada linha que importa, e por que ela está aí

**`--continue`, o que faz o agente lembrar de tudo.** Retoma a MESMA conversa da
pasta em vez de abrir uma nova. Sem ele, cada reinício começa um agente amnésico,
que perdeu o fio do que estava fazendo. E com `Restart=always` os reinícios
acontecem: queda de rede, atualização, reboot. É a flag mais importante da linha,
e é ela que faz a memória entre reinícios existir.

**`--channels plugin:telegram@claude-plugins-official`, sem ele o bot fica
mudo.** É o que anexa o canal. Sem essa flag o processo sobe normalmente, o
`systemctl status` diz `active (running)`, e **nada chega no Telegram**. Bot
emudeceu depois de você mexer no serviço? Confira esta flag primeiro.

**`WorkingDirectory=`, a identidade do agente.** É dele que saem o `CLAUDE.md`, a
memória e a sessão que o `--continue` retoma. Apontar para a pasta errada dá um
agente sem personalidade e sem passado, e o sintoma é confuso: ele responde, mas
como se fosse outro.

**`Restart=always` e `RestartSec=10`.** Caiu (rede, memória, erro), o systemd
sobe de novo em dez segundos. Junto com o `--continue`, o agente volta na mesma
conversa. É o que transforma "programa que roda" em "serviço que fica no ar".

**`/usr/bin/script -qfec "..." <arquivo de log>`, o pulo do gato.** O Claude Code
espera um terminal de verdade. Sob o systemd não existe TTY, e sem esse embrulho
a sessão se comporta de forma errática ou não sobe. O `script` cria um pseudo
terminal, roda o comando dentro dele e ainda grava tudo num log. Não remova por
parecer supérfluo: é ele que segura a peça.

**`--dangerously-skip-permissions`, necessário e perigoso.** Explicado no Passo 8:
sem ela o agente trava esperando uma aprovação que ninguém vai dar; com ela, o
Passo 8 deixa de ser opcional.

**`User=`.** Sem esta linha o serviço roda como **root**. Confira que ela está
lá e que aponta para o usuário dedicado.

**`Environment=HOME=...`, o esquecimento clássico.** O systemd não herda o seu
ambiente. Sem `HOME`, o Claude Code não acha `~/.claude`: não acha login, nem
plugins, nem canal do Telegram, nem memória. O sintoma é um serviço reiniciando
em laço sem explicação clara.

**`Environment=PATH=...`, o segundo esquecimento clássico.** O PATH do systemd é
mínimo. Inclua o diretório do binário `claude` e o do runtime do plugin do
Telegram, que usa `bun`.

**Duas flags opcionais que a instalação de referência usa:** `--model` e
`--effort` fixam modelo e esforço de raciocínio (por exemplo
`--model claude-opus-5 --effort max`), e `--debug` deixa o log verboso enquanto
você ajusta. Nenhuma das três é necessária para funcionar.

## Passo 10, ativar e provar que está no ar

**O que faz:** liga o serviço, garante que ele volta sozinho depois de um reboot,
e confirma com evidência que está de pé.

**Comando:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now <nome>.service
```

O `enable` é o que faz o serviço **subir sozinho quando o servidor reiniciar**. O
`--now` liga agora, sem esperar o próximo boot.

**Deu certo se** os cinco comandos abaixo responderem assim:

```bash
systemctl is-enabled <nome>.service                   # enabled  (sobe no boot)
systemctl is-active  <nome>.service                   # active   (está rodando)
pgrep -af "claude .*--channels" | wc -l               # 1, nunca 2
journalctl -u <nome>.service -n 30 --no-pager         # sem laço de reinício
find /opt/agentes/<nome> -name CLAUDE.md              # a pasta certa está lá
```

**E a prova que vale mais que todas:** mande uma mensagem pelo Telegram e receba
a resposta. **Serviço ativo com bot mudo é o estado de falha mais comum**, e
nenhum comando de status pega isso.

Confirme também que a conversa está sendo gravada, porque é dela que o
`--continue` vive:

```bash
ls -lt /home/<nome>/.claude/projects/<pasta-com-traços>/*.jsonl | head -3
```

O `<pasta-com-traços>` é o caminho da pasta do agente com as barras viradas
traços: `/opt/agentes/maria` vira `-opt-agentes-maria`. O `.jsonl` mais recente
precisa ter sido **modificado agora**, depois da sua última mensagem.

**Deu errado?** Serviço reiniciando em laço, vá para a Parte 6, que lista os
quatro suspeitos na ordem.

## Passo 11, operar no dia a dia

Esta é a parte que ninguém escreve e todo mundo precisa. São quatro tarefas.

### 11.1 Ver se está viva

```bash
systemctl status <nome>.service --no-pager
```

Leia três coisas na saída: **`Active:`** (quer dizer `active (running)`), o
**tempo desde que subiu** (`since ...`), e o **`Main PID`**. Um serviço que
mostra poucos minutos de vida toda vez que você olha está reiniciando em laço,
mesmo dizendo `active`.

### 11.2 Ler o log

```bash
journalctl -u <nome>.service -n 50 --no-pager       # as últimas 50 linhas
journalctl -u <nome>.service -f                     # acompanhar ao vivo (Ctrl+C sai)
journalctl -u <nome>.service --since "1 hour ago"   # a última hora
```

O log completo do terminal também fica no arquivo do `script`
(`/home/<nome>/<nome>-tty.log`), e ele é mais verboso.

### 11.3 Reiniciar, e o cuidado que custou caro

```bash
sudo systemctl restart <nome>.service
```

**Reiniciar não é de graça, e este aviso é conhecimento pago.** O processo **não
drena o que está em voo**: mensagem que estava chegando naquele instante
simplesmente some. Não vai para fila, não é reentregue depois, e ninguém é
avisado. Numa operação real, um `restart` engoliu **três mensagens de clientes**
exatamente assim.

A regra que sai disso: **reiniciar por reflexo é caro.** "Vou reiniciar para ver
se resolve" pode custar a mensagem de um cliente que você nunca vai saber que
existiu.

**Antes de todo restart, confira se há conversa em andamento:**

```bash
find /home/<nome>/.claude/projects/<pasta-com-traços>/ -name '*.jsonl' -mmin -5
```

**Vazio quer dizer sem atividade nos últimos cinco minutos: pode reiniciar.**
Voltou algum arquivo, alguém está falando com ele agora: espere.

E quando o restart for inevitável no meio do movimento, avise quem está do outro
lado antes, principalmente se o agente atende cliente. Uma linha de "vou reiniciar
aqui, me manda de novo se algo se perder" resolve o que a infraestrutura não
resolve.

**Reinicie de propósito, em janela de silêncio.** Depois de mexer no `.service`,
lembre do `daemon-reload`:

```bash
sudo systemctl daemon-reload && sudo systemctl restart <nome>.service
```

Para desligar de verdade (por exemplo, para abrir uma janela manual com canal):

```bash
sudo systemctl stop <nome>.service      # para agora
sudo systemctl start <nome>.service     # liga de novo
```

### 11.4 Quando o servidor reinicia

Com `enable` feito no Passo 10, o agente sobe sozinho. **Confirme mesmo assim**,
porque subir e falar são coisas diferentes:

```bash
systemctl is-enabled <nome>.service     # enabled
systemctl is-active  <nome>.service     # active
```

E mande um "oi" pelo Telegram. Reboot é o momento clássico de aparecer o cache
travado de MCP: se ele estiver mudo, apague
`/home/<nome>/.claude/mcp-needs-auth-cache.json` e reinicie o serviço.

### 11.5 A manutenção que ninguém lembra: o disco

O canal do Telegram **guarda todo anexo que chega e nunca limpa**. Na instalação
de referência, `~/.claude/channels/telegram/inbox/` acumulou **609 MB em 932
arquivos** em menos de um mês, só de áudio. Num servidor pequeno isso enche o
disco, e disco cheio derruba o agente de um jeito difícil de diagnosticar.

```bash
du -sh /home/<nome>/.claude/channels/telegram/inbox     # quanto está ocupando
find /home/<nome>/.claude/channels/telegram/inbox -type f -mtime +30 -delete
```

O segundo comando apaga anexo com mais de trinta dias. **Rode o `du` primeiro e
confira o que vai sair.** Se o agente precisa consultar anexo antigo, aumente o
prazo em vez de apagar.

## Passo 12, a regra que não tem exceção: nunca duas instâncias

Dois processos com o mesmo token disputam o canal e o Telegram devolve **erro
409**. O resultado prático é bot mudo, e nem sempre é óbvio, porque o serviço
continua `active`.

Acontece de dois jeitos na vida real: você abrir uma janela manual com
`--channels` enquanto o serviço está no ar, ou dois serviços apontando para o
mesmo bot.

**Antes de abrir qualquer janela com canal:**

```bash
sudo systemctl stop <nome>.service
```

**Para conferir a qualquer momento:**

```bash
pgrep -af "claude .*--channels" | wc -l    # tem que dar 1
```

Deu 2 ou mais, encerre o que não deveria estar lá e reinicie o serviço.

**Dois agentes diferentes no mesmo servidor podem conviver**, desde que cada um
tenha o seu bot, o seu token, a sua pasta e o seu `HOME`. O que não pode é dois
processos com o mesmo token.

---

# Parte 3, a memória (é o que faz durar)

Esta é a parte que quase nenhum manual escreve, e é a que separa um agente que
serve por meses de um que afoga na própria anotação em duas semanas. Não pule por
ser a menos técnica.

O número que justifica a seção: na instalação de referência o `working-memory.md`
chegou a **842 linhas** porque virou um segundo diário. Foi preciso mover o
histórico inteiro para os diários e arquivar a versão antiga. Hoje ele tem 297.

## Os três níveis, e o que vai em cada um

Três, não dois. Confundir os níveis é exatamente como o caderno vira diário.

**1. `working-memory.md`, o caderno do agora.** Fato novo, decisão tomada, tarefa
em aberto: escreve na hora, no mesmo turno, sem esperar "o momento certo". É o
único nível que se **apaga**: o que virou permanente sobe para o livro e **sai
daqui**. Passou de umas 100 linhas, está virando diário.

**2. `memoria/`, o livro de longo prazo.** Arquivos de texto comuns, que o dono
pode abrir e ler quando quiser.

- `memoria/MEMORY.md` é **só o sumário**: uma linha por assunto, apontando o
  arquivo da seção. Nunca conteúdo. Referência real: 74 linhas indexando 15
  seções.
- As seções são os arquivos ao lado (`familia.md`, `trabalho.md`,
  `clientes.md`). Seção passando de umas 200 linhas se divide em duas, e as duas
  entram no sumário.

**3. `diario/AAAA-MM-DD.md`, o que aconteceu no dia.** Cerca de dez linhas por
dia. **É aqui que vai o episódio**, nunca na memória. É o registro que sobrevive
quando o sistema apaga o histórico bruto da conversa. Diário não tem limite de
tamanho e ninguém o enxuga: ele é histórico, cresce mesmo.

## As três travas de escrita

Valem para toda linha escrita em `memoria/`.

**1. A regra, não a história.** O episódio vai para o diário. Na memória fica só
o que muda o que o agente faz amanhã. Cinco parágrafos contando que errou não
consertam o erro; um parágrafo dizendo como se faz, sim.

**2. Sem duplicidade.** Antes de escrever, procure se o assunto já existe e
**edite aquela linha**. Um tema, um lugar. A mesma regra em três arquivos vira
três verdades que envelhecem separadas, e um dia se contradizem.

**3. Sem contradição.** Regra nova que muda uma antiga **substitui** a antiga,
não convive com ela. Achou duas se contradizendo, não escolha sozinho: meça qual
é a verdade hoje e, se não der para medir, pergunte ao dono.

## O critério que decide tudo

Do dono da instalação de referência, e vale citar como está:

> "Se aquele ponto está lá, ele está lá por alguma coisa: ele está lá pra não
> repetir um padrão. Então é isso que deve estar."

Antes de escrever qualquer linha: **qual padrão isto impede de repetir?** Se você
não consegue responder numa frase, aquilo é diário, não é memória.

**E só entra o que o agente usa.** Número de contrato, CNPJ, endereço e nome de
pessoa atendida não moram em memória nenhuma: viram ruído entre o agente e o que
importa, e no caso de dado de cliente é informação que não deveria ficar guardada
ali.

**O teste antes de gravar:** isto muda alguma decisão minha? Se não muda, não
entra.

## A rotina que mantém isso vivo

Sem a rotina, os três níveis viram três lugares para a mesma bagunça. Todo dia,
ou pelo menos a cada três dias:

1. Reler o dia.
2. Atualizar o `working-memory.md`: refrescar o agora, riscar o resolvido.
3. **Promover o que virou permanente para a seção certa, e apagar da origem.**
   Promover sem apagar é duplicar.
4. Caçar contradição. Achou, e não dá para medir qual vale? Pergunte ao dono.
5. Escrever o diário do dia, umas dez linhas.
6. Atualizar a data da última manutenção no topo do `working-memory.md`.
7. Fechar com um resumo de duas ou três linhas para o dono.

O agente é o guardião do próprio prazo: passados três dias ou mais, ele mesmo
pede autorização, no máximo um lembrete por dia. Sob demanda funciona também:
"faz sua manutenção de memória".

Algo parecendo errado (mudo, lento, esquecido)? Rode `/agente:doctor`. Ele mede
os arquivos, mostra o inchaço, arruma perguntando antes de mudar e salva um
relatório técnico **sem nenhum dado pessoal**, pronto para enviar a quem entregou
o plugin.

## Tarefas agendadas: a corrente de avulsos

**Nunca crie tarefa agendada repetitiva.** O agendamento repetitivo nativo tem
bug conhecido e para de rodar **em silêncio**, que é o pior jeito de falhar.

Use a **corrente de avulsos**: cada tarefa é um agendamento único que, ao rodar,
(1) faz o trabalho, (2) entrega o resultado e (3) **agenda a próxima ocorrência**.
Se um elo cair, o agente recria o seguinte na primeira oportunidade.

**A execução agendada não é a sessão viva**, e por isso **não tem o Telegram
anexado**. A entrega sai pela API do Bot, com `curl`:

```bash
TOKEN=$(grep TELEGRAM_BOT_TOKEN ~/.claude/channels/telegram/.env | cut -d= -f2)
CHATID=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.claude/channels/telegram/access.json')))['allowFrom'][0])")
curl -s "https://api.telegram.org/bot$TOKEN/sendMessage" -d "chat_id=$CHATID" \
  --data-urlencode "text=<a mensagem, em texto puro, sem markdown>"
```

**Repare de onde vem o chat id: do `allowFrom` do `access.json`, não do
`approved/`.** Ler do lugar errado é a falha que quebra calada, porque o
`approved/` pode estar vazio numa instalação saudável e o `curl` simplesmente não
entrega nada, sem erro na tela.

---

# Parte 4, a disciplina que faz o agente confiável

Memória arrumada resolve metade do problema. A outra metade é o agente **não
afirmar o que não conferiu**, e a operação **não perder o que já foi corrigido**.
São quatro hábitos, e nenhum deles precisa de ferramenta nova.

## 4.1 Conferir o resultado, nunca o comando

O erro mais caro que um agente comete não é errar: é **dizer que deu certo sem
olhar**. `curl` que retornou `200` não prova que a página está certa; script que
rodou sem erro não prova que gravou o arquivo; `{"id": "..."}` de uma API não
prova que o objeto ficou como você queria.

A regra, que já vem escrita no `CLAUDE.md` do agente: **abra o resultado**. A
imagem pelo visualizador, o arquivo relendo do disco, a página por uma chamada
de fora, o registro relido da API. **Não conferiu, não afirma:** diz que ainda
não conferiu, o que é uma resposta perfeitamente aceitável e infinitamente
melhor que uma afirmação falsa.

## 4.2 O verificador: o que impede a correção de voltar

**O problema que ele resolve.** Você corrige algo, confere na mão, e fica
satisfeito. Semanas depois o mesmo defeito está de volta. Isso acontece porque
**conferência na mão morre junto com a sessão**: o próximo agente (ou o próximo
você) começa sem ela e reintroduz o mesmo problema, sem má fé nenhuma.

**A solução é um script que lê o estado real e reprova sozinho.** Ele não
conserta nada: ele mede e imprime APROVADO ou REPROVADO, item por item.

As três regras que fazem um verificador valer alguma coisa:

1. **Ele lê o ESTADO REAL**: o arquivo no disco, o processo vivo, o registro no
   banco, a resposta da API. Nunca a documentação, nunca "foi corrigido ontem",
   nunca o que um agente relatou.
2. **Se não consegue medir, diz INDETERMINADO, nunca APROVADO.** Rede fora e
   "está tudo certo" são coisas diferentes, e confundir as duas é pior que não
   ter verificador.
3. **Ele roda sozinho e avisa só quando reprova.** Verificador que depende de
   alguém lembrar de rodar é uma conferência na mão com passos extras.

Um esqueleto que já serve, e cresce com você:

```bash
#!/usr/bin/env bash
# verificar.sh - as correções continuam de pé? Saída 0 = tudo certo, 1 = reprovou.
FALHAS=0
checar() {  # checar "<nome>" <comando...>
  local nome="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "APROVADO   $nome"
  else
    echo "REPROVADO  $nome"; FALHAS=$((FALHAS+1))
  fi
}

checar "serviço no ar"          systemctl is-active --quiet <nome>.service
checar "só uma instância"       test "$(pgrep -cf 'claude .*--channels')" -eq 1
checar "acesso trancado"        grep -q '"dmPolicy": *"allowlist"' ~/.claude/channels/telegram/access.json
checar "caderno não inchou"     test "$(wc -l < /opt/agentes/<nome>/working-memory.md)" -lt 100
checar "sumário é índice"       test "$(wc -l < /opt/agentes/<nome>/memoria/MEMORY.md)" -lt 40
checar "disco do inbox"         test "$(du -sm ~/.claude/channels/telegram/inbox | cut -f1)" -lt 500

echo; [ "$FALHAS" -eq 0 ] && echo "tudo aprovado" || echo "$FALHAS item(ns) reprovado(s)"
exit $([ "$FALHAS" -eq 0 ] && echo 0 || echo 1)
```

Depois é só agendar e mandar avisar quando reprovar:

```
0 8,14,20 * * * /opt/agentes/<nome>/verificar.sh || /opt/agentes/<nome>/avisar.sh
```

**A regra de ouro na hora de fechar uma correção:** não pergunte "está certo
agora?", pergunte **"o que impede isto de voltar sem ninguém ver?"**. Se a
resposta for "eu vou lembrar", não impede nada: vira uma linha no verificador.

## 4.3 Um arquivo por ferramenta conectada

Conforme o agente ganha acesso a coisas (um banco, um painel, uma API, um
serviço de e-mail), cria-se uma pasta `conexoes/` na pasta dele, com **um
arquivo curto por ferramenta**. Cada arquivo responde quatro perguntas:

- **O que é**, em duas linhas, e para que o agente usa.
- **Como se conecta**: o comando, o endpoint, a biblioteca.
- **Onde mora a credencial**: o caminho do arquivo e o **nome** da variável.
  **Nunca o valor.**
- **O que já deu errado ali**, e como se resolveu.

Isso evita duas coisas que corroem operação: o agente redescobrir na marra a
mesma integração toda semana, e credencial espalhada em lugar que ninguém
lembra. E dá para compartilhar o mesmo arquivo entre dois agentes, cada um com
as suas credenciais na própria pasta.

## 4.4 Quem faz não é quem aprova

Quando o agente delega trabalho a subagentes (e conforme a operação cresce, ele
delega), vale a regra que qualquer equipe boa usa: **o revisor não é quem
executou**. Quem fez está comprometido com a própria solução, e revisar o
próprio trabalho é a forma mais educada de não revisar nada.

Três pontos que fazem essa revisão valer:

- **O mandato é adversarial.** Não é "confirme que está certo", é **"tente
  quebrar"**.
- **O revisor entrega prova, não parecer.** Cada afirmação vem com o comando que
  a produziu.
- **Não deu para testar de verdade? O revisor diz isso.** Cobertura menor
  declarada honestamente vale mais que cobertura fingida.

**E o alerta que só se aprende apanhando:** subagente que **não devolveu
relatório é subagente que NÃO RODOU**. Um agente esperando um resultado que
nunca chegou tende a preencher o vazio com o que seria plausível, e conclusão
certa por caminho inventado continua sendo invenção. Silêncio é **ausência de
resultado**, nunca resultado vazio, e se diz isso em vez de completar.

---

# Parte 5, os opcionais

Nenhum é necessário para o agente funcionar. Leia a linha "para quem serve" de
cada um e pule sem culpa se não for o seu caso.

## 5.1 Áudio: ele escuta suas mensagens de voz

**Para quem serve:** quem manda áudio no Telegram em vez de digitar. Sem isto o
agente avisa honestamente que não escuta e pede por texto.

O agente já enxerga foto e lê documento de fábrica. Só o áudio precisa de ajuda,
porque o modelo não tem ouvido: liga-se um serviço que vira voz em texto. Dois
caminhos, configurados num `audio.json` na pasta do agente.

**Caminho 1, Groq (recomendado).** Faixa grátis generosa (2.000 transcrições e
oito horas de áudio por dia), sem cartão. Crie a chave em
https://console.groq.com/keys, clique em `+ Create API Key`, dê um apelido e
copie a chave, que começa com `gsk_`. Ela **aparece uma vez só**: se fechar sem
copiar, apague e crie outra, leva trinta segundos.

```json
{ "provider": "groq", "groq_api_key": "<COLE AQUI SUA CHAVE gsk_>", "modelo_local": "small" }
```

**Caminho 2, local.** Grátis e privado, o áudio não sai da máquina. Em troca
precisa de Python, baixa um modelo de uns 500 MB na primeira vez e, sem placa
NVIDIA, fica lento. O wizard escreve o `transcrever.py` e grava
`"provider": "local"`.

**Como testar:** mande um áudio pelo Telegram. Ele deve responder reconhecendo o
que você falou.

**Deu errado?** Na Groq, dois detalhes da chamada não podem mudar: o
`;filename=audio.ogg` (ela valida pela extensão e recusa `.oga` com HTTP 400) e o
cabeçalho `User-Agent` (sem ele o Cloudflare devolve 403, `error code: 1010`).
Não resolveu? Grave `"provider": "off"` e siga: o agente volta a pedir por texto
e tudo o mais continua funcionando.

## 5.2 Google: Drive, Gmail e Agenda

**Para quem serve:** quem quer o agente lendo e-mail, arquivo e compromisso.

Não precisa de Google Cloud nem de OAuth na mão: são os **connectors nativos** do
Claude Code.

```
/agente:connect
```

Ou, na mão: rode `/mcp`, autorize **Google Drive**, **Gmail** e **Google
Calendar** um de cada vez no navegador, com a conta que o agente deve enxergar, e
confirme no `/mcp` que ficaram conectados.

**O passo que todo mundo esquece:** as conexões valem **por sessão**. Depois de
autorizar, **reinicie o serviço** (ou religue a janela, no Modo Pessoal). A
sessão que já estava de pé continua sem enxergar as ferramentas novas. Lembre do
cuidado do Passo 11.3 antes de reiniciar.

**Como testar:** peça pelo Telegram "vê meus próximos eventos da agenda".

**Deu errado?** Se ele diz que não tem essas ferramentas, quase sempre é o
reinício. Se nenhum connector do Google aparece no `/mcp`, a conta ou o plano
dessa pessoa pode não ter os connectors habilitados: **não é defeito do plugin**,
e não há nada para consertar na pasta do agente.

**Privacidade, dita e não implícita:** conectar dá ao agente acesso real de
leitura e escrita nos serviços escolhidos. Conecte só o que fizer sentido. Para
desligar, remova a autorização pelo `/mcp` ou revogue na sua Conta Google, e
reinicie.

## 5.3 Skills do Google Ads e Analytics

**Para quem serve:** quem gerencia Google Ads ou Google Analytics e quer o agente
consultando conta, diagnosticando queda e montando relatório. Quem usa o agente
para outra coisa não precisa disto.

**O que instala:** skills de texto, do repositório oficial
`github.com/google/skills`. A instalação de referência usa o commit `eba988f`,
clonado em 04/09/2026, e escolheu **6 das 17**:

- `finding-google-skills` (localiza a skill certa sob demanda)
- `google-ads-api-quickstart`
- `google-ads-api-account-diagnostics`
- `google-ads-api-mcp-setup`
- `google-analytics-admin-api-basics`
- `google-analytics-data-api-basics`

**Por que 11 ficaram de fora**, e o critério serve para a sua escolha também: as 6
de `google-mobile-ads-*` e as 2 de `ima-*` são do lado de **quem vende espaço
publicitário**, e uma agência de tráfego está do lado de **quem compra**; as 3 de
`data-manager-*` exigem projeto no Google Cloud, que é uma decisão de infra à
parte.

```bash
git clone https://github.com/google/skills.git /tmp/google-skills
sudo mkdir -p /opt/skills_comuns
for s in finding-google-skills google-ads-api-quickstart \
         google-ads-api-account-diagnostics google-ads-api-mcp-setup \
         google-analytics-admin-api-basics google-analytics-data-api-basics; do
  sudo cp -r "/tmp/google-skills/$s" /opt/skills_comuns/
  sudo -u <nome> ln -sfn "/opt/skills_comuns/$s" "/home/<nome>/.claude/skills/$s"
done
```

Symlink em `~/.claude/skills/` do usuário do agente, em vez de cópia dentro da
pasta dele: assim **vários agentes no mesmo servidor compartilham a mesma
versão**, e a atualização acontece num lugar só. Anote a origem e o critério num
`ORIGEM.txt` ao lado, para a próxima pessoa saber por que aquelas e não outras.

**As credenciais, e sem elas as skills instalam mas não servem para nada:** uma
**conta Google Ads** com acesso, um **developer token** aprovado (no painel de API
do Google Ads) e o **OAuth** configurado (client id, client secret e refresh
token). Conseguir o developer token não é imediato: o Google avalia o pedido, e o
token nasce com acesso de teste.

**Como testar:** peça um diagnóstico de conta. Se ele responde com número real da
sua conta, funcionou. Se responde explicando a API, faltou credencial.

## 5.4 MCP da Meta (tráfego pago)

**Para quem serve:** quem anuncia no Facebook e no Instagram e quer o agente
lendo campanha, medindo e mexendo em anúncio.

Aqui não se instala nada na máquina: é um **connector da sua conta claude.ai**,
autorizado no navegador.

**A parte honesta, medida em 05/09/2026 na instalação de referência:**

- O connector **Meta Ads, o oficial, funciona.** Devolveu a lista de contas com
  nome, moeda, status e orçamento mínimo. **É o que você deve usar.**
- Um MCP caseiro, apontando direto para a Graph API com credencial de aplicativo,
  respondeu **`Invalid appsecret_proof` em toda chamada** (erro 100 da Graph
  API). **Não monte sua operação sobre um MCP caseiro sem antes fazer uma leitura
  simples e olhar o retorno.**

**A armadilha que custa caro, e que a API não avisa.** Um **token de system user
alcança menos contas que o login do dono**. Na medição de referência: **23 contas
pelo token, contra 63 pelo login**. Quem varre a frota pelo token acha que
verificou tudo e deixa quarenta contas de fora, **sem nenhum erro na tela**. Se o
número de contas que voltou parecer baixo, ele provavelmente está.

**Como testar:** peça a lista de contas de anúncio e compare o total com o que
você vê no Gerenciador de Negócios. Bateu, está tudo à vista. Não bateu, você
está olhando por uma fresta.

**Se o agente cria anúncio por API**, duas regras que já custaram retrabalho: o
Instagram vive no **creative** (sem `instagram_user_id` o anúncio nasce só no
Facebook, e a API aceita sem reclamar), e o pixel vive no **anúncio**, em
`tracking_specs`. E um `{"id": "..."}` de sucesso não prova nada: **releia o
anúncio pela API** antes de dizer que ficou pronto.

---

# Parte 6, quando dá errado

| Sintoma | Causa mais provável | Conserto |
|---|---|---|
| Bot mudo | falta `--channels` no `ExecStart` | confira a linha e reinicie |
| Bot mudo, serviço `active` | duas instâncias, erro 409 | `pgrep -af "claude .*--channels" \| wc -l` tem que dar 1 |
| Bot mudo depois de meses | chat id saiu do `allowFrom`, ou token revogado | confira `access.json` e `.env` |
| Bot mudo depois de reboot | cache de MCP travado | apague `~/.claude/mcp-needs-auth-cache.json` e reinicie |
| "Ele esqueceu de tudo" | falta `--continue`, ou sessão avulsa na pasta | veja qual `.jsonl` está crescendo |
| Ele responde como outro | `WorkingDirectory` errado | aponte para a pasta do agente |
| "Unknown skill" | plugin instalado no meio da sessão | feche e reabra o Claude Code |
| Serviço reinicia em laço | falta `Environment=HOME` | veja os quatro suspeitos abaixo |
| Serviço para pedindo login | Claude Code não logado para o usuário do serviço | `sudo -u <nome> -i`, faça o login |
| Mensagens sumiram | restart no meio de conversa | Passo 11.3, o processo não drena o que está em voo |
| Agente caiu sem motivo | disco cheio pelo `inbox` | Passo 11.5 |
| Tarefa agendada não entrega | execução agendada não tem canal | entregue pelo `curl` (Parte 3) |
| Tarefa parou sozinha, sem erro | você criou uma repetitiva | troque pela corrente de avulsos |
| Chat id não está em `approved/` | diretório transitório, pode estar vazio | leia o `allowFrom` do `access.json` |
| Áudio não transcreve (Groq) | falta `;filename=audio.ogg` ou `User-Agent` | veja 5.1 |
| Google conectado e ele não vê | a sessão não foi reiniciada | reinicie o serviço (com o cuidado do 11.3) |

**Serviço reiniciando em laço, os quatro suspeitos na ordem:**

1. Falta `Environment=HOME=/home/<nome>`.
2. Falta o embrulho `/usr/bin/script` (o Claude Code precisa de TTY).
3. O binário `claude` não está no `PATH` declarado: confira com
   `sudo -u <nome> which claude`.
4. O `WorkingDirectory` não existe, ou o usuário não tem permissão nele.

O `journalctl -u <nome>.service -n 50 --no-pager` diz qual dos quatro é.

**Nada disso resolveu?** Rode `/agente:doctor`. Ele gera um
`diagnostico-AAAA-MM-DD.md` na pasta do agente, **sem nenhum dado pessoal**, que
você pode abrir, conferir e mandar para quem te entregou o plugin.

---

# Parte 7, o que este repositório não resolve

Dito agora, para você não descobrir travado no meio.

**Depende de conta sua, e nada aqui substitui:**

- **Assinatura Claude Pro ou Max.** O agente não roda sem login, e no Modo
  Servidor o login precisa estar feito **para o usuário dedicado** (Passo 8).
- **Os connectors do Google e da Meta**, que dependem do que a **sua** conta
  claude.ai tem habilitado. Não aparecendo no `/mcp`, não é defeito do plugin: é
  questão da conta.
- **O developer token do Google Ads**, que passa por aprovação do Google e
  demora.
- **O servidor**, que é infra sua, com custo seu, e precisa de alguém que saiba
  reiniciá-lo quando o provedor der problema.

**Não vem no repositório, e é assim de propósito:** nenhuma credencial, nenhum
token, nenhum `.env` preenchido. Todos os campos deste manual são placeholders.

**Não é fornecido aqui, e você monta se precisar:** as skills de negócio (a
instalação de referência tem quinze skills próprias, de tráfego a financeiro, que
são dela e não deste plugin), os subagentes especializados e qualquer verificador
automático da sua operação. O que este repositório entrega é o **núcleo**: a
pasta, a identidade, a memória com a regra que a mantém enxuta, o canal do
Telegram e o serviço que segura tudo de pé.

**Limites que não têm conserto, só aceitação:**

- **Reiniciar perde o que está em voo.** Não há fila, não há reentrega. É o
  Passo 11.3, e é o limite mais caro desta lista.
- **Nunca duas instâncias com o mesmo bot** (erro 409).
- **O histórico bruto da conversa é apagado pelo sistema** com o tempo. É
  exatamente por isso que o diário existe.
- No Modo Pessoal, computador desligado é agente dormindo, e mensagem enviada
  nesse período se perde. É só reenviar.

---

# Parte 8, como saber que ficou igual

"Instalei" e "funciona" são coisas diferentes. Esta é a checagem que você faz
sozinho, uma semana depois, para saber se o que você montou é de verdade um
agente que trabalha. Cada item tem um teste, e o teste é a resposta.

**Ele está no ar, e volta sozinho.**

- [ ] `systemctl is-active <nome>.service` responde `active`.
- [ ] `systemctl is-enabled <nome>.service` responde `enabled`.
- [ ] Depois de um `sudo reboot`, ele volta sozinho e responde no Telegram sem
      você fazer nada.
- [ ] `pgrep -af "claude .*--channels" | wc -l` responde `1`.

**Ele lembra.**

- [ ] Você conta um fato hoje, reinicia o serviço, e amanhã ele ainda sabe. Se
      esquece a cada reinício, falta `--continue`.
- [ ] O `.jsonl` da sessão em `~/.claude/projects/<pasta-com-traços>/` cresce
      conforme vocês conversam.
- [ ] Ele volta de uma compactação avisando, e sem perder o assunto.

**Ele fala do jeito certo.**

- [ ] Responde no Telegram com a personalidade que você escolheu, não genérico.
- [ ] Manda texto limpo, sem asterisco e sem tabela, porque o Telegram não
      renderiza markdown.
- [ ] Avisa antes de uma tarefa longa e volta com uma mensagem **nova** ao
      terminar, em vez de editar a antiga.

**A memória está disciplinada, não só cheia.**

- [ ] `wc -l working-memory.md` continua abaixo de ~100 linhas depois de
      semanas de uso.
- [ ] `memoria/MEMORY.md` continua sendo índice, abaixo de ~40 linhas.
- [ ] `ls diario/` tem um arquivo por dia de uso, e é lá que estão os episódios.
- [ ] Um fato que você contou uma vez está em **um** lugar só, não em três.
- [ ] Ele te pede autorização para a manutenção quando passa de três dias.

**Ele não inventa.**

- [ ] Quando não sabe, diz que vai checar, e checa.
- [ ] Quando não conseguiu conferir, diz que não conferiu, em vez de afirmar.
- [ ] Pedido algo de uma ferramenta que ele não tem, ele oferece conectar em vez
      de chutar uma resposta.

**A operação não perde o que já foi corrigido.**

- [ ] Existe um verificador que roda sozinho e avisa quando reprova (Parte 4.2).
- [ ] Toda correção que já voltou uma vez virou uma linha nele.
- [ ] O disco não está enchendo sem ninguém ver (Passo 11.5).

**Se todos os itens passam, você tem um agente que trabalha.** Se algum falha, o
item aponta a parte do manual que resolve. E o que faz o agente durar não é a
instalação, que é de um dia: é a Parte 3 e a Parte 4, que são de todo dia.
