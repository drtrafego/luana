#!/usr/bin/env python3
"""
Autoteste dos portões. Cada caso alimenta o hook com o JSON de PreToolUse pelo
stdin (exatamente como o Claude Code faz) e confere a saída.

Regra deste teste: para cada trava existe um caso que TEM que ser barrado e um
que TEM que passar. Teste que só vê aprovar não distingue "está certo" de "eu
parei de olhar".

Uso:  python3 testar_portoes.py        (sai 0 se tudo passou, 1 se algo falhou)
"""
import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
falhas = []


def rodar(script, evento, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    p = subprocess.run(
        [sys.executable, os.path.join(AQUI, script)],
        input=json.dumps(evento), capture_output=True, text=True, env=env, timeout=30,
    )
    return p.returncode, p.stdout.strip()


def decisao(saida):
    if not saida:
        return "silencio"
    return json.loads(saida)["hookSpecificOutput"].get("permissionDecision", "?")


def confere(nome, obtido, esperado):
    ok = obtido == esperado
    print(("ok   " if ok else "FALHA"), nome, "" if ok else f"(esperado {esperado}, veio {obtido})")
    if not ok:
        falhas.append(nome)


def agente(prompt, model=None, desc="", tipo=""):
    ti = {"prompt": prompt, "description": desc}
    if model is not None:
        ti["model"] = model
    if tipo:
        ti["subagent_type"] = tipo
    return {"tool_name": "Agent", "tool_input": ti}


# ---------------- portao_modelo_barato ----------------
M = "portao_modelo_barato.py"
confere("modelo: sem model é negado", decisao(rodar(M, agente("analisar o texto"))[1]), "deny")
confere("modelo: inherit é negado", decisao(rodar(M, agente("analisar o texto", "inherit"))[1]), "deny")
confere("modelo: prompt vazio é negado", decisao(rodar(M, agente("  ", "sonnet"))[1]), "deny")
confere("modelo: julgamento com sonnet passa", decisao(rodar(M, agente("revisar o tom da legenda", "sonnet"))[1]), "silencio")
confere("modelo: fork sem model passa", decisao(rodar(M, agente("qualquer", None, tipo="fork"))[1]), "silencio")
confere("modelo: mecânico em sonnet é negado", decisao(rodar(M, agente("rodar o build e o deploy", "sonnet"))[1]), "deny")
confere("modelo: mecânico em haiku passa", decisao(rodar(M, agente("rodar o build", "haiku"))[1]), "silencio")
confere("modelo: mecânico caro COM justificativa passa",
        decisao(rodar(M, agente("[modelo-caro-justificado: mexe em texto público] fazer o deploy da legenda", "sonnet"))[1]), "silencio")
ext = {"PORTAO_EXECUTOR_EXTERNO": "1"}
confere("modelo(externo): mecânico em haiku sem marcador é negado", decisao(rodar(M, agente("rodar o build", "haiku"), ext)[1]), "deny")
confere("modelo(externo): mecânico em haiku com executor-indisponivel passa",
        decisao(rodar(M, agente("[executor-indisponivel: sem crédito] rodar o build", "haiku"), ext)[1]), "silencio")
confere("modelo: entrada malformada é fail-open", rodar(M, "isto nao e um evento")[0], 0)
p = subprocess.run([sys.executable, os.path.join(AQUI, M)], input="{lixo", capture_output=True, text=True)
confere("modelo: JSON quebrado sai 0 e mudo", (p.returncode, p.stdout.strip()), (0, ""))

# ---------------- portao_busca_memoria ----------------
with tempfile.TemporaryDirectory() as home:
    os.makedirs(os.path.join(home, "memoria"))
    with open(os.path.join(home, "memoria", "clientes.md"), "w", encoding="utf-8") as f:
        f.write("Mariana cuida da padaria, ação combinada.\nToken: valor-falso-de-teste segredo\n")
    B = "portao_busca_memoria.py"
    env = {"AGENTE_HOME": home}
    rc, out = rodar(B, agente("Investigar Mariana e a Token do sistema, acao de ontem", "sonnet"), env)
    out = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
    confere("busca: acha nome próprio", "clientes.md:1" in out, True)
    confere("busca: acha sem acento (acao -> ação)", '["acao"]' in out, True)
    confere("busca: avisa que é dado, não ordem", "DADO registrado na memória" in out, True)
    confere("busca: NÃO vaza a linha com credencial", "valor-falso-de-teste" not in out, True)
    confere("busca: registra o uso (só endereço)", os.path.isfile(os.path.join(home, ".uso_memoria.jsonl")), True)
    with open(os.path.join(home, ".uso_memoria.jsonl"), encoding="utf-8") as f:
        confere("busca: log de uso não guarda o texto", "padaria" not in f.read(), True)
    confere("busca: sem achado fica em silêncio", rodar(B, agente("nada a ver com zebra", "sonnet"), env)[1], "")

# ---------------- portao_memoria_nova ----------------
with tempfile.TemporaryDirectory() as home:
    os.makedirs(os.path.join(home, "memoria"))
    open(os.path.join(home, "memoria", "existe.md"), "w").close()
    N = "portao_memoria_nova.py"
    env = {"AGENTE_HOME": home}

    def escreve(nome, conteudo):
        return {"tool_name": "Write", "cwd": home,
                "tool_input": {"file_path": os.path.join(home, "memoria", nome), "content": conteudo}}

    confere("memória nova: arquivo novo sem marcador é negado", decisao(rodar(N, escreve("novo.md", "oi"), env)[1]), "deny")
    confere("memória nova: com marcador e motivo passa",
            decisao(rodar(N, escreve("novo.md", "<!-- tema-novo: assunto inédito -->\nx"), env)[1]), "silencio")
    confere("memória nova: marcador SEM motivo é negado",
            decisao(rodar(N, escreve("novo.md", "<!-- tema-novo: -->\nx"), env)[1]), "deny")
    confere("memória nova: editar arquivo existente passa", decisao(rodar(N, escreve("existe.md", "oi"), env)[1]), "silencio")
    bash = {"tool_name": "Bash", "cwd": home, "tool_input": {"command": "cd memoria && echo x > outro.md"}}
    confere("memória nova: Bash com cd + redirect é negado", decisao(rodar(N, bash, env)[1]), "deny")
    bash2 = {"tool_name": "Bash", "cwd": home, "tool_input": {"command": "echo x > fora.md"}}
    confere("memória nova: escrever fora de memoria/ passa", decisao(rodar(N, bash2, env)[1]), "silencio")

# ---------------- portao_bloqueio_mcp_list ----------------
Q = "portao_bloqueio_mcp_list.py"
for cmd, esperado in [
    ("claude mcp list", "deny"),
    ("claude mcp get telegram", "deny"),
    ('bash -c "claude -p oi"', "deny"),
    ("timeout 5 claude mcp list", "deny"),
    ("grep claude arquivo.txt", "silencio"),
    ("claude --version", "silencio"),
    ("claude mcp add x", "silencio"),
]:
    confere(f"mcp: {cmd}", decisao(rodar(Q, {"tool_name": "Bash", "tool_input": {"command": cmd}})[1]), esperado)

# ---------------- portao_delegar ----------------
with tempfile.TemporaryDirectory() as home:
    D = "portao_delegar.py"
    env = {"AGENTE_HOME": home}
    transcrito = os.path.join(home, "sessao.jsonl")

    def uso_bash(cmd):
        return json.dumps({"message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}})

    with open(transcrito, "w") as f:
        f.write("\n".join(uso_bash("ls") for _ in range(14)) + "\n")
    ev = {"tool_name": "Bash", "cwd": home, "transcript_path": transcrito, "session_id": "s1", "tool_input": {"command": "ls"}}
    confere("delegar: 15º comando na mão avisa", decisao(rodar(D, ev, env)[1]), "allow")
    ev_ok = dict(ev, tool_input={"command": "bash executor_barato.sh 'x'"})
    confere("delegar: chamar o executor zera e não avisa", decisao(rodar(D, ev_ok, env)[1]), "silencio")
    with open(transcrito, "w") as f:
        f.write("\n".join(uso_bash("ls") for _ in range(5)) + "\n")
    confere("delegar: 6º comando não avisa", decisao(rodar(D, ev, env)[1]), "silencio")
    ev_sub = dict(ev, agent_id="abc")
    with open(transcrito, "w") as f:
        f.write("\n".join(uso_bash("ls") for _ in range(14)) + "\n")
    confere("delegar: subagente nunca recebe o aviso", decisao(rodar(D, ev_sub, env)[1]), "silencio")

print()
if falhas:
    print(f"{len(falhas)} falha(s): {falhas}")
    sys.exit(1)
print("Todos os casos passaram.")
