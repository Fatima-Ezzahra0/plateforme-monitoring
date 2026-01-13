import dash
from dash import dcc, html, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import json, os, io, csv, random
from datetime import datetime
import google.generativeai as genai

# ===================== CONFIG =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
PENDING_FILE = os.path.join(BASE_DIR, "pending_users.json")
APPROVED_FILE = os.path.join(BASE_DIR, "approved_users.json")
REJECTED_FILE = os.path.join(BASE_DIR, "rejected_users.json")

# CONFIGURATION GEMINI - Mis à jour pour Gemini 2.0 Flash
# On essaie d'abord de lire la clé depuis l'environnement (Cloud), sinon on utilise la vôtre
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyDSHkgLkCHPcDnhpVE7Eob1m3aIQPRbzDA") 
genai.configure(api_key=GOOGLE_API_KEY)
model_gemini = genai.GenerativeModel('gemini-2.0-flash')

# SEUILS D'ALERTE
THRESHOLD_TEMP = 70.0
THRESHOLD_SPEED = 2500.0
THRESHOLD_VIB = 4.0

# ===================== LOAD USERS =====================
def load_json(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list) and all(isinstance(u, dict) and "username" in u for u in data):
                    return data
            except:
                pass
    return []

PENDING_USERS = load_json(PENDING_FILE)
APPROVED_USERS = load_json(APPROVED_FILE)
REJECTED_USERS = load_json(REJECTED_FILE)

USERS = {"Fatima-ezzahra": "1234", "admin": "admin"}
for user in APPROVED_USERS:
    USERS[user["username"]] = user["password"]

# ===================== DASH APP =====================
external_stylesheets = [dbc.themes.BOOTSTRAP]
app = dash.Dash(__name__, external_stylesheets=external_stylesheets, suppress_callback_exceptions=True)
server = app.server # <--- MODIFICATION 1: Pour l'hébergement Cloud (Gunicorn)
app.title = "Platform"

