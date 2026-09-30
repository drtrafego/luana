#!/usr/bin/env bash
# executor_barato.sh - roda UMA tarefa mecânica num executor barato, em segundo
# plano, com fila, conferência de entrega e guarda dos arquivos de memória.
#
# Por que existe: o agente principal (o modelo forte, que conversa e decide) não
# deve gastar o seu limite com trabalho mecânico (build, deploy, contagem,
# varredura, patch já especificado). Este wrapper manda esse trabalho para outro
# executor (outro modelo, outro provedor, outro plano), sem que o agente
# principal precise saber os detalhes de linha de comando.
#
# O executor é QUALQUER CLI que aceite o prompt como último argumento e trabalhe
# na pasta atual. Você o declara por variável de ambiente:
#
#   EXECUTOR_CMD            comando base. Ex.: "codex exec --skip-git-repo-check -s workspace-write"
#                           ou "claude -p --permission-mode acceptEdits" (veja a nota
#                           sobre `claude` no README: NÃO use `claude -p` na mesma máquina
#                           de um agente com Telegram vivo, ele derruba o bot).
#   EXECUTOR_MODEL_FLAG     flag que escolhe o modelo (padrão: -m). Vazio = não passa modelo.
#   EXECUTOR_MODELO_BARATO  modelo do nível "barato" (padrão do nível, obrigatório se usar a flag)
#   EXECUTOR_MODELO_MEDIO   modelo do nível "medio"  (julgamento intermediário)
#   EXECUTOR_MODELO_FORTE   modelo do nível "forte"  (código complexo, síntese de alto risco)
#   AGENTE_HOME             pasta do agente (padrão: CLAUDE_PROJECT_DIR, senão a pasta deste arquivo)
#
# Uso:
#   executor_barato.sh [--nivel barato|medio|forte] [--justificativa "<motivo>"]
#                      [--espera <arquivo>]... [--pode-editar <arquivo>]...
#                      [--paralelo] "<prompt>" [pasta_de_trabalho]
#   executor_barato.sh --teste          # pergunta 19+23 e confere que veio 42
#
# Regras que o script aplica (cada uma vem de um erro real):
#   - NÍVEL: barato por padrão. "forte" exige --justificativa concreta (4+ palavras).
#   - FILA: uma instância por vez (flock). Ocupado = sai com 75, quem chamou espera
#     e tenta de novo. --paralelo permite até 3 ao mesmo tempo (frentes independentes).
#   - ARQUIVOS PROTEGIDOS: working-memory.md, CLAUDE.md, .claude/settings.json e
#     memoria/*.md são fotografados antes e comparados depois. Se o executor mexeu
#     em algum, sai com 79 e AVISA; nunca restaura nem apaga sozinho (restaurar
#     no escuro já destruiu trabalho bom). Libere um arquivo com --pode-editar.
#   - ENTREGA: --espera <arquivo> exige que o arquivo exista e seja mais novo que
#     o início da execução; senão sai com 78. "Rodou sem erro" não é "entregou".
#
# Códigos de saída: 0 ok | 64 uso errado | 75 ocupado (tente de novo) |
#   78 entrega não confere | 79 arquivo protegido alterado | 127 executor ausente |
#   demais = código do próprio executor.
set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AGENTE_HOME="${AGENTE_HOME:-${CLAUDE_PROJECT_DIR:-$SCRIPT_DIR}}"
LOG_DIR="$AGENTE_HOME/.executor_barato"
mkdir -p "$LOG_DIR" 2>/dev/null || LOG_DIR="/tmp"
LOG="$LOG_DIR/execucao-$(date +%Y%m%d-%H%M%S)-$$.log"

NIVEL="barato"
JUSTIFICATIVA=""
TESTE=0
PARALELO=0
ESPERAS=()
PODE_EDITAR=()
PROMPT=""
WORKDIR=""

