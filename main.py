import pandas as pd
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from pysentimiento import create_analyzer
from tqdm import tqdm
import os
import re

# Baixa recursos do NLTK na primeira vez
try:
    stopwords_pt = stopwords.words("portuguese")
except LookupError:
    nltk.download("stopwords")
    nltk.download("punkt")
    stopwords_pt = stopwords.words("portuguese")

print("Carregando modelo de IA (Transformers)...")
analyzer = create_analyzer(task="sentiment", lang="pt")

ARQUIVO_ENTRADA = "tweets_politica.csv"
ARQUIVO_SAIDA = "tweets_politica_analisado.csv"

if not os.path.exists(ARQUIVO_ENTRADA):
    print(f"Erro: Arquivo {ARQUIVO_ENTRADA} não encontrado.")
    exit()

df = pd.read_csv(ARQUIVO_ENTRADA)


# --- FUNÇÃO DE LIMPEZA COM NLTK ---
def preprocessar_tweet(texto):
    if not isinstance(texto, str):
        return ""

    # 1. Minúsculas
    texto = texto.lower()

    # 2. Remover URLs e Menções (@usuario) - Importante para política
    texto = re.sub(r"http\S+|www\S+|https\S+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"@\w+|#\w+", "", texto)

    # 3. Tokenização (NLTK)
    try:
        tokens = word_tokenize(texto, language="portuguese")
    except:
        tokens = texto.split()  # Fallback se faltar pacote punkt

    # 4. Remover Stopwords (palavras vazias como 'de', 'o', 'a')
    # Nota: Em análise de sentimento, às vezes manter stopwords ajuda no contexto.
    # Aqui vamos remover apenas as muito comuns para limpar ruído.
    tokens_filtrados = [
        word for word in tokens if word.isalpha() and word not in stopwords_pt
    ]

    return " ".join(tokens_filtrados)


print("Iniciando pré-processamento e análise...")

sentimentos = []
confiancas = []

for tweet in tqdm(df["tweet"], desc="Processando"):
    # 1. Limpa com NLTK
    texto_limpo = preprocessar_tweet(tweet)

    if len(texto_limpo) < 3:
        sentimentos.append("NEUTRO")
        confiancas.append(0.0)
        continue

    # 2. Classifica com pysentimiento (IA Moderna)
    try:
        resultado = analyzer.predict(texto_limpo)
        sentimentos.append(resultado.output)
        confiancas.append(max(resultado.probas.values()))
    except:
        sentimentos.append("ERRO")
        confiancas.append(0.0)

df["texto_limpo"] = df["tweet"].apply(preprocessar_tweet)
df["sentimento"] = sentimentos
df["confianca"] = confiancas

df.to_csv(ARQUIVO_SAIDA, index=False, encoding="utf-8-sig")
print(f"\nConcluído! Arquivo salvo: {ARQUIVO_SAIDA}")
print(df["sentimento"].value_counts())
