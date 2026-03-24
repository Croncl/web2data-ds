from datetime import datetime, timedelta
import time
import csv
import os
import pandas as pd
import random
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

SEARCH_TERMS = ["taxação do pix", "taxar o pix", "taxação pix", "taxad pix", "taxar pix", "imposto no pix", "fim do pix de graça"]
SINCE = "2025-01-01"
UNTIL = "2026-02-28" # Pesquisa do ano todo

MAX_TWEETS = 100000
MAX_RETRIES = 6
RETRY_INTERVAL = 120
SCROLL_PAUSE = 6
WINDOW_DAYS = 29 # Janela diária

CSV_PATH = f"tweets_{SEARCH_TERMS[0]}_graph.csv"

def extrair_usuario_da_url(href):
    """Extrai @usuario de uma URL, removendo parâmetros como ?src=..."""
    return "@" + href.split("/")[-1].split("?")[0]

def parse_metric(text):
    if not text: return 0
    text = text.lower().replace(',', '.')
    multiplier = 1
    if 'k' in text or ' mil' in text:
        multiplier = 1000
        text = text.replace('k', '').replace(' mil', '')
    if 'm' in text or ' mi' in text:
        multiplier = 1000000
        text = text.replace('m', '').replace(' mi', '')
    try:
        import re
        match = re.search(r'[\d\.]+', text)
        if match:
            return int(float(match.group()) * multiplier)
        return 0
    except:
        return 0

def wait_for_tweets(driver):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
            )
            return True
        except TimeoutException:
            if attempt < MAX_RETRIES:
                print(f"⌛ Tentativa {attempt}/{MAX_RETRIES} - Aguardando...")
                time.sleep(RETRY_INTERVAL)
            else:
                print("⚠️ Não foi possível carregar tweets")
                return False

def scroll_to_load_all(driver, max_tweets):
    previous_count = 0
    no_new_scrolls = 0
    max_no_new_scrolls = 6
    scroll_attempts = 0
    max_scroll_attempts = 50

    while no_new_scrolls < max_no_new_scrolls and scroll_attempts < max_scroll_attempts:
        try:
            WebDriverWait(driver, 15).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')) > previous_count or no_new_scrolls >= 1
            )
        except TimeoutException:
            print("⌛ Timeout durante espera por novos tweets")

        tweets = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
        current_count = len(tweets)

        if current_count >= max_tweets:
            print(f"✅ Limite de {max_tweets} tweets")
            break

        if current_count == previous_count:
            no_new_scrolls += 1
            print(f"🔁 Nenhum novo tweet após rolagem {scroll_attempts} (tentativas restantes: {max_no_new_scrolls - no_new_scrolls})")
        else:
            no_new_scrolls = 0
            delta = max(0, current_count - previous_count)
            print(f"⬇️ {delta} novos tweets carregados")

        previous_count = current_count
        
        driver.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
        
        wait_time = random.uniform(10, 18)
        print(f"⏳ Aguardando {wait_time:.1f} segundos para carregamento...")
        time.sleep(wait_time)
        
        try:
            error_msg = driver.find_element(By.XPATH, '//*[contains(text(), "Something went wrong")]')
            if error_msg:
                print("⚠️ Erro detectado - aguardando 20 segundos")
                time.sleep(20)
                driver.refresh()
                time.sleep(10)
                no_new_scrolls = 0
        except NoSuchElementException:
            pass

        if "rate limit" in driver.page_source.lower():
            print("⏳ Rate limit detectado - aguardando 5 minutos...")
            time.sleep(300)
            driver.refresh()
            time.sleep(10)
            no_new_scrolls = 0
        scroll_attempts += 1

    print(f"🛑 Finalizado após {scroll_attempts} rolagens. Total de tweets: {previous_count}")

def should_skip_user(username):
    """Filtra apenas usuários que são exatamente o termo de busca"""
    username_lower = username.lower()
    return username_lower == f"@{SEARCH_TERMS[0].lower()}"

