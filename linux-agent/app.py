from flask import Flask, request, jsonify, render_template
from agent_core import KubernetesAgent

app = Flask(__name__)
agent = KubernetesAgent()

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True)
        if not data or "message" not in data:
            return jsonify({
                "error": "Invalid request. Expected JSON with 'message'"
            }), 400

        user_message = data["message"]
        output = agent.handle(user_message)

        return jsonify({
            "response": output
        })

    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
