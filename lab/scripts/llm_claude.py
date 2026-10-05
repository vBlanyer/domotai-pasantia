"""Sustituto de llama-server SOLO PARA PRUEBAS: sirve en 127.0.0.1:8080 la misma API que usa el
prototipo (/health, /props y /v1/chat/completions con json_schema) y genera con `claude -p`, es
decir, con tu sesión de Claude Code y sin API key. El prototipo no cambia: el justificador, el RAG
agéntico y el agente ReAct hablan con este servidor como si fuera el modelo local.

Sirve para probar el flujo de punta a punta cuando el portátil no mueve el modelo local. No sirve
para sacar conclusiones del modelo que se despliega, y tiene tres límites que lo dejan fuera de
producción:
  - los prompts salen del portátil hacia Anthropic: solo con el banco sintético, nunca con datos
    reales de un cliente;
  - `claude -p` no deja fijar la temperatura a 0, así que no es reproducible (RNF-03);
  - gasta la cuota del plan de Claude de quien lo arranca.
La traza lo deja dicho: /props anuncia «claude-code-<modelo>» y cada justificación queda como
«llm-7e:claude-code-<modelo>».

Los embeddings del RAG (:8082) siguen siendo locales (sh lab/scripts/llm-server.sh --embedder).

Uso:  python3 lab/scripts/llm_claude.py [--modelo haiku|sonnet|opus] [--puerto 8080]
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SISTEMA = ("Eres el modelo de lenguaje de un prototipo de ciberseguridad (triaje de alertas y "
           "contención). Responde solo lo que se te pide, en español, sin preámbulos.")
# Por debajo de los 120 s con los que espera el cliente (justificador_llm.generador_servidor):
# así el prototipo recibe un 500 y degrada a plantilla en vez de cortar él la conexión.
PLAZO_S = 110


def binario_claude():
    """El CLI de Claude Code: CLAUDE_BIN, el del PATH o el que trae la extensión de VS Code."""
    if os.environ.get("CLAUDE_BIN"):
        return os.environ["CLAUDE_BIN"]
    if shutil.which("claude"):
        return shutil.which("claude")
    candidatos = glob.glob(os.path.expanduser(
        "~/.vscode-server/extensions/anthropic.claude-code-*/resources/native-binary/claude"))
    return max(candidatos, key=os.path.getmtime) if candidatos else None


def comando(binario, modelo, esquema=None):
    # Sin herramientas, sin ajustes (ni plugins ni hooks del usuario, que meterían texto en el
    # prompt) y sin guardar sesión: un generador de texto, no un agente con acceso al repo.
    cmd = [binario, "-p", "--model", modelo, "--tools", "", "--setting-sources", "",
           "--no-session-persistence", "--system-prompt", SISTEMA, "--output-format", "json"]
    if esquema is not None:
        cmd += ["--json-schema", json.dumps(esquema)]
    return cmd


def _entorno():
    # Sin ANTHROPIC_API_KEY el CLI usa la sesión iniciada: nunca factura por API.
    return {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}


def generar(prompt, esquema=None, modelo="haiku", binario=None, timeout=PLAZO_S, _run=subprocess.run):
    """El texto generado (con esquema, el objeto validado serializado) o None ante cualquier fallo."""
    binario = binario or binario_claude()
    if not binario:
        return None
    # Desde una carpeta vacía: el CLI no lee el CLAUDE.md ni la memoria del repo.
    with tempfile.TemporaryDirectory() as vacia:
        try:
            cp = _run(comando(binario, modelo, esquema), input=prompt, capture_output=True,
                      text=True, timeout=timeout, cwd=vacia, env=_entorno())
        except (subprocess.TimeoutExpired, OSError):
            return None
    try:
        datos = json.loads(cp.stdout)
    except ValueError:
        return None
    if datos.get("is_error"):
        return None
    if esquema is not None:
        objeto = datos.get("structured_output")
        return json.dumps(objeto, ensure_ascii=False) if objeto is not None else None
    return datos.get("result")


def respuesta_chat(cuerpo, generar_fn, modelo):
    """(estado HTTP, cuerpo) para POST /v1/chat/completions, con la forma que lee el prototipo."""
    mensajes = cuerpo.get("messages") or []
    prompt = "\n\n".join(str(m.get("content") or "") for m in mensajes if isinstance(m, dict))
    formato = cuerpo.get("response_format") or {}
    esquema = ((formato.get("json_schema") or {}).get("schema")
               if formato.get("type") == "json_schema" else None)
    texto = generar_fn(prompt, esquema)
    if texto is None:
        return 500, {"error": {"message": "claude -p no devolvió respuesta"}}
    return 200, {"object": "chat.completion", "model": f"claude-code-{modelo}",
                 "choices": [{"index": 0, "finish_reason": "stop",
                              "message": {"role": "assistant", "content": texto}}]}


def crear_servidor(modelo="haiku", puerto=8080, generar_fn=None, registro=None):
    generar_fn = generar_fn or (lambda prompt, esquema: generar(prompt, esquema, modelo))

    class Manejador(BaseHTTPRequestHandler):
        def _json(self, estado, datos):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(estado)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            if self.path == "/health":
                return self._json(200, {"status": "ok"})
            if self.path == "/props":
                return self._json(200, {"model_path": f"claude-code-{modelo}"})
            self._json(404, {"error": {"message": "no existe"}})

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                return self._json(404, {"error": {"message": "no existe"}})
            try:
                cuerpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            except ValueError:
                return self._json(400, {"error": {"message": "JSON mal formado"}})
            inicio = time.monotonic()
            estado, datos = respuesta_chat(cuerpo, generar_fn, modelo)
            if registro:
                con_esquema = "con esquema" if (cuerpo.get("response_format") or {}).get("type") else "texto"
                registro(f"[claude] {time.monotonic() - inicio:.1f} s, {con_esquema}, "
                         f"{'ok' if estado == 200 else 'FALLO -> el prototipo usará la plantilla'}")
            self._json(estado, datos)

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sustituto de llama-server con Claude Code (solo pruebas).")
    ap.add_argument("--modelo", default="haiku", help="haiku (por defecto), sonnet u opus")
    ap.add_argument("--puerto", type=int, default=8080)
    args = ap.parse_args(argv)
    binario = binario_claude()
    if not binario:
        sys.exit("No encuentro el CLI de Claude Code: instálalo o indica su ruta con CLAUDE_BIN.")
    try:
        srv = crear_servidor(args.modelo, args.puerto, registro=lambda linea: print(linea, flush=True))
    except OSError as e:
        sys.exit(f"No puedo escuchar en el puerto {args.puerto} ({e}). ¿Sigue el llama-server? "
                 "Páralo con: sh lab/scripts/llm-server.sh --parar")
    print(f"Claude Code ({args.modelo}) sirviendo como LLM en http://127.0.0.1:{args.puerto} — SOLO PRUEBAS.\n"
          "  Los prompts salen hacia Anthropic (solo datos del banco), no es reproducible y gasta tu cuota.\n"
          f"  CLI: {binario}\n  Ctrl+C para parar.", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
