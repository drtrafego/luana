#!/usr/bin/env python3
"""Portão de memória nova: um tema = um arquivo.

Hook PreToolUse (matcher: Write|Bash). Nega a CRIAÇÃO de um arquivo novo
dentro de `memoria/` a menos que o conteúdo traga, na primeira linha (Write)
ou em qualquer lugar do comando (Bash), o marcador:

    <!-- tema-novo: <motivo em uma frase> -->

Por que existe: a regra "procure antes de criar, atualize o que já existe"
estava escrita no CLAUDE.md e mesmo assim o agente criava arquivo paralelo a
cada pedido. Regra escrita é pedido; o portão faz a pergunta na hora certa.

Configuração: a pasta do agente vem da variável AGENTE_HOME (padrão: CLAUDE_PROJECT_DIR,
que o Claude Code define; depois, a pasta onde este arquivo está). Só arquivos .md dentro de <AGENTE_HOME>/memoria/
são vigiados; editar um arquivo que já existe nunca é bloqueado.

Fail-open: qualquer erro do próprio hook sai 0 em silêncio (um bug aqui não
pode travar o trabalho real). O erro vai para .portao_memoria_nova_erros.log.

Cobertura de Bash (conservadora de propósito; na dúvida de parse, NÃO
bloqueia): redirecionamento (>, >>, >|), tee, touch, cp/mv/install (inclusive
-t DIR), ln, e um `cd`/`pushd` no INÍCIO do comando. Symlink novo dentro de
memoria/ conta como arquivo novo (o critério é o NOME, não o alvo do link).

O que fica DESCOBERTO, dito aqui para ninguém confiar além do que cobre:
caminho montado por variável de shell, escrita por `python -c`/`dd`/`rsync`/
API, destino que é pasta em vez de arquivo, `cd` no meio do comando ou em
subshell, e vários pares origem/destino de cp/mv na mesma linha. É uma rede
contra o descuido, não contra quem quer contornar.
"""

import json
import os
import re
import sys
from pathlib import Path


ROOTS = (Path(os.environ.get("AGENTE_HOME") or os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.abspath(__file__))).resolve(),)
MOTIVO = (
    "Memória nova: UM tema = UM arquivo. Procure o arquivo existente "
    "(ls memoria/; grep -ril <tema> memoria/) e atualize ele. Se for tema "
    "novo de verdade, a primeira linha do conteúdo deve ser "
    "<!-- tema-novo: <motivo> -->."
)
# Write: marcador tem que ser a PRIMEIRA LINHA do conteúdo (fullmatch).
MARCADOR = re.compile(r"^<!-- tema-novo:(.*?)-->\s*$")
# Bash: não existe "primeira linha de conteúdo" isolada (é tudo uma string
# de comando só, pode incluir heredoc), então aceita o marcador em
# QUALQUER LUGAR do comando.
MARCADOR_BASH = re.compile(r"<!--\s*tema-novo:(.*?)-->")

# Padrões de escrita reconhecidos em comando Bash. Cada um captura o
# caminho-alvo (sem aspas) de um arquivo .md. Deliberadamente restrito aos
# operadores mais comuns desta casa (ver docstring: "o que fica descoberto").
_PATH_BARE = r"[^\s'\";|&<>]+\.md"
_PATH_DQ = r'[^"\n]+\.md'
_PATH_SQ = r"[^'\n]+\.md"


def _path_alt() -> str:
    """Alternância de caminho .md: aspas duplas (espaço interno permitido),
    aspas simples (espaço interno permitido), ou token sem aspas (sem
    espaço) — antes o token excluía whitespace mesmo
    dentro de aspas. Gera sempre 3 grupos de captura fixos (dq, sq, bare);
    ``_grupo_path`` devolve o que bateu."""
    return r'(?:"(' + _PATH_DQ + r')"|\'(' + _PATH_SQ + r")'|(" + _PATH_BARE + r"))"


def _grupo_path(m: "re.Match[str]") -> str:
    return m.group(1) or m.group(2) or m.group(3)