uso() {
  sed -n '2,45p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
  exit 64
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --nivel)          NIVEL="${2:-}"; shift 2 ;;
    --justificativa)  JUSTIFICATIVA="${2:-}"; shift 2 ;;
    --espera)         ESPERAS+=("${2:-}"); shift 2 ;;
    --pode-editar)    PODE_EDITAR+=("${2:-}"); shift 2 ;;
    --paralelo)       PARALELO=1; shift ;;
    --teste)          TESTE=1; shift ;;
    -h|--help)        uso ;;
    --)               shift; break ;;
    -*)               echo "Opção desconhecida: $1" >&2; uso ;;
    *)
      if [[ -z "$PROMPT" ]]; then PROMPT="$1"
      elif [[ -z "$WORKDIR" ]]; then WORKDIR="$1"
      else echo "Argumento a mais: $1" >&2; uso; fi
      shift ;;
  esac
done

if [[ "$TESTE" -eq 1 ]]; then
  PROMPT="Quanto é 19 mais 23? Responda só com o número, sem fazer mais nada."
fi
[[ -n "$PROMPT" ]] || { echo "Falta o prompt." >&2; uso; }
WORKDIR="${WORKDIR:-$AGENTE_HOME}"
[[ -d "$WORKDIR" ]] || { echo "Pasta de trabalho não existe: $WORKDIR" >&2; exit 64; }
WORKDIR="$(cd -- "$WORKDIR" && pwd -P)"

if [[ -z "${EXECUTOR_CMD:-}" ]]; then
  echo "EXECUTOR_CMD não definido. Defina o comando do executor barato (veja o cabeçalho deste arquivo)." >&2
  exit 127
fi
read -r -a CMD_BASE <<< "$EXECUTOR_CMD"
if ! command -v "${CMD_BASE[0]}" >/dev/null 2>&1; then
  echo "Executor não encontrado no PATH: ${CMD_BASE[0]}" >&2
  exit 127
fi

case "$NIVEL" in
  barato) MODELO="${EXECUTOR_MODELO_BARATO:-}" ;;
  medio)  MODELO="${EXECUTOR_MODELO_MEDIO:-}" ;;
  forte)  MODELO="${EXECUTOR_MODELO_FORTE:-}" ;;
  *) echo "Nível inválido: $NIVEL (use barato, medio ou forte)" >&2; exit 64 ;;
esac

if [[ "$NIVEL" == "forte" ]]; then
  read -r -a PALAVRAS <<< "$JUSTIFICATIVA"
  if [[ "${#JUSTIFICATIVA}" -lt 20 || "${#PALAVRAS[@]}" -lt 4 ]]; then
    echo "Nível forte exige --justificativa concreta (mínimo 4 palavras): por que a tarefa não cabe no barato ou no médio?" >&2
    exit 64
  fi
fi

MODEL_FLAG="${EXECUTOR_MODEL_FLAG--m}"
MODEL_ARGS=()
if [[ -n "$MODEL_FLAG" && -n "$MODELO" ]]; then
  MODEL_ARGS=("$MODEL_FLAG" "$MODELO")
fi

{
  echo "inicio=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "nivel=$NIVEL modelo=${MODELO:-<padrão do executor>}"
  [[ -n "$JUSTIFICATIVA" ]] && echo "justificativa=$JUSTIFICATIVA"
  echo "workdir=$WORKDIR"
} >> "$LOG"

# ---- fila: uma por vez (ou até 3 com --paralelo). Ocupado = 75. ----
if command -v flock >/dev/null 2>&1; then
  CHAVE="$(printf '%s' "$AGENTE_HOME" | md5sum | cut -c1-10)"
  if [[ "$PARALELO" -eq 1 ]]; then
    OK=0
    for SLOT in 1 2 3; do
      exec {LOCK_FD}>"/tmp/executor-barato-$CHAVE-$SLOT.lock"
      if flock -n "$LOCK_FD"; then OK=1; echo "slot=$SLOT" >> "$LOG"; break; fi
      exec {LOCK_FD}>&-
    done
    if [[ "$OK" -ne 1 ]]; then
      echo "Já existem 3 execuções paralelas rodando. Tente de novo em instantes." | tee -a "$LOG" >&2
      exit 75
    fi
  else
    exec {LOCK_FD}>"/tmp/executor-barato-$CHAVE.lock"
    if ! flock -n "$LOCK_FD"; then
      echo "Já existe uma execução rodando. Tente de novo em instantes." | tee -a "$LOG" >&2
      exit 75
    fi
  fi