# ===================== HTML INDEX =====================
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body { background: #ecf0f1; font-family: 'Segoe UI', sans-serif; }
            .sidebar { position: fixed; top: 0; left: 0; height: 100vh; width: 220px; padding: 20px; background: #2c3e50; color: #ecf0f1; box-shadow: 2px 0 6px rgba(0,0,0,0.2); }
            .sidebar .nav-link { color: #ecf0f1; margin-bottom: 8px; }
            .sidebar .nav-link:hover, .sidebar .nav-link.active { background-color: #34495e; border-radius: 6px; }
            .content { margin-left: 240px; padding: 24px; }
            .graph-card { background: #fdfdfd; padding: 12px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
            .pending-user { display:flex; align-items:center; gap:10px; padding:6px 0; border-bottom:1px solid #eee; }
            .center-card { margin: 60px auto; }
            .small-input { max-width: 320px; margin: 6px auto; display:block; }
            .brand-logos { display:flex; gap:10px; justify-content:center; align-items:center; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
        <script>
            function scrollChat() {
                const chatContainer = document.getElementById('chat-container');
                if(chatContainer) { chatContainer.scrollTop = chatContainer.scrollHeight; }
            }
            setInterval(scrollChat, 500);
        </script>
    </body>
</html>
"""

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content")
])

# ===================== SENSOR DATA =====================
HISTORY_LIMIT = 500
sensor_data = {"temperature":25.0,"speed":1200.0,"vibration":[],"acoustic":[],"history":[]}

def record_history():
    ts = datetime.utcnow().isoformat()
    vib_mean = sum(sensor_data["vibration"])/len(sensor_data["vibration"]) if sensor_data["vibration"] else 0.0
    acou_mean = sum(sensor_data["acoustic"])/len(sensor_data["acoustic"]) if sensor_data["acoustic"] else 0.0
    entry = {"timestamp": ts, "temperature": sensor_data["temperature"], "speed": sensor_data["speed"],
             "vibration": vib_mean, "acoustic": acou_mean}
    sensor_data["history"].append(entry)
    if len(sensor_data["history"]) > HISTORY_LIMIT: sensor_data["history"].pop(0)

def simulate_sensor_data():
    sensor_data["temperature"] = random.uniform(20, 85) 
    sensor_data["speed"] = random.uniform(500, 2800)
    if len(sensor_data["vibration"]) >= 50: sensor_data["vibration"].pop(0)
    sensor_data["vibration"].append(random.uniform(0,6)) 
    if len(sensor_data["acoustic"]) >= 50: sensor_data["acoustic"].pop(0)
    sensor_data["acoustic"].append(random.uniform(0,80))

# ===================== SIDEBAR =====================
sidebar = html.Div([
    html.Div([html.Img(src="/assets/emsi_logo.png", style={"height":"50px"}),
              html.Img(src="/assets/xr_logo.png", style={"height":"50px"})], className="brand-logos mb-3"),
    dbc.Nav([
        dbc.NavLink("Control Panel", href="/dashboard", id="nav-dashboard", active="exact"),
        dbc.NavLink("3D Visualization", href="/3dmodel", id="nav-3d", active="exact"),
        dbc.NavLink("IA: Open Chat", href="/ai", id="nav-ai", active="exact"),
        dbc.NavLink("Sensor Archives", href="/history", id="nav-history", active="exact"),
        dbc.NavLink("Account privacy", href="/admin", id="nav-admin", active="exact"),
        html.Hr(),
        dbc.NavLink("Sign Out", href="/", id="nav-logout")
    ], vertical=True, pills=True)
], className="sidebar")

# ===================== LOGIN & REGISTER =====================
login_layout = dbc.Container([
    html.Div([html.Div([html.Img(src="/assets/emsi_logo.png", style={"height": "60px"}),
                        html.Img(src="/assets/xr_logo.png", style={"height": "60px"})], className="brand-logos mb-3"),
              html.H2("Login", className="text-center"),
              dbc.Input(id="login-username", placeholder="Username", type="text", className="small-input"),
              dbc.Input(id="login-password", placeholder="Password", type="password", className="small-input"),
              dbc.Button("Sign In", id="login-button", color="primary", className="w-100", style={"maxWidth":"320px","margin":"10px auto","display":"block"}),
              html.Div(id="login-message", className="text-danger mt-2 text-center"),
              html.Hr(),
              html.Div(html.A("Create an account", href="/register"), className="text-center")
             ], className="center-card", style={"maxWidth":"420px"})
], className="mt-5")

register_layout = dbc.Container([
    html.H2("Register", className="text-center"),
    dbc.Input(id="register-username", placeholder="Username", type="text", className="small-input"),
    dbc.Input(id="register-password", placeholder="Password", type="password", className="small-input"),
    dbc.Button("Sign Up", id="register-button", color="success", className="w-100", style={"maxWidth":"320px","margin":"10px auto","display":"block"}),
    html.Div(id="register-message", className="text-info mt-2 text-center"),
    html.Hr(),
    html.Div(html.A("Already have an account? Login", href="/"), className="text-center")
], className="mt-3")

# ===================== DASHBOARD =====================
def dashboard_layout():
    return html.Div([sidebar,
        html.Div([
            dcc.Interval(id="update-interval", interval=2000, n_intervals=0),
            html.H3("Dashboard", style={"marginBottom":"20px"}),
            html.Div(id="alert-container"), 
            html.Div(style={"display":"flex","gap":"20px","flexWrap":"wrap"}, children=[
               dcc.Graph(id="gauge-temp", style={"flex":"1 1 35%","height":"250px"}, className="graph-card"),
               dcc.Graph(id="gauge-speed", style={"flex":"1 1 35%","height":"250px"}, className="graph-card")
            ]),
            html.Div(style={"display":"flex","gap":"20px","marginTop":"20px","flexWrap":"wrap"}, children=[
                dcc.Graph(id="graph-vibration", style={"flex":"1 1 48%","height":"350px"}, className="graph-card"),
                dcc.Graph(id="graph-acoustic", style={"flex":"1 1 48%","height":"350px"}, className="graph-card")
            ]),
            html.Hr(),
            html.Div([
                dbc.Row([
                    dbc.Col(dbc.Card([dbc.CardBody([html.H6("Last Temperature"), html.H4(id="last-temp")])]), md=3),
                    dbc.Col(dbc.Card([dbc.CardBody([html.H6("Last Speed"), html.H4(id="last-speed")])]), md=3),
                    dbc.Col(dbc.Card([dbc.CardBody([html.H6("History Points"), html.H4(id="history-count")])]), md=3),
                ])
            ], style={"marginTop":"18px"})
        ], className="content")
    ])

# ===================== 3D MODEL =====================
def model3d_layout():
    return html.Div([sidebar,
        html.Div([
            html.H3("3D Visualization"),
            html.Video(src="/assets/Simulation.mp4", controls=True, style={"width":"100%","marginTop":"12px"})
        ], className="content")
    ])

# ===================== HISTORY =====================
def history_layout():
    table_header = [html.Thead(html.Tr([html.Th("Timestamp"), html.Th("Temp (°C)"), html.Th("Speed (RPM)"), html.Th("Vibration mean"), html.Th("Acoustic mean")]))]
    rows = [html.Tr([html.Td(h["timestamp"]), html.Td(h["temperature"]), html.Td(h["speed"]), html.Td(round(h["vibration"],3)), html.Td(round(h["acoustic"],3))]) for h in sensor_data["history"][-200:][::-1]]
    table_body = [html.Tbody(rows)]
    return html.Div([sidebar, html.Div([html.H3("Sensor History"),
        dbc.Button("Download CSV", id="download-csv", color="primary"),
        html.Table(table_header + table_body, className="table table-striped mt-3")], className="content")])

# ===================== ADMIN =====================
def admin_layout():
    pending_list = [html.Div([html.Span(f"{u['username']}", style={"flex":"1"}),
                               dbc.Button("Approve", color="success", size="sm", className="mx-1", id={"type":"approve-user","index":u['username']}),
                               dbc.Button("Reject", color="danger", size="sm", id={"type":"reject-user","index":u['username']})
                              ], className="pending-user") for u in PENDING_USERS]
    approved_list = [html.Div([html.Span(u['username'])]) for u in APPROVED_USERS]
    rejected_list = [html.Div([html.Span(u['username'])]) for u in REJECTED_USERS]
    return html.Div([sidebar, html.Div([
        html.H3("Settings"),
        html.H5("Pending Accounts"), html.Div(pending_list, id="pending-users-list"),
        html.Hr(), html.H5("Approved Accounts"), html.Div(approved_list, id="approved-users-list"),
        html.Hr(), html.H5("Rejected Accounts"), html.Div(rejected_list, id="rejected-users-list")
    ], className="content")])

# ===================== AI CHAT (MODIFIÉ) =====================
chat_history = []

def ai_layout():
    return html.Div([sidebar,
        html.Div([
            html.H3("ChatBot"),
            html.Div(id="chat-container", style={
                "border": "1px solid #ccc",
                "borderRadius": "8px",
                "padding": "10px",
                "height": "400px",
                "overflowY": "auto",
                "background": "#f9f9f9"
            }),
            dbc.Textarea(id="ai-input", placeholder="Posez une question...", style={"width":"100%","marginTop":"10px","height":"80px"}),
            dbc.Button("Send", id="ai-send", color="primary", className="mt-2"),
            dcc.Interval(id="scroll-interval", interval=50, n_intervals=0)
        ], className="content")
    ])

@app.callback(
    Output("chat-container", "children"),
    Input("ai-send", "n_clicks"),
    State("ai-input", "value"),
    prevent_initial_call=True
)
def ai_chat(n_clicks, question):
    global chat_history
    if not question or question.strip() == "":
        return chat_history

    chat_history.append(html.Div([
        html.Div(question, style={
            "background": "#2c3e50", "color": "white",
            "padding": "8px 12px", "borderRadius": "12px",
            "display": "inline-block", "maxWidth": "80%", "marginLeft": "auto"
        })
    ], style={"marginBottom": "6px", "display": "flex"}))

    current_vib = sensor_data["vibration"][-1] if sensor_data["vibration"] else 0
    context = f"Tu es un assistant industriel. Données actuelles: Temp={sensor_data['temperature']:.1f}°C, Vitesse={sensor_data['speed']:.0f} RPM, Vibration={current_vib:.2f}. "
    
    # MODIFICATION 2: Gestion robuste de l'IA (Modèle + Erreur Quota)
    try:
        response = model_gemini.generate_content(context + question)
        answer = response.text
    except Exception as e:
        if "429" in str(e):
            answer = "⚠️ Limite de requêtes atteinte. Veuillez patienter 60 secondes."
        else:
            answer = f"Erreur Gemini: {str(e)}"

    chat_history.append(html.Div([
        html.Div(answer, style={
            "background": "#3498db", "color": "white",
            "padding": "8px 12px", "borderRadius": "12px",
            "display": "inline-block", "maxWidth": "80%"
        })
    ], style={"marginBottom": "6px", "display": "flex"}))

    return chat_history

# ===================== NAVIGATION CALLBACK =====================
@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    if pathname == "/register": return register_layout
    elif pathname == "/admin": return admin_layout()
    elif pathname == "/dashboard": return dashboard_layout()
    elif pathname == "/history": return history_layout()
    elif pathname == "/3dmodel": return model3d_layout()
    elif pathname == "/ai": return ai_layout()
    return login_layout

# ===================== LOGIN CALLBACK =====================
@app.callback(
    Output("login-message", "children"),
    Output("url", "pathname"),
    Input("login-button", "n_clicks"),
    State("login-username", "value"),
    State("login-password", "value"),
    prevent_initial_call=True
)
def login(n_clicks, username, password):
    if not username or not password: return "⚠️ Please fill in all fields.", no_update
    if username in [u["username"] for u in REJECTED_USERS]: return "⛔ Your account has been rejected.", no_update
    if any(u["username"] == username for u in PENDING_USERS): return "⏳ Account pending approval.", no_update
    if username in USERS and USERS[username] == password:
        return "", "/admin" if username=="admin" else "/dashboard"
    return "Incorrect username or password.", no_update

# ===================== DASHBOARD UPDATE & ALERTS =====================
@app.callback(
    [
        Output("gauge-temp","figure"),
        Output("gauge-speed","figure"),
        Output("graph-vibration","figure"),
        Output("graph-acoustic","figure"),
        Output("last-temp","children"),
        Output("last-speed","children"),
        Output("history-count","children"),
        Output("alert-container", "children") 
    ],
    Input("update-interval","n_intervals")
)
def update_dashboard(n):
    simulate_sensor_data()
    record_history()

    alerts = []
    if sensor_data["temperature"] > THRESHOLD_TEMP:
        alerts.append(dbc.Alert(f"🚨 ALERTE: Température élevée ({sensor_data['temperature']:.1f}°C)", color="danger", dismissable=True))
    if sensor_data["speed"] > THRESHOLD_SPEED:
        alerts.append(dbc.Alert(f"⚠️ ALERTE: Survitesse ({sensor_data['speed']:.0f} RPM)", color="warning", dismissable=True))
    
    current_vib = sensor_data["vibration"][-1] if sensor_data["vibration"] else 0
    if current_vib > THRESHOLD_VIB:
        alerts.append(dbc.Alert(f"📉 ALERTE: Vibration critique ({current_vib:.2f})", color="danger", dismissable=True))

    fig_temp = go.Figure(go.Indicator(
        mode="gauge+number", value=sensor_data["temperature"],
        gauge={"axis": {"range": [0,100]}, "bar": {"color": "#27ae60"},
               "steps":[{"range":[0,40],"color":"#2ecc71"},{"range":[40,70],"color":"#f1c40f"},{"range":[70,100],"color":"#e74c3c"}]}))
    fig_temp.update_layout(margin=dict(l=10,r=10,t=25,b=40))

    fig_speed = go.Figure(go.Indicator(
        mode="gauge+number", value=sensor_data["speed"],
        gauge={"axis": {"range":[0,3000]}, "bar":{"color":"#3498db"},
               "steps":[{"range":[0,1000],"color":"#85c1e9"},{"range":[1000,2000],"color":"#f1c40f"},{"range":[2000,3000],"color":"#e74c3c"}]}))
    fig_speed.update_layout(margin=dict(l=10,r=10,t=25,b=40))

    fig_vib = go.Figure(go.Scatter(y=sensor_data["vibration"][-50:], mode="lines", line=dict(color="#27ae60")))
    fig_vib.update_layout(title="Vibration", margin=dict(l=10,r=10,t=30,b=10))

    fig_acou = go.Figure(go.Scatter(y=sensor_data["acoustic"][-50:], mode="lines", line=dict(color="#e67e22")))
    fig_acou.update_layout(title="Acoustic", margin=dict(l=10,r=10,t=30,b=10))

    return fig_temp, fig_speed, fig_vib, fig_acou, f"{sensor_data['temperature']:.1f} °C", f"{sensor_data['speed']:.0f} RPM", f"{len(sensor_data['history'])}", alerts

# ===================== CSV DOWNLOAD =====================
@app.callback(
    Output("download-csv", "href"),
    Input("download-csv", "n_clicks"),
    prevent_initial_call=True
)
def download_csv(n):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["timestamp","temperature","speed","vibration","acoustic"])
    writer.writeheader()
    writer.writerows(sensor_data["history"])
    return "data:text/csv;charset=utf-8," + output.getvalue()

# ===================== MAIN =====================
if __name__ == "__main__":
    # MODIFICATION 3: Port dynamique pour Render/Cloud
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)