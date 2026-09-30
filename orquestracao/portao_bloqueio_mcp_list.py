#!/usr/bin/env python3
"""
Portão contra comandos do CLI `claude` que sobem OUTRA sessão e derrubam o
Telegram do agente vivo. Hook PreToolUse, matcher: Bash.

O problema (medido, não suposto): o plugin do Telegram faz long polling
(getUpdates), e a API do Telegram só aceita UM consumidor por bot. Ao subir,
cada cópia do servidor do plugin manda SIGTERM no poller anterior que estiver
registrado. Só que `claude mcp list` e `claude mcp get <nome>` fazem health
check de CADA servidor MCP configurado, o que sobe uma SEGUNDA cópia do
servidor do Telegram; ela mata o poller da sessão viva e sai. Resultado: o bot
fica mudo no segundo exato do comando, sem erro na tela. O mesmo vale para
qualquer comando que abra uma nova sessão do CLI (`claude`, `claude -p`,
`--print`, `--agent`, `-c`/`--continue`, `--resume`).

Este portão NEGA esses comandos. Continuam liberados: `claude --version`,
`claude mcp add` e `claude mcp remove` (só mexem na config, não sobem o check).

Alternativas seguras:
- Consultar MCP configurado: ler ~/.claude.json com python (só lê o arquivo).
- Testar a ficha de um subagente: despachar pelo Agent tool da sessão viva.
- Testar este hook: alimentar o JSON de PreToolUse pelo stdin.

Desenho: casador heurístico sobre os tokens de shell do comando Bash inteiro.
Não é sandbox nem parser completo, mas diferencia "executar o binário claude"
de "mencionar a palavra claude" em grep/cat/echo/mensagem de commit. Analisa
comandos encadeados e pipelines, e entra recursivamente nos wrappers comuns
(`bash -c`, `sh -c`, `env`, `nohup`, `timeout`, `xargs`, `exec`, `command`,
`setsid`, `script -qfec`).

Contrato: sempre sai 0; o bloqueio vem do JSON (permissionDecision "deny").
Fail-open: bug neste script nunca bloqueia um Bash legítimo.

O que NÃO cobre (para ninguém confiar além do que existe):
- Uma pessoa abrindo outro `claude` interativo fora do tool Bash desta sessão:
  hook só dispara para tool call da sessão que o registrou.
- Outros caminhos que subam uma segunda cópia do plugin sem um comando Bash
  detectável (ex.: reiniciar o próprio serviço).
- Ofuscação deliberada (concatenação de string, base64, variável montada em
  duas linhas). O alvo é o padrão que de fato acontece, não sabotagem.
"""
import sys
import os
import re
import json
import shlex
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ERROR_LOG = os.path.join(BASE, ".portao_bloqueio_mcp_list_erros.log")

CLAUDE_BINS = {"claude", "claude.exe"}
SHELLS = {"bash", "sh", "dash", "zsh", "ksh"}
WRAPPERS_SIMPLES = {"nohup", "setsid", "time", "command", "builtin"}
SEPARADORES = {";", "&&", "||", "|", "|&", "&", "(", ")"}

ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
REDIRECT_RE = re.compile(r"^(?:\d*)?(?:>>?|<<?|<>|>&|<&|&>|&>>)$")

MOTIVO_DENY = (
    "BLOQUEADO (portao_bloqueio_mcp_list.py): este comando abriria uma nova "
    "sessão do CLI `claude` ou rodaria `claude mcp list/get`. Isso sobe uma "
    "segunda cópia do servidor do Telegram e mata o poller da sessão viva "
    "(o bot fica mudo). Alternativas seguras: ler ~/.claude.json com python "
    "para ver os MCPs configurados; testar ficha de subagente pelo Agent tool "
    "da sessão viva; testar este hook alimentando o JSON pelo stdin. "
    "`claude --version`, `claude mcp add` e `claude mcp remove` continuam liberados."
)


def log_error(exc):
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(ERROR_LOG, "a") as f:
            f.write(f"{timestamp} {exc!r}\n")
    except Exception:
        pass


