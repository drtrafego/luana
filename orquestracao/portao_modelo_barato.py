#!/usr/bin/env python3
"""
Portão de modelo barato, hook PreToolUse (matcher: Agent|Task).

O que faz, antes de TODO despacho de subagente:
1. `model` tem que vir preenchido, com um modelo de verdade. Sem `model` (ou
   com `inherit`) o despacho é NEGADO: o portão não escolhe o modelo por você,
   só obriga a escolha a ser consciente, a cada chamada.
2. `prompt` vazio é NEGADO.
3. Tarefa com cara de MECÂNICA (build, deploy, git pull/push/commit, restart,
   ffprobe, md5sum, contar, varredura...) NÃO pode ir para um modelo caro sem
   justificativa escrita.
4. `fork` é sempre liberado: fork herda o modelo do pai, não há escolha a cobrar.

Por que é um hook e não uma linha no CLAUDE.md: medido numa instalação real,
com o lembrete apenas escrito (e depois com um hook que só lembrava), 95% dos
despachos seguiam saindo sem modelo explícito. Lembrete não funciona; quem
está com a cabeça na tarefa lê por cima. O que funcionou foi NEGAR, com o
motivo dizendo o que fazer, para o modelo relançar a chamada corrigida.

A régua (o que é "mecânico" e o que não é):
- MECÂNICO / baixo julgamento: varredura de arquivo, contagem, grep, rodar um
  verificador e devolver PASS/FAIL cru, conferir se algo existe, checagem de
  formato, patch já especificado palavra por palavra. Vai no modelo barato.
- NÃO é mecânico: decidir, julgar tom de texto, mexer em anúncio/contrato/
  mensagem para cliente, sintetizar achado de outro agente. Fica no modelo
  padrão (ou no forte, se for síntese de alto risco).
- A régua de risco não é "que tipo de arquivo", é "quão preciso é o MEU plano
  e o que acontece se eu errar". Um patch de duas linhas num arquivo que manda
  mensagem para cliente real NÃO é mecânico, por mais que o diff seja pequeno.

Marcadores que liberam (devem aparecer no prompt ou na description):
- `[modelo-caro-justificado: <motivo>]`  tarefa parece mecânica mas exige
  julgamento de verdade (texto público, criativo, privacidade, merge com conflito).
- `[executor-indisponivel: <erro>]`      só no modo executor externo: o executor
  barato (executor_barato.sh) falhou, então o modelo barato do Claude pode fazer.

Configuração por variável de ambiente (todas opcionais):
- AGENTE_HOME              pasta do agente (padrão: CLAUDE_PROJECT_DIR, senão a pasta deste arquivo). Só
                           define onde o log de erro e o caminho do executor moram.
- PORTAO_MODELO_BARATO     nome do modelo barato (padrão: haiku).
- PORTAO_EXECUTOR_EXTERNO  "1" = tarefa mecânica NUNCA vai para subagente do
                           Claude, vai para o executor_barato.sh (outro
                           provedor/plano, para não gastar o mesmo limite).
                           "0" (padrão) = tarefa mecânica passa se o modelo for
                           o barato.

Contrato: a decisão de bloquear vai no JSON (permissionDecision "deny") e o
processo SEMPRE sai 0. Qualquer falha do próprio script (stdin malformado,
exceção) é FAIL-OPEN: sai 0 em silêncio, o que equivale a "sem decisão, segue o
fluxo normal". Um bug aqui não pode travar um despacho real.
"""
import datetime
import json
import os
import re
import sys

BASE = os.path.abspath(os.environ.get("AGENTE_HOME") or os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.abspath(__file__)))
ERROR_LOG = os.path.join(BASE, ".portao_modelo_erros.log")
MODELO_BARATO = (os.environ.get("PORTAO_MODELO_BARATO") or "haiku").strip().lower()
EXECUTOR_EXTERNO = os.environ.get("PORTAO_EXECUTOR_EXTERNO", "0").strip() == "1"

