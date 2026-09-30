#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aviso NÃO bloqueante para delegar trabalho mecânico.

Hook PreToolUse, matcher Bash. Conta quantos comandos Bash o agente principal
rodou "na mão" desde a última delegação (subagente ou executor_barato.sh) e,
ao chegar em 15 (depois a cada 10), injeta um lembrete de delegar. Subagente
nunca recebe o aviso. A pasta vigiada vem de AGENTE_HOME.

A documentação oficial do Claude Code informa
que chamadas de subagente trazem ``agent_id`` e ``agent_type``; como defesa
para versões antigas, um transcript dentro de ``/subagents/`` também é tratado
como subagente.  Toda falha é fail-open: saída vazia e código 0.
"""

import datetime
import json
import os
import stat
import sys


LIMITE_BYTES = 2 * 1024 * 1024
LIMIAR = 15
INTERVALO = 10
BASE_AGENTE = os.path.abspath(os.environ.get("AGENTE_HOME") or os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.abspath(__file__)))
BASES_AUTORIZADAS = (BASE_AGENTE,)
NOME_LOG = ".aviso_delegar.jsonl"
AVISO = (
    "AVISO DE DELEGAR: {contagem} comandos feitos na mão desde o último "
    "subagente/executor barato. Regra: trabalho mecânico vai para o executor "
    "barato (executor_barato.sh) ou para um subagente em segundo plano; na mão "
    "só o trivial de um comando e o que é indelegável (decidir, falar com o dono)."
)


def pasta_da_casa(cwd):
    """Retorna somente uma das três casas autorizadas, a partir do cwd."""
    if not isinstance(cwd, str):
        return None
    cwd_normalizado = os.path.normpath(cwd)
    for base in BASES_AUTORIZADAS:
        if cwd_normalizado == base or cwd_normalizado.startswith(base + os.sep):
            return base
    return None


def eh_subagente(evento):
    """agent_id/agent_type são o sinal oficial; o caminho é só fallback."""
    if evento.get("agent_id") or evento.get("agent_type"):
        return True
    caminho = evento.get("transcript_path")
    if isinstance(caminho, str):
        partes = caminho.replace("\\", "/").split("/")
        return "subagents" in partes
    return False


def ultimos_bytes(caminho):
    tamanho = os.path.getsize(caminho)
    with open(caminho, "rb") as arquivo:
        if tamanho > LIMITE_BYTES:
            arquivo.seek(tamanho - LIMITE_BYTES)
            arquivo.readline()  # descarta a linha JSON possivelmente cortada
        return arquivo.read().decode("utf-8", errors="replace")


def usos_de_ferramenta(registro):
    mensagem = registro.get("message")
    if not isinstance(mensagem, dict):
        return []
    conteudo = mensagem.get("content")
    if not isinstance(conteudo, list):
        return []
    return [item for item in conteudo if isinstance(item, dict) and item.get("type") == "tool_use"]


def comando_do_bash(uso):
    entrada = uso.get("input")
    if not isinstance(entrada, dict):
        return ""
    comando = entrada.get("command", "")
    return comando if isinstance(comando, str) else ""


def contar_desde_delegacao(transcript_path):
    """Conta Bash após a última delegação, usando o JSONL real do transcript."""
    contagem = 0
    for linha in ultimos_bytes(transcript_path).splitlines():
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError:
            continue
        for uso in usos_de_ferramenta(registro):
            nome = uso.get("name")
            if nome in ("Agent", "Task"):
                contagem = 0
            elif nome == "Bash":
                if "executor_barato.sh" in comando_do_bash(uso):
                    contagem = 0
                else:
                    contagem += 1
    return contagem


def deve_avisar(contagem):
    return contagem >= LIMIAR and (contagem - LIMIAR) % INTERVALO == 0


def registrar_aviso(base, sessao, contagem):
    """Tenta anexar o log sem jamais seguir link simbólico.

    O diretório e o nome são constantes, nunca vêm do evento. O descritor do
    diretório evita troca de caminho durante a abertura; O_NOFOLLOW recusa um
    link no log e st_nlink == 1 também recusa hard link. Falhar aqui é normal:
    o aviso ao agente é independente do registro de medição.
    """
    if base not in BASES_AUTORIZADAS:
        return False
    entrada = {
        "data_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sessao": sessao if isinstance(sessao, str) else "",
        "contagem": contagem,
    }
    dados = (json.dumps(entrada, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    diretorio_fd = None
    log_fd = None
    try:
        diretorio_fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if not stat.S_ISDIR(os.fstat(diretorio_fd).st_mode):
            return False
        log_fd = os.open(
            NOME_LOG,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
            dir_fd=diretorio_fd,
        )
        metadados = os.fstat(log_fd)
        if not stat.S_ISREG(metadados.st_mode) or metadados.st_nlink != 1:
            return False
        inicio = 0
        while inicio < len(dados):
            escritos = os.write(log_fd, dados[inicio:])
            if escritos <= 0:
                return False
            inicio += escritos
        return True
    except Exception:
        return False
    finally:
        if log_fd is not None:
            try:
                os.close(log_fd)
            except OSError:
                pass
        if diretorio_fd is not None:
            try:
                os.close(diretorio_fd)
            except OSError:
                pass


def contagem_no_instante(transcript, evento):
    """Inclui o Bash atual, ausente do transcript durante PreToolUse.

    O hook só é configurado para Bash. Portanto, 14 Bash já registrados mais
    este Bash atual totalizam 15 e avisam no 15º, não no 16º. Se o próprio
    Bash atual chama executor_barato.sh, ele é a delegação e zera a sequência.
    """
    entrada_atual = evento.get("tool_input")
    comando_atual = ""
    if isinstance(entrada_atual, dict):
        candidato = entrada_atual.get("command", "")
        comando_atual = candidato if isinstance(candidato, str) else ""
    if "executor_barato.sh" in comando_atual:
        return 0
    return contar_desde_delegacao(transcript) + 1


def emitir_aviso(contagem):
    saida = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": AVISO.format(contagem=contagem),
        }
    }
    print(json.dumps(saida, ensure_ascii=False, separators=(",", ":")))


def main():
    try:
        evento = json.load(sys.stdin)
        if not isinstance(evento, dict):
            return
        if evento.get("tool_name") != "Bash":
            return
        base = pasta_da_casa(evento.get("cwd"))
        if not base or eh_subagente(evento):
            return
        transcript = evento.get("transcript_path")
        if not isinstance(transcript, str) or not os.path.isfile(transcript):
            return
        contagem = contagem_no_instante(transcript, evento)
        if deve_avisar(contagem):
            # O log é secundário: qualquer recusa de segurança ainda avisa.
            registrar_aviso(base, evento.get("session_id"), contagem)
            emitir_aviso(contagem)
    except Exception:
        # Fail-open: nunca bloqueia e nunca escreve log de erro fora do log
        # explicitamente autorizado.
        return


if __name__ == "__main__":
    main()
