from flask import Flask, request, jsonify, session, Response
import os, random, hashlib, smtplib, base64, json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ff-secret-2025')

ADMIN_EMAIL    = os.environ.get('ADMIN_EMAIL', 'valdo.soh@facsciences-uy1.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin1234')

# ══════════════════════════════════════════════
#  HTML (embarqué depuis le fichier statique)
# ══════════════════════════════════════════════

_HTML_PATH = os.path.join(os.path.dirname(__file__), '..', 'public', 'index.html')

def get_html():
    with open(_HTML_PATH, 'r', encoding='utf-8') as f:
        return f.read()

# ══════════════════════════════════════════════
#  Vercel KV (Redis) — couche de données
#  Toutes les données sont stockées dans Redis
#  via l'API REST officielle de Vercel KV.
#
#  Variables d'environnement nécessaires :
#    KV_REST_API_URL   → URL de votre KV store
#    KV_REST_API_TOKEN → Token d'accès
# ══════════════════════════════════════════════

import urllib.request

def _kv_url():
    return os.environ.get('KV_REST_API_URL', '').rstrip('/')

def _kv_token():
    return os.environ.get('KV_REST_API_TOKEN', '')

def _kv_request(method, path, body=None):
    url = f"{_kv_url()}{path}"
    headers = {
        'Authorization': f'Bearer {_kv_token()}',
        'Content-Type': 'application/json',
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def kv_get(key):
    """Retourne la valeur (déjà parsée) ou None."""
    try:
        result = _kv_request('GET', f'/get/{key}')
        raw = result.get('result')
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return raw
        return raw
    except Exception as e:
        print(f'[KV GET {key}] {e}')
        return None

def kv_set(key, value):
    """Stocke value (sérialisé en JSON string)."""
    try:
        _kv_request('POST', '/set', [key, json.dumps(value)])
        return True
    except Exception as e:
        print(f'[KV SET {key}] {e}')
        return False

def kv_del(key):
    try:
        _kv_request('POST', '/del', [key])
        return True
    except Exception as e:
        print(f'[KV DEL {key}] {e}')
        return False

# ── Helpers KV ──

def get_players():
    return kv_get('players') or {}

def set_players(data):
    return kv_set('players', data)

def get_tournament():
    return kv_get('tournament')

def set_tournament(data):
    return kv_set('tournament', data)

def del_tournament():
    return kv_del('tournament')

# ══════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def safe(p):
    return {k: v for k, v in p.items() if k != 'password'}

# ══════════════════════════════════════════════
#  Email
# ══════════════════════════════════════════════

def send_email(to_list, subject, html):
    host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    port = int(os.environ.get('SMTP_PORT', 587))
    user = os.environ.get('SMTP_USER', '')
    pw   = os.environ.get('SMTP_PASS', '')
    if not user:
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = user
        msg['To']      = ', '.join(to_list)
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(host, port) as s:
            s.ehlo(); s.starttls(); s.login(user, pw)
            s.sendmail(user, to_list, msg.as_string())
        return True
    except Exception as e:
        print(f'[EMAIL] {e}')
        return False

def email_new_registration(p):
    rows = ''.join(
        f"<tr><td style='padding:8px;color:#888'>{k}</td><td style='padding:8px;color:#fff;font-weight:600'>{v}</td></tr>"
        for k, v in [('Pseudo FF', p['pseudo']), ('ID FF', p['ff_id']), ('Email', p['email']), ('WhatsApp', p['whatsapp'])]
    )
    send_email([ADMIN_EMAIL], f"🎮 Inscription — {p['pseudo']}",
        f"<div style='font-family:Arial;background:#111;padding:24px;border-radius:10px;color:#fff'>"
        f"<h2 style='color:#f5a623'>🔥 Nouvelle inscription</h2><table>{rows}</table></div>")

def email_group_assigned(player, group_name, members):
    rivals = ''.join(
        f"<li style='padding:6px 0'><b style='color:#f5a623'>{m['pseudo']}</b> — ID: {m['ff_id']}</li>"
        for m in members if m['email'] != player['email']
    )
    send_email([player['email']], f"🏆 Ton groupe : {group_name}",
        f"<div style='font-family:Arial;background:#111;padding:24px;border-radius:10px;color:#fff'>"
        f"<h2 style='color:#f5a623'>🔥 TOURNOI FREE FIRE</h2>"
        f"<p>Salut <b style='color:#f5a623'>{player['pseudo']}</b> ! Tu es dans le <b>{group_name}</b> 🎯</p>"
        f"<h3 style='color:#f5a623'>Tes adversaires</h3><ul style='list-style:none;padding:0'>{rivals}</ul></div>")

def email_score_updated(player, score, group_name):
    send_email([player['email']], f"📊 Score mis à jour — {group_name}",
        f"<div style='font-family:Arial;background:#111;padding:24px;border-radius:10px;color:#fff'>"
        f"<h2 style='color:#f5a623'>📊 Score mis à jour</h2>"
        f"<p>Salut <b style='color:#f5a623'>{player['pseudo']}</b> !</p>"
        f"<p>Ton score dans le <b>{group_name}</b> : <span style='font-size:32px;color:#f5a623;font-weight:900'>{score} pts</span></p></div>")

# ══════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════

@app.route('/')
def index():
    return Response(get_html(), mimetype='text/html')

@app.route('/manifest.json')
def manifest():
    m = {
        "name": "FF Tournoi",
        "short_name": "FF Tournoi",
        "description": "Tournoi Free Fire — inscriptions, poules et scores",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0a0a0a",
        "theme_color": "#f5a623",
        "orientation": "portrait-primary",
        "icons": [
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
        ]
    }
    return Response(json.dumps(m), mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    sw = """
const CACHE = 'ff-tournoi-v1';
const PRECACHE = ['/'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // API toujours en réseau
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(fetch(e.request));
    return;
  }
  // Pages : réseau d'abord, cache en fallback
  e.respondWith(
    fetch(e.request)
      .then(resp => {
        if (resp && resp.status === 200) {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});
"""
    return Response(sw, mimetype='application/javascript')

# ── AUTH ──

@app.route('/api/register', methods=['POST'])
def register():
    body     = request.json or {}
    pseudo   = body.get('pseudo', '').strip()
    ff_id    = body.get('ff_id', '').strip()
    email    = body.get('email', '').strip().lower()
    whatsapp = body.get('whatsapp', '').strip()
    password = body.get('password', '')

    if not all([pseudo, ff_id, email, whatsapp, password]):
        return jsonify({'error': 'Tous les champs sont requis'}), 400

    players = get_players()

    if email in players:
        return jsonify({'error': 'Email déjà utilisé'}), 400
    if any(p['ff_id'] == ff_id for p in players.values()):
        return jsonify({'error': 'ID Free Fire déjà enregistré'}), 400

    t = get_tournament()
    if t and t.get('status') in ('open', 'in_progress'):
        if len(players) >= t.get('max_players', 16):
            return jsonify({'error': 'Le tournoi est complet !'}), 400

    player = {
        'pseudo':        pseudo,
        'ff_id':         ff_id,
        'email':         email,
        'whatsapp':      whatsapp,
        'password':      hash_pw(password),
        'group':         None,
        'score':         0,
        'registered_at': datetime.utcnow().isoformat(),
    }
    players[email] = player
    set_players(players)

    session['user_email'] = email
    session['is_admin']   = False

    try:
        email_new_registration(player)
    except Exception:
        pass

    return jsonify({'success': True, 'player': safe(player)})

@app.route('/api/login', methods=['POST'])
def login():
    body     = request.json or {}
    email    = body.get('email', '').strip().lower()
    password = body.get('password', '')

    if email == 'admin' and password == ADMIN_PASSWORD:
        session['user_email'] = 'admin'
        session['is_admin']   = True
        return jsonify({'success': True, 'is_admin': True})

    players = get_players()
    player  = players.get(email)
    if not player or player['password'] != hash_pw(password):
        return jsonify({'error': 'Email ou mot de passe incorrect'}), 401

    session['user_email'] = email
    session['is_admin']   = False
    return jsonify({'success': True, 'is_admin': False, 'player': safe(player)})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/me')
def me():
    if 'user_email' not in session:
        return jsonify({'logged_in': False})
    if session.get('is_admin'):
        return jsonify({'logged_in': True, 'is_admin': True})
    players = get_players()
    email   = session['user_email']
    player  = players.get(email)
    if not player:
        session.clear()
        return jsonify({'logged_in': False})
    return jsonify({'logged_in': True, 'is_admin': False, 'player': safe(player)})

# ── TOURNAMENT ──

@app.route('/api/tournament', methods=['GET'])
def get_tournament_route():
    t       = get_tournament()
    players = get_players()
    return jsonify({'tournament': t, 'players_count': len(players)})

@app.route('/api/tournament', methods=['POST'])
def create_tournament():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    body = request.json or {}
    # Réinitialise les groupes des joueurs existants
    players = get_players()
    for email in players:
        players[email]['group'] = None
        players[email]['score'] = 0
    set_players(players)

    t = {
        'name':             body.get('name', 'Tournoi Free Fire'),
        'date':             body.get('date') or None,
        'max_players':      int(body.get('max_players', 16)),
        'players_per_group': int(body.get('players_per_group', 4)),
        'prize_1':          body.get('prize_1', '600 Diamants'),
        'prize_2':          body.get('prize_2', '220 Diamants'),
        'prize_3':          body.get('prize_3', '110 Diamants'),
        'status':           'open',
        'created_at':       datetime.utcnow().isoformat(),
    }
    set_tournament(t)
    return jsonify({'success': True, 'tournament': t})

@app.route('/api/tournament', methods=['DELETE'])
def delete_tournament():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    t = get_tournament()
    if not t:
        return jsonify({'error': 'Aucun tournoi actif'}), 404
    players = get_players()
    for email in players:
        players[email]['group'] = None
        players[email]['score'] = 0
    set_players(players)
    del_tournament()
    return jsonify({'success': True})

@app.route('/api/tournament/draw', methods=['POST'])
def draw_groups():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    t = get_tournament()
    if not t:
        return jsonify({'error': 'Aucun tournoi actif'}), 400

    players = get_players()
    if not players:
        return jsonify({'error': 'Aucun joueur inscrit'}), 400

    player_list = list(players.values())
    random.shuffle(player_list)

    ppg     = t.get('players_per_group', 4)
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    groups_map = {}

    for i, player in enumerate(player_list):
        gname = f"Groupe {letters[i // ppg]}"
        groups_map.setdefault(gname, []).append(player)
        players[player['email']]['group'] = gname

    set_players(players)

    t['status'] = 'in_progress'
    set_tournament(t)

    for gname, members in groups_map.items():
        for p in members:
            try:
                email_group_assigned(p, gname, members)
            except Exception:
                pass

    return jsonify({'success': True, 'groups_created': list(groups_map.keys())})

# ── GROUPS ──

@app.route('/api/groups')
def get_groups():
    players = get_players()
    groups  = {}
    for p in players.values():
        gname = p.get('group')
        if not gname:
            continue
        groups.setdefault(gname, []).append({
            'pseudo': p['pseudo'],
            'ff_id':  p['ff_id'],
            'email':  p['email'],
            'score':  p.get('score') or 0,
        })
    for g in groups:
        groups[g].sort(key=lambda x: x['score'], reverse=True)
    return jsonify({'groups': {k: {'members': v} for k, v in sorted(groups.items())}})

# ── SCORES ──

@app.route('/api/score', methods=['POST'])
def set_score():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    body  = request.json or {}
    email = body.get('email', '').strip().lower()
    score = int(body.get('score', 0))

    players = get_players()
    if email not in players:
        return jsonify({'error': 'Joueur introuvable'}), 404

    players[email]['score'] = score
    set_players(players)

    try:
        p = players[email]
        if p.get('group'):
            email_score_updated(p, score, p['group'])
    except Exception:
        pass

    return jsonify({'success': True})

# ── PLAYERS ──

@app.route('/api/players')
def get_players_route():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    players = get_players()
    result  = sorted(
        [safe(p) for p in players.values()],
        key=lambda x: x.get('registered_at', '')
    )
    # Renommage group → group pour le front
    for p in result:
        p['group'] = p.get('group')
    return jsonify({'players': result})

@app.route('/api/players/<path:player_email>', methods=['DELETE'])
def delete_player(player_email):
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    players = get_players()
    if player_email in players:
        del players[player_email]
        set_players(players)
    return jsonify({'success': True})

@app.route('/api/stats')
def get_stats():
    players = get_players()
    lb = sorted(
        [{'pseudo': p['pseudo'], 'ff_id': p['ff_id'], 'group': p.get('group'), 'score': p.get('score', 0)}
         for p in players.values() if p.get('group')],
        key=lambda x: x['score'], reverse=True
    )[:20]
    return jsonify({'leaderboard': lb})

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '3.0', 'storage': 'vercel-kv'})

