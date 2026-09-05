#!/usr/bin/env bash
# instalar.sh - cria a pasta de um agente a partir dos templates deste plugin.
#
# O que ele faz:  pergunta nome, personalidade e pasta, valida, escreve os
#                 arquivos de identidade e memoria, e (se voce disser que e
#                 servidor) GERA o arquivo <nome>.service para voce conferir.
# O que ele NAO faz: nao escreve em /etc, nao roda systemctl, nao instala
#                 pacote e nao toca em credencial. Essas partes ficam na sua
#                 mao, de proposito: veja a Parte 2 do README.
#
# Uso:  bash instalar.sh

set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TPL="$AQUI/templates"

vermelho() { printf '\033[91m%s\033[0m\n' "$1"; }
verde()    { printf '\033[92m%s\033[0m\n' "$1"; }
amarelo()  { printf '\033[93m%s\033[0m\n' "$1"; }
titulo()   { printf '\n\033[1m%s\033[0m\n' "$1"; }

abortar() { vermelho "ERRO: $1"; exit 1; }

# ---------------------------------------------------------------- pre-checagem
[ -d "$TPL" ] || abortar "nao achei a pasta templates/ ao lado deste script."
for t in CLAUDE.md.tmpl working-memory.md.tmpl TROUBLESHOOTING.md.tmpl; do
  [ -f "$TPL/$t" ] || abortar "falta o template $t em $TPL"
done
command -v python3 >/dev/null 2>&1 || abortar "preciso do python3 para preencher os templates."

titulo "Instalador do agente"
cat <<'TXT'
Vou criar a pasta do seu agente e escrever os arquivos dele.
Nada e instalado no sistema, e nenhuma credencial e pedida aqui.
Ctrl+C cancela a qualquer momento.
TXT

# ------------------------------------------------------------------- perguntas
titulo "1. O nome"
read -r -p "Nome de exibicao (como ele se apresenta, ex.: Maria): " NOME_EXIB
[ -n "${NOME_EXIB:-}" ] || abortar "o nome de exibicao nao pode ficar vazio."

SUGESTAO="$(printf '%s' "$NOME_EXIB" \
  | iconv -f UTF-8 -t ASCII//TRANSLIT 2>/dev/null || printf '%s' "$NOME_EXIB")"
SUGESTAO="$(printf '%s' "$SUGESTAO" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')"

read -r -p "Nome tecnico, para pasta e servico [${SUGESTAO}]: " NOME_TEC
NOME_TEC="${NOME_TEC:-$SUGESTAO}"

echo "$NOME_TEC" | grep -qE '^[a-z][a-z0-9_-]{1,30}$' \
  || abortar "nome tecnico invalido: so letra minuscula, numero, hifen e sublinhado, comecando por letra."
case "$NOME_TEC" in
  claude|telegram|systemd|network|root)
    abortar "'$NOME_TEC' e um nome reservado, escolha outro." ;;
esac
if systemctl list-unit-files 2>/dev/null | grep -q "^${NOME_TEC}.service"; then
  abortar "ja existe um servico chamado ${NOME_TEC}.service. Escolha outro nome."
fi

titulo "2. Quem ele e"
read -r -p "Como ele deve chamar voce (seu nome ou apelido): " DONO
[ -n "${DONO:-}" ] || abortar "o nome do dono nao pode ficar vazio."
echo "Descreva a personalidade em uma ou duas frases (tom, jeito, o que ele curte)."
read -r -p "> " PERSONALIDADE
[ -n "${PERSONALIDADE:-}" ] || PERSONALIDADE="Direto, prestativo e objetivo. Fala pouco e resolve."