RE_REDIRECT = re.compile(r"(?:>>|>\|?)\s*" + _path_alt())
RE_TEE = re.compile(r"\btee\b(?:\s+-a)?\s+" + _path_alt())
RE_TOUCH = re.compile(r"\btouch\b\s+" + _path_alt())
RE_CPMV = re.compile(r"\b(?:cp|mv|install)\b\s+([^\n;&|]+)")
# ln [-s] ORIGEM DESTINO: criar o link JÁ é criar o nome novo em memoria/,
# mesmo que nenhum conteúdo seja escrito no mesmo comando.
# ORIGEM não é capturada (pode ser qualquer coisa); só o último
# argumento (DESTINO) importa aqui, e só quando ele já termina em .md
# explicitamente — `ln -s x.md memoria/` (destino é uma pasta) não é
# reconhecido, mesmo gap de "cp pra pasta" já documentado acima.
RE_LN = re.compile(
    r"\bln\b\s+(?:-\S+\s+)*(?:['\"]?[^\s'\";&|]+['\"]?)\s+" + _path_alt()
)
# `cd <pasta> &&`/`;` NO INÍCIO do comando: caso simples pedido no briefing.
# `pushd` entra na mesma posição de `cd` (mesmo efeito de
# trocar o diretório de trabalho antes do resto do comando rodar).
# re.DOTALL porque o resto do comando pode ser um heredoc multi-linha.
RE_CD_PREFIX = re.compile(
    r"^\s*(?:cd|pushd)\s+(['\"]?)([^\s'\";&|]+)\1\s*(?:&&|;)\s*(.*)$", re.DOTALL
)


def _resolver(caminho: str, cwd: str) -> str:
    """Caminho LÓGICO absoluto: relativo é resolvido contra o `cwd` do
    EVENTO do hook (nunca contra o cwd do processo Python),
    e `..`/`.` colapsam como TEXTO (`os.path.normpath`), sem nunca
    seguir symlink (ao contrário de `Path.resolve()`)."""
    if not os.path.isabs(caminho):
        caminho = os.path.join(cwd or "/", caminho)
    return os.path.normpath(caminho)


def raiz_da_memoria(file_path: object, cwd: str = "") -> Path | None:
    if not isinstance(file_path, str) or not file_path:
        return None
    try:
        candidate = Path(_resolver(file_path, cwd))
    except (OSError, ValueError):
        return None
    for root in ROOTS:
        memory = root / "memoria"
        try:
            candidate.relative_to(memory)
        except ValueError:
            continue
        return root
    return None


def registrar_erro(root: Path | None, error: Exception) -> None:
    # Sem file_path válido não há como deduzir a pasta; a raiz configurada é o fallback
    # operacional para que erro de entrada também permaneça auditável.
    destination = (root or ROOTS[0]) / ".portao_memoria_nova_erros.log"
    try:
        with destination.open("a", encoding="utf-8") as log:
            log.write(f"{type(error).__name__}: {error}\n")
    except OSError:
        pass


def _ja_existia(target: Path) -> bool:
    """um caminho que HOJE é um symlink dentro de
    memoria/ nunca conta como "já existia" pra este hook, mesmo que o alvo
    do link exista de verdade — o critério é o NOME dentro da pasta
    protegida, não o que ele aponta. `is_symlink()` não segue o link (não
    lança em caso de alvo dangling); `exists()` sozinho SEGUE o link, que é
    exatamente o bug fechado aqui."""
    return target.exists() and not target.is_symlink()


def _decidir_write(tool_input: dict, cwd: str) -> str | None:
    """Devolve o JSON de deny (string) ou None (permite/silêncio)."""
    file_path = tool_input.get("file_path")
    root = raiz_da_memoria(file_path, cwd)
    if root is None or not isinstance(file_path, str) or not file_path.endswith(".md"):
        return None
    target = Path(_resolver(file_path, cwd))
    if _ja_existia(target):
        return None
    content = tool_input.get("content", "")
    first_line = content.splitlines()[0] if isinstance(content, str) and content.splitlines() else ""
    marker = MARCADOR.fullmatch(first_line)
    if marker and marker.group(1).strip():
        return None
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": MOTIVO}}, ensure_ascii=False)


def _alvos_cpmv(args_str: str) -> set[str]:
    """Alvo(s) de `cp`/`mv`/`install`. suporta `-t DIR` e
    `--target-directory=DIR` (target-directory ANTES da origem) — o parser
    antigo pegava sempre o ÚLTIMO token como destino, então em
    `cp -t memoria/ x.md` lia `x.md` (nome da ORIGEM, sem pasta) como se
    fosse o destino inteiro. Com `-t`/`--target-directory=` presente, o
    destino de cada origem restante é `DIR/basename(origem)`. Sem `-t`,
    mantém o comportamento antigo (último token = destino). Continua sem
    desambiguar múltiplos pares origem/destino fora do padrão `-t` na
    mesma linha (gap já documentado no módulo)."""
    tokens = [tok.strip("'\"") for tok in args_str.split() if tok.strip("'\"")]
    target_dir = None
    filtrados: list[str] = []
    pular = False
    for i, tok in enumerate(tokens):
        if pular:
            pular = False
            continue
        if tok == "-t":
            if i + 1 < len(tokens):
                target_dir = tokens[i + 1]
                pular = True
            continue
        if tok.startswith("--target-directory="):
            target_dir = tok.split("=", 1)[1]
            continue
        if tok.startswith("-") and tok != "-":
            continue
        filtrados.append(tok)
    if target_dir is not None:
        saida: set[str] = set()
        for origem in filtrados:
            base = origem.rstrip("/").rsplit("/", 1)[-1]
            candidato = target_dir.rstrip("/") + "/" + base
            if candidato.endswith(".md"):
                saida.add(candidato)
        return saida
    if filtrados and filtrados[-1].endswith(".md"):
        return {filtrados[-1]}
    return set()


