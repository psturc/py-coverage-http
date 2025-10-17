# app.py
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello, World!"

@app.route('/status')
def status():
    return jsonify({"status": "ok"})

# This route will not be hit by our tests
@app.route('/untested')
def untested():
    return "This is not tested.", 418

if __name__ == '__main__':
    # In a real setup, a production server like Gunicorn would run this.
    app.run(host='0.0.0.0', port=8080)