# ══════════════════════════════════════════════
#  MATCHS — Round-robin par poule
# ══════════════════════════════════════════════

def get_matches():
    return kv_get('matches') or {}

def set_matches(data):
    return kv_set('matches', data)

def generate_round_robin(members):
    """Génère tous les matchs (combinaisons C(n,2)) pour une liste de joueurs."""
    matches = []
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            matches.append({
                'p1': members[i]['email'],
                'p1_pseudo': members[i]['pseudo'],
                'p2': members[j]['email'],
                'p2_pseudo': members[j]['pseudo'],
                'score_p1': None,
                'score_p2': None,
                'played': False,
            })
    return matches

@app.route('/api/matches', methods=['GET'])
def get_matches_route():
    return jsonify({'matches': get_matches()})

@app.route('/api/matches/generate', methods=['POST'])
def generate_matches():
    """Génère les matchs après le tirage des poules."""
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403

    players = get_players()
    groups  = {}
    for p in players.values():
        gname = p.get('group')
        if gname:
            groups.setdefault(gname, []).append(p)

    if not groups:
        return jsonify({'error': 'Aucune poule définie. Lance d\'abord le tirage.'}), 400

    matches = {}
    for gname, members in groups.items():
        matches[gname] = generate_round_robin(members)

    set_matches(matches)
    total = sum(len(v) for v in matches.values())
    return jsonify({'success': True, 'total_matches': total, 'matches': matches})