def fetch_tweets_from_search(driver, existing_tweets):
    tweets_elements = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
    results = []
    
    for tweet in tweets_elements:
        try:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", tweet)
            time.sleep(random.uniform(5, 10))
            
            user_section = WebDriverWait(tweet, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="User-Name"]'))
            )
            author_link = user_section.find_element(By.XPATH, './/a[contains(@href, "/") and not(contains(@href, "/status/"))]')
            author_handle = extrair_usuario_da_url(author_link.get_attribute("href"))
            
            if should_skip_user(author_handle):
                continue

            tweet_date = tweet.find_element(By.TAG_NAME, "time").get_attribute("datetime") if tweet.find_elements(By.TAG_NAME, "time") else ""
            
            tweetText_element = tweet.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetText"]')
            content = tweetText_element[0].text if tweetText_element else ""
            language = tweetText_element[0].get_attribute("lang") if tweetText_element else ""
            
            tweet_id = tweet.find_element(By.XPATH, './/a[contains(@href, "/status/")]').get_attribute("href").split("/")[-1] if tweet.find_elements(By.XPATH, './/a[contains(@href, "/status/")]') else ""
            is_verified = bool(tweet.find_elements(By.CSS_SELECTOR, 'svg[data-testid="icon-verified"]'))
            has_media = bool(tweet.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"], div[data-testid="videoPlayer"], div[data-testid="card.wrapper"]'))
            
            try:
                replies = parse_metric(tweet.find_element(By.CSS_SELECTOR, 'button[data-testid="reply"]').text)
            except: replies = 0
            try:
                retweets = parse_metric(tweet.find_element(By.CSS_SELECTOR, 'button[data-testid="retweet"]').text)
            except: retweets = 0
            try:
                likes = parse_metric(tweet.find_element(By.CSS_SELECTOR, 'button[data-testid="like"]').text)
            except: likes = 0
            try:
                views_elem = tweet.find_elements(By.XPATH, './/a[contains(@href, "/analytics")]')
                views = parse_metric(views_elem[0].text) if views_elem else 0
            except: views = 0

            reply_to = set()
            try:
                reply_section = tweet.find_element(By.CSS_SELECTOR, 'div[data-testid="reply"]')
                reply_users = reply_section.find_elements(By.XPATH, './/a[contains(@href, "/") and not(contains(@href, "/status/"))]')
                
                for user in reply_users:
                    mention = extrair_usuario_da_url(user.get_attribute("href"))
                    if mention != author_handle and not should_skip_user(mention):
                        reply_to.add(mention)

                if "and others" in reply_section.text:
                    try:
                        driver.execute_script("arguments[0].click();", reply_section)
                        time.sleep(3)
                        
                        modal_users = driver.find_elements(By.XPATH, '//div[@role="dialog"]//a[contains(@href, "/")]')
                        for user in modal_users:
                            mention = extrair_usuario_da_url(user.get_attribute("href"))
                            if mention not in reply_to and not should_skip_user(mention):
                                reply_to.add(mention)
                    except:
                        pass

            except NoSuchElementException:
                pass

            mentions = set()
            for link in tweet.find_elements(By.XPATH, './/a[contains(@href, "/") and not(contains(@href, "/status/"))]'):
                mention = extrair_usuario_da_url(link.get_attribute("href"))
                if mention != author_handle and not should_skip_user(mention):
                    mentions.add(mention)
            
            mentions.update(reply_to)

            new_row = (tweet_id, author_handle, "", tweet_date, is_verified, views, likes, retweets, replies, language, has_media, content)
            if mentions:
                for mention in mentions:
                    results.append((tweet_id, author_handle, mention, tweet_date, is_verified, views, likes, retweets, replies, language, has_media, content))
            else:
                results.append(new_row)

        except Exception as e:
            if "NoSuchElementException" not in str(e):
                print(f"⚠️ Erro inesperado: {str(e)[:100]}")
            continue
    print(f"📊 Tweets encontrados: {len(tweets_elements)}, Após filtro: {len(results)}")
    return results

def salvar_tweets(tweets, existing_tweets, periodo):
    try:
        if not os.path.exists(CSV_PATH):
            with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["tweet_id", "source", "target", "tweet_date", "is_verified", "views", "likes", "retweets", "replies", "language", "has_media", "tweet_text"])
            print(f"🆕 Arquivo CSV criado: {CSV_PATH}")

        new_tweets = [t for t in tweets if t not in existing_tweets]
        count = len(new_tweets)
        
        if count > 0:
            with open(CSV_PATH, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(new_tweets)
            
            print(f"✅ [{periodo}] {count} tweets novos salvos")
            existing_tweets.update(new_tweets)
        else:
            print(f"ℹ️ [{periodo}] Nenhum tweet novo para salvar")
        
        return count
    
    except Exception as e:
        print(f"❌ Erro ao salvar tweets: {e}")
        return 0

def reverse_daterange(start_date, end_date, step_days):
    """Gera intervalos de datas do mais recente para o mais antigo"""
    current_end = end_date
    while current_end > start_date:
        current_start = max(current_end - timedelta(days=step_days), start_date)
        yield current_start, current_end
        current_end = current_start - timedelta(days=1)  # Subtrai 1 dia para evitar sobreposição

def login_manual(driver):
    print("\n==========================================================")
    print("🛑 PAUSA PARA LOGIN MANUAL 🛑")
    print("O navegador abrirá na página inicial do X.")
    print("1. Vá para a janela do Chrome que abriu.")
    print("2. Faça o login na sua conta do Twitter.")
    print("==========================================================")
    driver.get("https://x.com/login")
    input("\n👉 APERTE [ENTER] NESTE TERMINAL APÓS CONCLUIR O LOGIN...> ")
    print("✅ Login confirmado, iniciando a coleta de dados...\n")

def main():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-infobars")
    
    print("🚀 Iniciando o navegador Indetectável (Undetected Chromedriver)...")
    try:
        driver = uc.Chrome(options=options, version_main=146)
    except Exception as e:
        print(f"❌ Erro ao iniciar o driver. Verifique se o undetected-chromedriver está instalado. Detalhes: {e}")
        return
    
    # Pausa para o usuário fazer o login obrigatoriamente
    login_manual(driver)

    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["tweet_id", "source", "target", "tweet_date", "is_verified", "views", "likes", "retweets", "replies", "language", "has_media", "tweet_text"])
        print(f"🆕 Arquivo CSV inicial criado: {CSV_PATH}")

    existing_tweets = set()
    try:
        df_existing = pd.read_csv(CSV_PATH)
        required_columns = {'tweet_id', 'source', 'target', 'tweet_date', 'has_media'}
        
        if not required_columns.issubset(df_existing.columns):
            print("⚠️ Arquivo CSV antigo detectado - não possui as novas métricas. Recriando.")
            os.remove(CSV_PATH)
            with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["tweet_id", "source", "target", "tweet_date", "is_verified", "views", "likes", "retweets", "replies", "language", "has_media", "tweet_text"])
        else:
            existing_tweets = {
                (str(row["tweet_id"]),
                 str(row["source"]).lower(),
                 str(row["target"]).lower() if pd.notna(row["target"]) else "",
                 str(row["tweet_date"]),
                 bool(row["is_verified"]),
                 int(row["views"]) if pd.notna(row["views"]) else 0,
                 int(row["likes"]) if pd.notna(row["likes"]) else 0,
                 int(row["retweets"]) if pd.notna(row["retweets"]) else 0,
                 int(row["replies"]) if pd.notna(row["replies"]) else 0,
                 str(row["language"]) if pd.notna(row["language"]) else "",
                 bool(row["has_media"]),
                 str(row["tweet_text"]))
                for _, row in df_existing.iterrows()
            }
            print(f"📂 {len(existing_tweets)} tweets carregados")

    except Exception as e:
        print(f"⚠️ Erro ao ler CSV: {e} - Recriando")
        os.remove(CSV_PATH)
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["tweet_id", "source", "target", "tweet_date", "is_verified", "views", "likes", "retweets", "replies", "language", "has_media", "tweet_text"])

    try:
        count = 0
        since_date = datetime.strptime(SINCE, "%Y-%m-%d")
        until_date = datetime.strptime(UNTIL, "%Y-%m-%d")
        
        # Modificado para usar reverse_daterange
        for start, end in reverse_daterange(since_date, until_date, WINDOW_DAYS):
            if count >= MAX_TWEETS:
                break

            print(f"\n📅 Período: {start.date()} a {end.date()}")
            
            query = " OR ".join([f'({term})' if " " in term else term for term in SEARCH_TERMS])
            url = f"https://x.com/search?q={query}%20since%3A{start.date()}%20until%3A{end.date()}&src=typed_query&f=live"
            driver.get(url)
            time.sleep(random.uniform(20, 45))

            try:
                WebDriverWait(driver, 35).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
                )
            except TimeoutException:
                print("⚠️ Timeout ao abrir busca — tentando recarregar")
                driver.refresh()
                time.sleep(random.uniform(25, 55))
                try:
                    WebDriverWait(driver, 50).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
                    )
                except TimeoutException:
                    print("❌ Ainda sem sucesso — pulando período")
                    continue

            if not wait_for_tweets(driver):
                continue

            scroll_to_load_all(driver, MAX_TWEETS - count)
            tweets = fetch_tweets_from_search(driver, existing_tweets)
            count += salvar_tweets(tweets, existing_tweets, f"{start.date()} a {end.date()}")

            intervalo = random.uniform(25, 60)
            print(f"⏸️ Aguardando {intervalo:.1f} segundos antes da próxima janela...")
            time.sleep(intervalo)

    finally:
        driver.quit()
        print(f"\n✅ Total de tweets salvos: {count}")

if __name__ == "__main__":
    main()