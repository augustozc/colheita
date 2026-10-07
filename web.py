import hmac
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agente Macro</title>
  <style>
    body { max-width: 900px; margin: 40px auto; padding: 0 16px;
           font: 16px system-ui, sans-serif; color: #222; }
    input, button { padding: 10px; margin: 6px 0; }
    input { width: min(420px, 90%); }
    button { cursor: pointer; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #f4f4f4;
          padding: 16px; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>Agente Macro</h1>
  <label for="token">APP_TOKEN</label><br>
  <input id="token" type="password" autocomplete="off"
         placeholder="Informe o token configurado no Render">
  <button id="run" type="button">Gerar relatório</button>
  <pre id="result">O relatório aparecerá aqui.</pre>

  <script>
    const button = document.getElementById("run");
    const result = document.getElementById("result");

    button.addEventListener("click", async () => {
      button.disabled = true;
      result.textContent = "Gerando relatório...";
      try {
        const response = await fetch("/generate", {
          method: "POST",
          headers: {
            "Authorization": "Bearer " + document.getElementById("token").value
          }
        });
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || "Falha ao gerar relatório");
        }
        result.textContent = data.report || "O relatório está vazio.";
      } catch (error) {
        result.textContent = "Erro: " + error.message;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.post("/generate")
def generate():
    token = os.getenv("APP_TOKEN")
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")

    if not token:
        return jsonify(error="APP_TOKEN não está configurado no Render"), 503
    if not hmac.compare_digest(supplied, token):
        return jsonify(error="Token inválido"), 401

    try:
        with tempfile.TemporaryDirectory(prefix="agente-macro-") as temp_dir:
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "agente.py")],
                cwd=temp_dir,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=180,
            )

            if result.returncode != 0:
                app.logger.error("Falha no agente: %s", result.stderr)
                return jsonify(error="Falha ao executar o agente"), 502

            report_path = Path(temp_dir) / "Relatorio_Estresse_Patrimonial.md"
            if not report_path.is_file():
                app.logger.error("Relatório não encontrado. Saída: %s", result.stdout)
                return jsonify(
                    error="O agente terminou, mas não gerou o arquivo do relatório."
                ), 500

            report = report_path.read_text(encoding="utf-8")
            return jsonify(status="concluído", report=report)

    except subprocess.TimeoutExpired:
        return jsonify(error="A geração do relatório excedeu o limite de tempo"), 504
    except OSError:
        app.logger.exception("Erro ao iniciar o agente")
        return jsonify(error="Não foi possível iniciar o agente"), 500