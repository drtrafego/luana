#!/usr/bin/env python3
"""
Leitor SÓ LEITURA do log de uso de memória (.uso_memoria.jsonl), escrito por
portao_busca_memoria.py. Não escreve nada em lugar nenhum. Imprime:
  1. Por (arquivo, linha): quantas vezes foi injetado e a data da última vez (UTC).
  2. Arquivos de memoria/*.md que NUNCA apareceram no log dentro da janela de
     --dias (padrão 30): candidatos a CONFERÊNCIA antes de entrarem numa
     faxina. Não é lista de "apagar": memória pode ser usada sem casar palavra.

Uso:
  python3 uso_memoria.py --pasta /caminho/da/pasta/do/agente
  python3 uso_memoria.py --pasta /caminho/da/pasta/do/agente --dias 14
"""
import argparse
import collections
import datetime
import glob
import json
import os
import sys


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pasta", required=True, help="pasta do agente (a mesma do AGENTE_HOME dos portões)")
    p.add_argument("--dias", type=int, default=30, help="janela em dias pra 'nunca injetado' (default 30)")
    return p.parse_args(argv)


def carregar_registros(caminho_jsonl):
    """Devolve (registros, malformadas, existe). Nunca levanta: linha
    malformada é pulada e contada; arquivo ausente é tratado como 'zero uso
    registrado ainda', não como erro."""
    registros = []
    malformadas = 0
    if not os.path.isfile(caminho_jsonl):
        return registros, malformadas, False
    with open(caminho_jsonl, "r", encoding="utf-8", errors="replace") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                obj = json.loads(linha)
                ts = obj["ts"]
                arquivo = obj["arquivo"]
                num_linha = obj["linha"]
                palavra = obj.get("palavra")
                dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=datetime.timezone.utc
                )
                registros.append((arquivo, num_linha, palavra, dt))
            except Exception:
                malformadas += 1
    return registros, malformadas, True


def main(argv=None):
    args = parse_args(argv)
    pasta = os.path.abspath(args.pasta)
    caminho_jsonl = os.path.join(pasta, ".uso_memoria.jsonl")
    registros, malformadas, existe = carregar_registros(caminho_jsonl)

    agora = datetime.datetime.now(datetime.timezone.utc)
    corte = agora - datetime.timedelta(days=args.dias)

    print(f"Uso de memória: {pasta}")
    print(f"Log: {caminho_jsonl} ({'existe' if existe else 'ainda não existe, zero uso registrado até agora'})")
    if malformadas:
        print(f"AVISO: {malformadas} linha(s) malformada(s) no jsonl, ignoradas (não derrubam a leitura).")
    print(f"Total de injeções registradas (todo o histórico do log): {len(registros)}")
    print()

    if registros:
        por_chave = collections.defaultdict(lambda: {"count": 0, "ultima": None, "palavras": set()})
        for arquivo, num_linha, palavra, dt in registros:
            info = por_chave[(arquivo, num_linha)]
            info["count"] += 1
            if palavra:
                info["palavras"].add(palavra)
            if info["ultima"] is None or dt > info["ultima"]:
                info["ultima"] = dt

        print("POR ARQUIVO:LINHA (injeções no histórico, última data UTC):")
        for (arquivo, num_linha), info in sorted(
            por_chave.items(), key=lambda kv: (-kv[1]["count"], kv[0][0], kv[0][1])
        ):
            palavras = ", ".join(sorted(info["palavras"]))
            ultima = info["ultima"].strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"  {arquivo}:{num_linha}  {info['count']}x  última={ultima}  palavra(s)={palavras}")
        print()

    injetados_na_janela = set()
    for arquivo, _num_linha, _palavra, dt in registros:
        if dt >= corte:
            injetados_na_janela.add(arquivo)

    memoria_glob = os.path.join(pasta, "memoria", "*.md")
    arquivos_memoria = sorted(glob.glob(memoria_glob))
    nunca_na_janela = [
        caminho.replace(pasta + "/", "")
        for caminho in arquivos_memoria
        if caminho.replace(pasta + "/", "") not in injetados_na_janela
    ]

    print(f"NUNCA INJETADO NOS ÚLTIMOS {args.dias} DIAS (candidato a conferência antes de compactar/arquivar):")
    if not arquivos_memoria:
        print(f"  (nenhum arquivo em {memoria_glob})")
    elif not nunca_na_janela:
        print("  nenhum: todo arquivo de memoria/ apareceu no log dentro da janela.")
    else:
        for rel in nunca_na_janela:
            print(f"  {rel}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