MOTIVO_SEM_MODEL = (
    "Despacho de Agent/Task sem `model` explícito, bloqueado pelo portão de "
    f"modelo barato. Passe `model`: {MODELO_BARATO} para tarefa mecânica "
    "(varredura, contagem, grep, rodar verificador, conferir se existe, patch "
    "já especificado palavra por palavra), sonnet para julgamento e código, "
    "opus só para síntese de alto risco. Relance a chamada com `model` "
    "preenchido: o portão não decide por você, só exige a escolha explícita."
)
MOTIVO_PROMPT_VAZIO = (
    "Despacho de Agent/Task com `prompt` vazio, bloqueado pelo portão de "
    "modelo barato. Preencha o prompt com a tarefa e relance."
)

# Padrões de tarefa mecânica (fronteira de palavra, sem diferença de caixa).
PADROES_MECANICOS = [
    r"\bdeploy\b",
    r"\bbuild\b",
    r"npm run build",
    r"\bgit\s+(pull|push|fetch|commit)\b",
    r"\breinici\w*\b",
    r"\brestart\b",
    r"\bapag\w*\b.{0,40}\btarefas?\b",
    r"\bdelet\w*\b.{0,40}\btarefas?\b",
    r"\bffprobe\b",
    r"\bsilencedetect\b",
    r"\bmd5sum\b",
    r"\bcontar\b",
    r"\bcontagem\b",
    r"\bvarredura\b",
]
REGEX_MECANICOS = [re.compile(p, re.IGNORECASE) for p in PADROES_MECANICOS]


def negar(motivo):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        }
    }, ensure_ascii=False))


def motivo_mecanico(padrao):
    if EXECUTOR_EXTERNO:
        return (
            f"Tarefa mecânica (padrão: {padrao}): neste setup ela vai para o "
            f"executor barato, não para subagente do Claude. Rode: bash "
            f"{BASE}/executor_barato.sh \"<tarefa>\" <pasta>. Se o executor "
            f"estiver indisponível, relance em `{MODELO_BARATO}` com "
            "[executor-indisponivel: <erro>] no começo do prompt. Se a tarefa "
            "exige julgamento de verdade, use [modelo-caro-justificado: <motivo>]."
        )
    return (
        f"Tarefa mecânica (padrão: {padrao}) em modelo caro, bloqueada pelo "
        f"portão. Relance com model `{MODELO_BARATO}`. Se a tarefa exige "
        "julgamento de verdade (texto público, criativo, privacidade, merge "
        "com conflito), escreva [modelo-caro-justificado: <motivo>] no começo "
        "do prompt."
    )


def log_error(exc):
    try:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(ERROR_LOG, "a") as f:
            f.write(f"{ts} {exc!r}\n")
    except Exception:
        pass


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        log_error(exc)
        return
    if data.get("tool_name") not in ("Agent", "Task"):
        return
    tool_input = data.get("tool_input", {}) or {}

    tipo = str(tool_input.get("subagent_type", "") or "").strip().lower()
    if tipo == "fork":
        return

    prompt = tool_input.get("prompt")
    if not (isinstance(prompt, str) and prompt.strip()):
        negar(MOTIVO_PROMPT_VAZIO)
        return

    model = tool_input.get("model")
    if not (isinstance(model, str) and model.strip()) or model.strip().lower() == "inherit":
        negar(MOTIVO_SEM_MODEL)
        return
    model = model.strip().lower()

    description = tool_input.get("description", "") or ""
    if not isinstance(description, str):
        description = ""
    texto = (description + " " + prompt).lower()

    if "[modelo-caro-justificado:" in texto:
        return

    for regex in REGEX_MECANICOS:
        if regex.search(texto):
            if EXECUTOR_EXTERNO:
                if model == MODELO_BARATO and "[executor-indisponivel:" in texto:
                    return
            elif model == MODELO_BARATO:
                return
            negar(motivo_mecanico(regex.pattern))
            return


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_error(exc)
    sys.exit(0)
