#!/usr/bin/env python3
import os

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template
from flask_cors import CORS
from index.index import check_auth
from modules.Swagger.swagger import swagger_bp
from modules.TutoringCalculator.routes import tutoring_bp
from modules.Monitor.routes import monitoring_bp
from modules.ToDo.routes import todo_bp
from modules.InvoiceGenerator.routes import invoice_bp
from modules.Finance.routes import finance_bp

app = Flask(__name__, static_folder='index/static', static_url_path='/static', template_folder='index')
CORS(app)

# Register Swagger documentation UI & OpenAPI spec
app.register_blueprint(swagger_bp)

# Register Monitoring dashboard & endpoints
app.register_blueprint(monitoring_bp)

# Register Tutoring Calculator endpoints (both top-level and with /TutoringCalculator prefix)
app.register_blueprint(tutoring_bp)
app.register_blueprint(tutoring_bp, name='tutoring_calculator', url_prefix='/TutoringCalculator')

# Register To-Do board & endpoints
app.register_blueprint(todo_bp)

# Register Invoice Generator & history endpoints
app.register_blueprint(invoice_bp)
app.register_blueprint(invoice_bp, name='invoice_generator', url_prefix='/InvoiceGenerator')

# Register Financial Dashboard & SimpleFIN endpoints
app.register_blueprint(finance_bp)
app.register_blueprint(finance_bp, name='finance_dashboard', url_prefix='/Finance')


@app.before_request
def auth():
    return check_auth()


@app.route("/test")
def test():
    return {"status": "success", "message": "Hello, World!"}


@app.route("/privacy", methods=["GET"])
def privacy():
    return render_template("privacy.html")



if __name__ == "__main__":
    from modules.TutoringCalculator.config import CONFIG
    port = int(os.environ.get("PORT", CONFIG.get("PORT", 5000)))
    app.run(host="0.0.0.0", port=port, debug=True)