fi

# ---- arquivos protegidos: fotografia (md5) antes, comparação depois ----
declare -A MD5_ANTES=()
PROTEGIDOS=("$AGENTE_HOME/working-memory.md" "$AGENTE_HOME/CLAUDE.md" "$AGENTE_HOME/.claude/settings.json")
shopt -s nullglob
for f in "$AGENTE_HOME"/memoria/*.md; do PROTEGIDOS+=("$f"); done
shopt -u nullglob

# --pode-editar relativo é lido a partir do AGENTE_HOME; normaliza UMA vez, antes do cd.
PODE_ABS=()
for p in "${PODE_EDITAR[@]+"${PODE_EDITAR[@]}"}"; do
  [[ "$p" = /* ]] && PODE_ABS+=("$(readlink -m -- "$p")") || PODE_ABS+=("$(readlink -m -- "$AGENTE_HOME/$p")")
done

liberado() {
  local alvo p
  alvo="$(readlink -m -- "$1")"
  for p in "${PODE_ABS[@]+"${PODE_ABS[@]}"}"; do
    [[ "$alvo" == "$p" ]] && return 0
  done
  return 1
}

for f in "${PROTEGIDOS[@]}"; do
  liberado "$f" && continue
  if [[ -e "$f" ]]; then MD5_ANTES["$f"]="$(md5sum -- "$f" | cut -d' ' -f1)"; else MD5_ANTES["$f"]="-"; fi
done

MARCA="$(mktemp "/tmp/executor-barato-inicio.XXXXXX")"
trap 'rm -f -- "$MARCA"' EXIT

# ---- roda o executor (o prompt vai como ÚLTIMO argumento, nunca por shell) ----
cd "$WORKDIR" || exit 64
if [[ "$TESTE" -eq 1 ]]; then
  timeout 90s "${CMD_BASE[@]}" "${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"}" "$PROMPT" < /dev/null >> "$LOG" 2>&1
else
  "${CMD_BASE[@]}" "${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"}" "$PROMPT" < /dev/null >> "$LOG" 2>&1
fi
RC=$?
FINAL=$RC

# ---- conferência do que mudou: SÓ AVISA, nunca restaura nem apaga ----
ALTERADOS=()
for f in "${!MD5_ANTES[@]}"; do
  if [[ -e "$f" ]]; then ATUAL="$(md5sum -- "$f" | cut -d' ' -f1)"; else ATUAL="-"; fi
  [[ "$ATUAL" != "${MD5_ANTES[$f]}" ]] && ALTERADOS+=("$f")
done
# arquivo novo em memoria/ também conta
shopt -s nullglob
for f in "$AGENTE_HOME"/memoria/*.md; do
  liberado "$f" && continue
  [[ -z "${MD5_ANTES[$f]+x}" ]] && ALTERADOS+=("$f")
done
shopt -u nullglob

if [[ "${#ALTERADOS[@]}" -gt 0 ]]; then
  echo "ARQUIVO PROTEGIDO ALTERADO (NÃO restaurado, conferir à mão): ${ALTERADOS[*]}" | tee -a "$LOG" >&2
  FINAL=79
else
  for e in "${ESPERAS[@]+"${ESPERAS[@]}"}"; do
    [[ "$e" = /* ]] && alvo="$e" || alvo="$WORKDIR/$e"
    # precisa existir e ser mais novo que a marca criada ANTES da execução
    if [[ ! -e "$alvo" || ! "$alvo" -nt "$MARCA" ]]; then
      echo "ENTREGA NÃO CONFERE: $e não foi criado/alterado." | tee -a "$LOG" >&2
      FINAL=78
      break
    fi
  done
fi

if [[ "$TESTE" -eq 1 && "$FINAL" -eq 0 ]] && ! grep -q "42" "$LOG"; then
  echo "Teste falhou: o executor não respondeu 42." | tee -a "$LOG" >&2
  FINAL=1
fi

echo "exit_code=$RC final_exit_code=$FINAL log=$LOG" >> "$LOG"
tail -n 80 "$LOG"
exit "$FINAL"
