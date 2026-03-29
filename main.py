"""
Módulo de Análise de Sentimento para Tweets Políticos (pt-BR)
Projeto: web2data-ds | Autor: Croncl
"""

import pandas as pd
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from pysentimiento import create_analyzer
from tqdm import tqdm
import re
import os

# Garante recursos do NLTK na primeira execução
try:
    stopwords_pt = stopwords.words("portuguese")
except LookupError:
    nltk.download("stopwords", quiet=True)
    nltk.download("punkt", quiet=True)
    stopwords_pt = stopwords.words("portuguese")

# Carrega modelo de sentimento
print("🔄 Carregando modelo de análise de sentimento (pysentimiento)...")
analyzer = create_analyzer(task="sentiment", lang="pt")


def limpar_tweet(texto):
    """Limpeza básica com NLTK + Regex para tweets em português"""
    if not isinstance(texto, str) or not texto.strip():
        return ""

    texto = texto.lower()
    texto = re.sub(r"http\S+|www\S+|https\S+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"@\w+|#\w+", "", texto)
    texto = re.sub(r"[^\w\s]", " ", texto)

    try:
        tokens = word_tokenize(texto, language="portuguese")
    except:
        tokens = texto.split()

    tokens_filtrados = [w for w in tokens if w.isalpha() and w not in stopwords_pt]
    return " ".join(tokens_filtrados)


def analisar_sentimento(df, coluna_tweet="tweet_text"):
    """
    Aplica análise de sentimento em um DataFrame de tweets.
    """
    if coluna_tweet not in df.columns:
        raise ValueError(
            f"Coluna '{coluna_tweet}' não encontrada. Disponíveis: {df.columns.tolist()}"
        )

    sentimentos, confiancas = [], []

    for tweet in tqdm(df[coluna_tweet], desc="🔍 Analisando tweets"):
        texto_limpo = limpar_tweet(tweet)

        # Se o texto ficar vazio após limpeza, marca como NEUTRO
        if len(texto_limpo) < 2:
            sentimentos.append("NEUTRO")
            confiancas.append(0.0)
            continue

        try:
            resultado = analyzer.predict(texto_limpo)
            sentimentos.append(resultado.output)
            confiancas.append(max(resultado.probas.values()))
        except Exception as e:
            sentimentos.append("ERRO")
            confiancas.append(0.0)

    df["sentimento"] = sentimentos
    df["confianca"] = confiancas
    return df


def main():
    DIR_RAW = os.path.join("data", "raw")
    DIR_PROCESSED = os.path.join("data", "processed")

    os.makedirs(DIR_PROCESSED, exist_ok=True)

    arquivos = [f for f in os.listdir(DIR_RAW) if f.endswith(".csv")]

    if not arquivos:
        print(f"⚠️ Nenhum arquivo .csv encontrado em '{DIR_RAW}'")
        return

    for arquivo in arquivos:
        caminho_entrada = os.path.join(DIR_RAW, arquivo)
        nome_saida = f"analise_{arquivo}"
        caminho_saida = os.path.join(DIR_PROCESSED, nome_saida)

        print(f"\n📄 Processando: {arquivo}")
        try:
            # Tenta diferentes encodings
            for encoding in ["utf-8-sig", "latin1", "cp1252"]:
                try:
                    df = pd.read_csv(caminho_entrada, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Erro de encoding.")

            # Garante que a data seja legível pelo pandas
            if "tweet_date" in df.columns:
                df["tweet_date"] = pd.to_datetime(df["tweet_date"], errors="coerce")

            df = analisar_sentimento(df, coluna_tweet="tweet_text")
            df.to_csv(caminho_saida, index=False, encoding="utf-8-sig")

            print(f"✅ Salvo em: {caminho_saida}")
            print(f"📊 Resumo:\n{df['sentimento'].value_counts().to_string()}")

        except Exception as e:
            print(f"❌ Erro ao processar {arquivo}: {e}")


if __name__ == "__main__":
    print("🚀 Iniciando módulo de análise - web2data-ds")
    main()
