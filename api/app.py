from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from utils.db import init_pool
from utils.json_provider import ISODateJSONProvider
from routes import usuarios, turmas, eventos, faces, recorrencias, dispositivos


def create_app():
    app = Flask(__name__)
    app.json_provider_class = ISODateJSONProvider
    app.json = ISODateJSONProvider(app)
    CORS(app)  # em produção, restrinja allowed origins conforme necessário

    init_pool()

    app.register_blueprint(usuarios.bp)
    app.register_blueprint(turmas.bp)
    app.register_blueprint(eventos.bp)
    app.register_blueprint(faces.bp)
    app.register_blueprint(recorrencias.bp)
    app.register_blueprint(dispositivos.bp)

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    # Waitress em vez do servidor embutido do Flask.
    #
    # Com debug=True o Werkzeug liga um "reloader" que reinicia o processo
    # sozinho ao ver arquivo mudar. Isso é ótimo escrevendo código e
    # péssimo em demonstração: com o TensorFlow carregado ele já travou
    # ("could not acquire lock ... daemon threads") e derrubou a API no
    # meio do uso, sem ninguém encostar em nada. O servidor embutido
    # também atende uma requisição por vez - com a Raspberry perguntando
    # de segundo em segundo e o app consultando junto, dava fila.
    #
    # Pra voltar ao modo de desenvolvimento (reload automático a cada
    # save), rode: python app.py --dev
    import sys

    if "--dev" in sys.argv:
        app.run(host="0.0.0.0", port=Config.PORT, debug=True)
    else:
        from waitress import serve

        print(f"Fetin API em http://0.0.0.0:{Config.PORT}  (Ctrl+C para parar)")
        serve(app, host="0.0.0.0", port=Config.PORT, threads=8)
