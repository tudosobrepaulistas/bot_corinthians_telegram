import json
import os
import html
import re
import requests
import feedparser

# Configuração (vem dos Secrets do GitHub)
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]          # ex: @meucanal ou -100xxxxxxxxxx
FEED_URL = os.environ["FEED_URL"]                 # ex: https://seusite.com.br/categoria/corinthians/feed
ARQUIVO_ENVIADOS = "enviados.json"
MAX_GUARDADOS = 300

API = f"https://api.telegram.org/bot{TOKEN}"


def carregar_enviados():
    if os.path.exists(ARQUIVO_ENVIADOS):
        with open(ARQUIVO_ENVIADOS, encoding="utf-8") as f:
            return json.load(f)
    return None  # primeira execução


def salvar_enviados(lista):
    with open(ARQUIVO_ENVIADOS, "w", encoding="utf-8") as f:
        json.dump(lista[-MAX_GUARDADOS:], f, ensure_ascii=False, indent=0)


def pegar_imagem(item):
    # 1) media:content / media:thumbnail
    for campo in ("media_content", "media_thumbnail"):
        if campo in item and item[campo]:
            url = item[campo][0].get("url")
            if url:
                return url
    # 2) enclosure
    for enc in item.get("enclosures", []):
        if enc.get("type", "").startswith("image"):
            return enc.get("href")
    # 3) primeira <img> no conteúdo
    conteudo = ""
    if item.get("content"):
        conteudo = item["content"][0].get("value", "")
    conteudo = conteudo or item.get("summary", "")
    m = re.search(r'<img[^>]+src="([^"]+)"', conteudo)
    return m.group(1) if m else None


def enviar(item):
    titulo = html.escape(item.get("title", "").strip())
    link = item.get("link", "")
    texto = f"⚫⚪ <b>{titulo}</b>\n\n👉 <a href=\"{link}\">Leia a matéria completa</a>"
    botao = {"inline_keyboard": [[{"text": "📰 Ler no Tudo Sobre Paulista", "url": link}]]}
    imagem = pegar_imagem(item)

    if imagem:
        r = requests.post(f"{API}/sendPhoto", data={
            "chat_id": CHAT_ID, "photo": imagem, "caption": texto,
            "parse_mode": "HTML", "reply_markup": json.dumps(botao)}, timeout=30)
        if r.ok:
            return True
    # sem imagem (ou falhou a imagem): manda texto com prévia do link
    r = requests.post(f"{API}/sendMessage", data={
        "chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML",
        "reply_markup": json.dumps(botao)}, timeout=30)
    if not r.ok:
        print("Erro ao enviar:", r.text)
    return r.ok


def main():
    feed = feedparser.parse(FEED_URL)
    itens = feed.entries
    if not itens:
        print("Feed vazio ou inacessível.")
        return

    enviados = carregar_enviados()
    ids = [i.get("id") or i.get("link") for i in itens]

    # Primeira execução: só registra o que já existe, para não lotar o canal
    if enviados is None:
        salvar_enviados(ids[::-1])
        print(f"Primeira execução: {len(ids)} posts marcados como já enviados.")
        return

    novos = [i for i in itens if (i.get("id") or i.get("link")) not in enviados]
    for item in reversed(novos):  # do mais antigo pro mais novo
        if enviar(item):
            enviados.append(item.get("id") or item.get("link"))
            print("Enviado:", item.get("title"))

    salvar_enviados(enviados)


if __name__ == "__main__":
    main()