def _tokenizar(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _basename(token):
    return os.path.basename(str(token)).lower()


def _eh_separador(token):
    return token in SEPARADORES


def _eh_redirecionamento(token):
    return bool(REDIRECT_RE.match(token))


def _remove_redirecionamentos(tokens):
    limpos = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.isdigit() and i + 1 < len(tokens) and _eh_redirecionamento(tokens[i + 1]):
            i += 3
            continue
        if _eh_redirecionamento(token):
            i += 2
            continue
        limpos.append(token)
        i += 1
    return limpos


def _remove_prefixos_de_comando(tokens):
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if ASSIGNMENT_RE.match(token):
            i += 1
            continue
        if token.isdigit() and i + 1 < len(tokens) and _eh_redirecionamento(tokens[i + 1]):
            i += 3
            continue
        if _eh_redirecionamento(token):
            i += 2
            continue
        break
    return tokens[i:]


def _segmentos(tokens):
    atual = []
    for token in tokens:
        if _eh_separador(token):
            if atual:
                yield atual
                atual = []
            continue
        atual.append(token)
    if atual:
        yield atual


def _claude_perigoso(args):
    args = _remove_redirecionamentos(args)
    if not args:
        return True

    primeiro = args[0].lower()
    if len(args) == 1 and primeiro == "--version":
        return False

    if primeiro == "mcp" and len(args) >= 2:
        acao = args[1].lower()
        if acao in {"add", "remove"}:
            return False
        if acao in {"list", "get"}:
            return True

    # Qualquer outra chamada do binario `claude` pode abrir sessao nova
    # (interativa, headless, continue/resume, prompt direto, etc.).
    return True


def _comandos_shell_c(args):
    comandos = []
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--":
            i += 1
            continue
        if token == "-c":
            if i + 1 < len(args):
                comandos.append(args[i + 1])
            i += 2
            continue
        if token.startswith("-") and not token.startswith("--") and "c" in token[1:]:
            if i + 1 < len(args):
                comandos.append(args[i + 1])
            i += 2
            continue
        i += 1
    return comandos


def _comandos_script_c(args):
    comandos = []
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--":
            break
        if token in {"-c", "--command"}:
            if i + 1 < len(args):
                comandos.append(args[i + 1])
            i += 2
            continue
        if token.startswith("--command="):
            comandos.append(token.split("=", 1)[1])
            i += 1
            continue
        if token.startswith("-") and not token.startswith("--") and "c" in token[1:]:
            if i + 1 < len(args):
                comandos.append(args[i + 1])
            i += 2
            continue
        i += 1
    return comandos


def _env_perigoso(args, depth):
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--":
            i += 1
            break
        if token in {"-S", "--split-string"}:
            if i + 1 < len(args):
                return _comando_perigoso(args[i + 1], depth + 1)
            return False
        if token.startswith("--split-string="):
            return _comando_perigoso(token.split("=", 1)[1], depth + 1)
        if token in {"-u", "--unset"}:
            i += 2
            continue
        if token.startswith("--unset="):
            i += 1
            continue
        if token.startswith("-") and token != "-":
            i += 1
            continue
        if ASSIGNMENT_RE.match(token):
            i += 1
            continue
        break
    return _segmento_perigoso(args[i:], depth + 1)


def _timeout_resto(args):
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--":
            i += 1
            break
        if token in {"-k", "--kill-after", "-s", "--signal"}:
            i += 2
            continue
        if token.startswith("--kill-after=") or token.startswith("--signal="):
            i += 1
            continue
        if token.startswith("-") and token != "-":
            i += 1
            continue
        break
    if i < len(args):
        i += 1  # duracao
    return args[i:]


def _xargs_resto(args):
    i = 0
    opcoes_com_arg = {
        "-a", "--arg-file",
        "-d", "--delimiter",
        "-E", "--eof",
        "-I", "--replace",
        "-L", "--max-lines",
        "-l",
        "-n", "--max-args",
        "-P", "--max-procs",
        "-s", "--max-chars",
    }
    prefixos_com_arg_curto = ("-a", "-d", "-E", "-I", "-L", "-l", "-n", "-P", "-s")
    prefixos_com_arg_longo = (
        "--arg-file=", "--delimiter=", "--eof=", "--replace=",
        "--max-lines=", "--max-args=", "--max-procs=", "--max-chars=",
    )

    while i < len(args):
        token = args[i]
        if token == "--":
            i += 1
            break
        if token in opcoes_com_arg:
            i += 2
            continue
        if token.startswith(prefixos_com_arg_longo):
            i += 1
            continue
        if any(token.startswith(prefixo) and token != prefixo for prefixo in prefixos_com_arg_curto):
            i += 1
            continue
        if token.startswith("-") and token != "-":
            i += 1
            continue
        break
    return args[i:]


def _exec_resto(args):
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--":
            i += 1
            break
        if token == "-a":
            i += 2
            continue
        if token.startswith("-") and token != "-":
            i += 1
            continue
        break
    return args[i:]


def _segmento_perigoso(tokens, depth):
    if depth > 12:
        return False

    tokens = _remove_prefixos_de_comando(tokens)
    if not tokens:
        return False

    exe = _basename(tokens[0])
    args = tokens[1:]

    if exe in CLAUDE_BINS:
        return _claude_perigoso(args)

    if exe in SHELLS:
        return any(_comando_perigoso(cmd, depth + 1) for cmd in _comandos_shell_c(args))

    if exe == "script":
        return any(_comando_perigoso(cmd, depth + 1) for cmd in _comandos_script_c(args))

    if exe == "env":
        return _env_perigoso(args, depth)

    if exe == "timeout":
        return _segmento_perigoso(_timeout_resto(args), depth + 1)

    if exe == "xargs":
        resto = _xargs_resto(args)
        return bool(resto) and _segmento_perigoso(resto, depth + 1)

    if exe == "exec":
        return _segmento_perigoso(_exec_resto(args), depth + 1)

    if exe in WRAPPERS_SIMPLES:
        return _segmento_perigoso(args, depth + 1)

    return False


def _comando_perigoso(command, depth=0):
    if depth > 12:
        return False
    try:
        tokens = _tokenizar(command)
    except Exception:
        return False
    return any(_segmento_perigoso(segmento, depth + 1) for segmento in _segmentos(tokens))


def deve_bloquear(command):
    return _comando_perigoso(command)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        log_error(exc)
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)  # matcher ja deveria filtrar isso, defesa extra

    tool_input = data.get("tool_input", {}) or {}
    command = str(tool_input.get("command", "") or "")
    if not command.strip():
        sys.exit(0)

    if not deve_bloquear(command):
        sys.exit(0)  # sem o padrao: silencio, sem ruido

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": MOTIVO_DENY,
        }
    }
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_error(exc)
        sys.exit(0)