titulo "3. Onde ele mora"
PADRAO_PASTA="$HOME/agente-$NOME_TEC"
read -r -p "Pasta do agente [${PADRAO_PASTA}]: " PASTA
PASTA="${PASTA:-$PADRAO_PASTA}"
case "$PASTA" in /*) ;; *) abortar "use um caminho absoluto, comecando com /." ;; esac

if [ "$PASTA" = "$AQUI" ] || [ "${PASTA#"$AQUI"/}" != "$PASTA" ]; then
  abortar "a pasta do agente nao pode ficar dentro da pasta do plugin. Escolha outro lugar."
fi
if [ -e "$PASTA/CLAUDE.md" ]; then
  amarelo "Ja existe um CLAUDE.md em $PASTA."
  read -r -p "Sobrescrever os arquivos do agente? (digite SIM para confirmar): " OK
  [ "$OK" = "SIM" ] || abortar "cancelado por voce."
fi

titulo "4. Servidor?"
echo "Se este agente vai rodar 24 horas com systemd, eu gero o arquivo do servico"
echo "para voce conferir (nao instalo nada)."
read -r -p "Gerar o <nome>.service? (s/N): " QUER_SERVICE

# ------------------------------------------------------------------- escreve
DATA_HOJE="$(date +%Y-%m-%d)"
mkdir -p "$PASTA/memoria" "$PASTA/diario"

preencher() {  # preencher <template> <destino>
  TPL_IN="$1" DEST="$2" P_NOME="$NOME_EXIB" P_DONO="$DONO" \
  P_PERS="$PERSONALIDADE" P_DATA="$DATA_HOJE" python3 - <<'PY'
import os
src, dst = os.environ["TPL_IN"], os.environ["DEST"]
txt = open(src, encoding="utf-8").read()
for chave, valor in (("{{NOME}}", os.environ["P_NOME"]),
                     ("{{DONO}}", os.environ["P_DONO"]),
                     ("{{PERSONALIDADE}}", os.environ["P_PERS"]),
                     ("{{DATA}}", os.environ["P_DATA"])):
    txt = txt.replace(chave, valor)
open(dst, "w", encoding="utf-8").write(txt)
PY
}

preencher "$TPL/CLAUDE.md.tmpl"          "$PASTA/CLAUDE.md"
preencher "$TPL/working-memory.md.tmpl"  "$PASTA/working-memory.md"
preencher "$TPL/TROUBLESHOOTING.md.tmpl" "$PASTA/TROUBLESHOOTING.md"

if [ ! -f "$PASTA/memoria/MEMORY.md" ]; then
  cat > "$PASTA/memoria/MEMORY.md" <<EOF
# Livro de memoria - $NOME_EXIB

Sumario: uma linha por assunto, apontando pro arquivo da secao.
As secoes vivem nesta mesma pasta (familia.md, trabalho.md, projetos.md...).
Mantenha isto como INDICE: o conteudo mora nas secoes, nunca aqui.

<!-- exemplo: - Familia do $DONO -> familia.md -->
EOF
fi

cat > "$PASTA/.gitignore" <<'EOF'
# credenciais e estado local do agente
.env*
audio.json
*credentials*.json
diagnostico-*.md
EOF

chmod 700 "$PASTA" 2>/dev/null || true

verde "Pasta do agente criada em $PASTA"
printf '  %s\n' "CLAUDE.md" "working-memory.md" "TROUBLESHOOTING.md" \
                "memoria/MEMORY.md" "diario/ (vazia por enquanto)"

# ------------------------------------------------------------------- service
if [ "${QUER_SERVICE,,}" = "s" ]; then
  CLAUDE_BIN="$(command -v claude || echo /usr/local/bin/claude)"
  SVC="$AQUI/${NOME_TEC}.service"
  cat > "$SVC" <<EOF
[Unit]
Description=Agente ${NOME_EXIB} (Claude Code, canal Telegram)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${NOME_TEC}
WorkingDirectory=${PASTA}
ExecStart=/usr/bin/script -qfec "${CLAUDE_BIN} --continue --channels plugin:telegram@claude-plugins-official --dangerously-skip-permissions" /home/${NOME_TEC}/${NOME_TEC}-tty.log
Restart=always
RestartSec=10
Environment=HOME=/home/${NOME_TEC}
Environment=PATH=/home/${NOME_TEC}/.bun/bin:/home/${NOME_TEC}/.local/bin:/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin

[Install]
WantedBy=multi-user.target
EOF
  verde "Arquivo do servico gerado em $SVC"
  amarelo "EU NAO INSTALEI. Confira o arquivo (principalmente User=, WorkingDirectory= e o caminho do claude) e rode voce:"
  cat <<EOF

  sudo cp "$SVC" /etc/systemd/system/${NOME_TEC}.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now ${NOME_TEC}.service

EOF
  amarelo "Antes disso, faca o Passo 8 do README: usuario dedicado, pasta, permissao e login do Claude Code para esse usuario."
fi

titulo "Proximos passos"
cat <<EOF
1. Instale os plugins no Claude Code, se ainda nao instalou:
     /plugin marketplace add $AQUI
     /plugin install agente@agente
     /plugin install telegram@claude-plugins-official
2. Crie o bot no BotFather e grave o token com /telegram:configure
3. Acorde o agente e pareie (Passo 6 do README):
     cd "$PASTA" && claude --channels plugin:telegram@claude-plugins-official
4. Tranque o acesso: dmPolicy "allowlist" no access.json
5. Faca as tres provas do Passo 7

O manual completo esta no README.md deste repositorio.
EOF