@app.route('/api/matches/score', methods=['PATCH'])
def update_match_score():
    """Met à jour le score d'un match et recalcule les points de poule."""
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403

    body      = request.json or {}
    group     = body.get('group', '')
    match_idx = int(body.get('match_idx', -1))
    score_p1  = body.get('score_p1')
    score_p2  = body.get('score_p2')

    matches = get_matches()
    if group not in matches or match_idx < 0 or match_idx >= len(matches[group]):
        return jsonify({'error': 'Match introuvable'}), 404

    m = matches[group][match_idx]
    m['score_p1'] = score_p1
    m['score_p2'] = score_p2
    m['played']   = (score_p1 is not None and score_p2 is not None)

    set_matches(matches)

    # Recalcule le score global de chaque joueur dans la poule
    # Règle : victoire = 3 pts, nul = 1 pt, défaite = 0 pt
    players = get_players()
    tally   = {}  # email → points de poule

    for match in matches[group]:
        if not match['played']:
            continue
        s1 = match['score_p1']
        s2 = match['score_p2']
        e1 = match['p1']
        e2 = match['p2']
        tally.setdefault(e1, 0)
        tally.setdefault(e2, 0)
        if s1 > s2:
            tally[e1] += 3
        elif s2 > s1:
            tally[e2] += 3
        else:
            tally[e1] += 1
            tally[e2] += 1

    for email, pts in tally.items():
        if email in players:
            players[email]['score'] = pts

    set_players(players)
    return jsonify({'success': True, 'matches': matches[group]})

@app.route('/api/matches/reset', methods=['DELETE'])
def reset_matches():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    kv_del('matches')
    return jsonify({'success': True})
