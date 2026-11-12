"""Servidor local do quiz: serve a página e conversa com a IA (API da Anthropic).
Aceita GEMINI_API_KEY (gratuito) ou ANTHROPIC_API_KEY (pago). A chave fica só aqui no servidor (variável de ambiente), nunca vai para o navegador.
Uso:  set ANTHROPIC_API_KEY=sua_chave   (Windows)   |   export ANTHROPIC_API_KEY=sua_chave  (Linux/Mac)
      python server.py   ->  abra http://localhost:8000
Só usa a biblioteca padrão do Python (sem pip install)."""
import json, os, re, time, urllib.error, urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CHAVE_G = os.environ.get("GEMINI_API_KEY", "")      # Google Gemini (tem plano gratuito)
CHAVE = os.environ.get("ANTHROPIC_API_KEY", "")     # Anthropic (pago)
MODELO = os.environ.get("MODELO", "gemini-3.8-flash" if CHAVE_G else "claude-sonnet-5-5")
MODELOS_G = [m.strip() for m in os.environ.get("MODELO", "gemini-3.8-flash,gemini-3.6-flash").split(",") if m.strip()]
PORTA = int(os.environ.get("PORTA", "8000"))

SISTEMA = ("Você cria perguntas de quiz em português do Brasil para um evento de portas abertas de uma "
           "universidade, com público de Ensino Médio. Use apenas fatos bem conhecidos e verificáveis, "
           "conteúdo leve e adequado para adolescentes. Cada pergunta tem 1 resposta certa e 3 erradas "
           "plausíveis, curtas (até 40 caracteres). Responda SOMENTE com um array JSON, sem texto extra "
           'nem crases: [{"q":"pergunta","ok":"certa","err":["e1","e2","e3"]}]')

def _chamar_gemini(modelo, tema, n):
    corpo = {"systemInstruction": {"parts": [{"text": SISTEMA}]},
             "contents": [{"role": "user", "parts": [{"text": f"Tema: {tema[:80]}. Crie {n} perguntas, variando a dificuldade."}]}],
             "generationConfig": {"responseMimeType": "application/json"}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
        json.dumps(corpo).encode(), {"content-type": "application/json", "x-goog-api-key": CHAVE_G})
    with urllib.request.urlopen(req, timeout=25) as r:
        partes = json.load(r)["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in partes)

def gerar_gemini(tema, n):
    """Tenta cada modelo; se o Google responder 503/429 (sobrecarga), espera e tenta de novo."""
    ultimo = None
    for modelo in MODELOS_G:
        for tentativa in range(3):
            try:
                return _chamar_gemini(modelo, tema, n)
            except urllib.error.HTTPError as e:
                print(f"[{modelo}] tentativa {tentativa+1}: HTTP {e.code} {e.read().decode('utf8','ignore')[:200]}")
                ultimo = e
                if e.code in (429, 500, 502, 503, 504): time.sleep(2 * (tentativa + 1)); continue
                break  # 400/403/404: esse modelo nao serve, tenta o proximo
            except Exception as e:
                print(f"[{modelo}] erro: {e}"); ultimo = e; break
    raise ultimo or RuntimeError("falhou")

def gerar(tema, n):
    if CHAVE_G:
        txt = gerar_gemini(tema, n)
        txt = re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip()
        dados = json.loads(txt)
        return [d for d in dados if isinstance(d.get("q"), str) and isinstance(d.get("ok"), str)
                and isinstance(d.get("err"), list) and len(d["err"]) == 3][:n]
    corpo = {"model": MODELO, "max_tokens": 2500, "system": SISTEMA,
             "messages": [{"role": "user", "content": f"Tema: {tema[:80]}. Crie {n} perguntas, variando a dificuldade."}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", json.dumps(corpo).encode(),
        {"content-type": "application/json", "x-api-key": CHAVE, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=40) as r:
        txt = "".join(b.get("text", "") for b in json.load(r)["content"])
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip()
    dados = json.loads(txt)
    return [d for d in dados if isinstance(d.get("q"), str) and isinstance(d.get("ok"), str)
            and isinstance(d.get("err"), list) and len(d["err"]) == 3][:n]

class H(SimpleHTTPRequestHandler):
    def do_POST(self):
        try:
            if self.path != "/gerar": raise ValueError("rota")
            if not (CHAVE or CHAVE_G): raise ValueError("sem chave")
            p = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps(gerar(str(p["tema"]), max(1, min(int(p["n"]), 20)))).encode()
            self.send_response(200)
        except Exception as e:
            print("Erro ao gerar:", e)
            out = b"[]"; self.send_response(502)
        self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(out)

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    print("IA:", "Gemini" if CHAVE_G else ("Anthropic" if CHAVE else "nenhuma (so offline)"), MODELO, "| abra http://localhost:%d" % PORTA)
    ThreadingHTTPServer(("", PORTA), H).serve_forever()