def _alvos_bash(command: str) -> set[str]:
    """Varre o comando atrás de caminho(s) .md que a linha parece criar.
    Ver docstring do módulo para o que NÃO é coberto de propósito."""
    alvos: set[str] = set()
    for m in RE_REDIRECT.finditer(command):
        alvos.add(_grupo_path(m))
    for m in RE_TEE.finditer(command):
        alvos.add(_grupo_path(m))
    for m in RE_TOUCH.finditer(command):
        alvos.add(_grupo_path(m))
    for m in RE_LN.finditer(command):
        alvos.add(_grupo_path(m))
    for m in RE_CPMV.finditer(command):
        alvos.update(_alvos_cpmv(m.group(1)))
    return alvos


def _cwd_efetivo_e_resto(command: str, cwd: str) -> tuple[str, str]:
    """Acompanha um `cd <pasta> &&`/`;` NO INÍCIO do comando (o caso pedido
    no briefing: `cd memoria && echo > novo.md`). Devolve (cwd_efetivo,
    resto_do_comando) — a busca de alvo roda só no RESTO (depois do cd),
    resolvido contra o novo cwd.

    NÃO tenta resolver: `cd` no meio do comando (`algo && cd x && ...`),
    mais de um `cd` encadeado, `cd` dentro de subshell (`(cd x && ...)`),
    nem `cd -`/`cd` sem argumento. Nesses casos devolve o comando inteiro
    e o cwd do evento como está — fail-open, documentado (não é o caso
    pedido, e tentar cobrir com regex arrisca falso-negativo silencioso
    pior do que simplesmente não reconhecer o padrão)."""
    m = RE_CD_PREFIX.match(command)
    if not m:
        return cwd, command
    destino, resto = m.group(2), m.group(3)
    cwd_efetivo = destino if os.path.isabs(destino) else os.path.normpath(os.path.join(cwd or "/", destino))
    return cwd_efetivo, resto


def _decidir_bash(tool_input: dict, cwd: str) -> str | None:
    """Devolve o JSON de deny (string) ou None (permite/silêncio)."""
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    cwd_efetivo, comando_para_alvos = _cwd_efetivo_e_resto(command, cwd)
    alvos = _alvos_bash(comando_para_alvos)
    if not alvos:
        return None  # não reconheceu nenhum padrão de escrita: fail-open
    # marcador é buscado no comando ORIGINAL inteiro (pode vir antes do cd,
    # ou dentro do heredoc que ficou no "resto" — os dois são um superset
    # do resto, então buscar no original cobre os dois casos).
    marker = MARCADOR_BASH.search(command)
    if marker and marker.group(1).strip():
        return None  # marcador presente em qualquer lugar do comando: ok
    for alvo in alvos:
        root = raiz_da_memoria(alvo, cwd_efetivo)
        if root is None:
            continue  # alvo fora de qualquer memoria/: não é desta trava
        try:
            caminho_abs = Path(_resolver(alvo, cwd_efetivo))
        except (OSError, ValueError):
            continue
        if _ja_existia(caminho_abs):
            continue  # arquivo já existe (e não é symlink novo): não é criação
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": MOTIVO}}, ensure_ascii=False)
    return None


def main() -> int:
    root = None
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return 0
        tool_name = event.get("tool_name")
        tool_input = event.get("tool_input")
        cwd = event.get("cwd") or ""
        if not isinstance(cwd, str):
            cwd = ""
        if not isinstance(tool_input, dict):
            return 0

        if tool_name == "Write":
            saida = _decidir_write(tool_input, cwd)
        elif tool_name == "Bash":
            saida = _decidir_bash(tool_input, cwd)
        else:
            return 0

        if saida is not None:
            print(saida)
    except Exception as error:  # Hook não pode interromper trabalho por falha própria.
        registrar_erro(root, error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
