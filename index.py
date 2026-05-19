from flask import Flask, request, jsonify, session
import os, random, hashlib, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ff-secret-2025')

ADMIN_EMAIL    = 'valdo.soh@facsciences-uy1.com'
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin1234')

# ══════════════════════════════════════════════
#  Supabase
# ══════════════════════════════════════════════
def get_sb() -> Client:
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_KEY', '')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL / SUPABASE_KEY manquants')
    return create_client(url, key)

# ══════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def safe(p):     return {k: v for k, v in p.items() if k != 'password'}

# ══════════════════════════════════════════════
#  Email
# ══════════════════════════════════════════════
def send_email(to_list, subject, html):
    host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    port = int(os.environ.get('SMTP_PORT', 587))
    user = os.environ.get('SMTP_USER', '')
    pw   = os.environ.get('SMTP_PASS', '')
    if not user: return False
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
        f"<tr><td style='padding:8px;color:#888'>{k}</td>"
        f"<td style='padding:8px;color:#fff;font-weight:600'>{v}</td></tr>"
        for k, v in [('Pseudo FF', p['pseudo']), ('ID FF', p['ff_id']),
                     ('Email', p['email']), ('WhatsApp', p['whatsapp'])])
    send_email([ADMIN_EMAIL], f"🎮 Inscription — {p['pseudo']}",
        f"<div style='font-family:Arial;background:#111;padding:24px;border-radius:10px;color:#fff'>"
        f"<h2 style='color:#f5a623'>🔥 Nouvelle inscription</h2><table>{rows}</table></div>")

def email_group_assigned(player, group_name, members):
    rivals = ''.join(
        f"<li style='padding:6px 0'><b style='color:#f5a623'>{m['pseudo']}</b> — ID: {m['ff_id']}</li>"
        for m in members if m['email'] != player['email'])
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
        f"<p>Ton score dans le <b>{group_name}</b> : "
        f"<span style='font-size:32px;color:#f5a623;font-weight:900'>{score} pts</span></p></div>")

# ══════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '3.0'})

# ── AUTH ──────────────────────────────────────

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
    try:
        sb = get_sb()
        if sb.table('players').select('id').eq('email', email).execute().data:
            return jsonify({'error': 'Email déjà utilisé'}), 400
        if sb.table('players').select('id').eq('ff_id', ff_id).execute().data:
            return jsonify({'error': 'ID Free Fire déjà enregistré'}), 400
        t_row = sb.table('tournaments').select('*').in_('status', ['open', 'in_progress']).order('created_at', desc=True).limit(1).execute()
        if t_row.data:
            cnt = sb.table('players').select('id', count='exact').execute()
            if (cnt.count or 0) >= t_row.data[0]['max_players']:
                return jsonify({'error': 'Le tournoi est complet !'}), 400
        res = sb.table('players').insert({
            'pseudo': pseudo, 'ff_id': ff_id, 'email': email,
            'whatsapp': whatsapp, 'password': hash_pw(password),
            'group_name': None, 'score': 0
        }).execute()
        player = res.data[0]
        session['user_email'] = email
        session['is_admin']   = False
        try: email_new_registration(player)
        except: pass
        return jsonify({'success': True, 'player': safe(player)})
    except Exception as e:
        print(f'[REGISTER] {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    body     = request.json or {}
    email    = body.get('email', '').strip().lower()
    password = body.get('password', '')
    if email == 'admin' and password == ADMIN_PASSWORD:
        session['user_email'] = 'admin'
        session['is_admin']   = True
        return jsonify({'success': True, 'is_admin': True})
    try:
        sb  = get_sb()
        res = sb.table('players').select('*').eq('email', email).execute()
        if not res.data or res.data[0]['password'] != hash_pw(password):
            return jsonify({'error': 'Email ou mot de passe incorrect'}), 401
        player = res.data[0]
        session['user_email'] = email
        session['is_admin']   = False
        return jsonify({'success': True, 'is_admin': False, 'player': safe(player)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    try:
        sb  = get_sb()
        res = sb.table('players').select('*').eq('email', session['user_email']).execute()
        if not res.data:
            session.clear()
            return jsonify({'logged_in': False})
        return jsonify({'logged_in': True, 'is_admin': False, 'player': safe(res.data[0])})
    except:
        return jsonify({'logged_in': False})

# ── TOURNAMENT ────────────────────────────────

@app.route('/api/tournament', methods=['GET'])
def get_tournament():
    try:
        sb    = get_sb()
        t_row = sb.table('tournaments').select('*').neq('status', 'archived').order('created_at', desc=True).limit(1).execute()
        cnt   = sb.table('players').select('id', count='exact').execute()
        return jsonify({'tournament': t_row.data[0] if t_row.data else None, 'players_count': cnt.count or 0})
    except Exception as e:
        return jsonify({'tournament': None, 'players_count': 0})

@app.route('/api/tournament', methods=['POST'])
def create_tournament():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    body = request.json or {}
    try:
        sb = get_sb()
        sb.table('tournaments').update({'status': 'archived'}).neq('status', 'archived').execute()
        sb.table('players').update({'group_name': None, 'score': 0}).execute()
        res = sb.table('tournaments').insert({
            'name':              body.get('name', 'Tournoi Free Fire'),
            'date':              body.get('date') or None,
            'max_players':       int(body.get('max_players', 16)),
            'players_per_group': int(body.get('players_per_group', 4)),
            'prize_1':           body.get('prize_1', '600 Diamants'),
            'prize_2':           body.get('prize_2', '220 Diamants'),
            'prize_3':           body.get('prize_3', '110 Diamants'),
            'status':            'open',
        }).execute()
        return jsonify({'success': True, 'tournament': res.data[0]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tournament', methods=['PATCH'])
def update_tournament():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    body = request.json or {}
    try:
        sb    = get_sb()
        t_row = sb.table('tournaments').select('id').neq('status', 'archived').order('created_at', desc=True).limit(1).execute()
        if not t_row.data:
            return jsonify({'error': 'Aucun tournoi actif'}), 404
        allowed = {'name', 'date', 'max_players', 'players_per_group', 'prize_1', 'prize_2', 'prize_3', 'status'}
        sb.table('tournaments').update({k: v for k, v in body.items() if k in allowed}).eq('id', t_row.data[0]['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tournament/draw', methods=['POST'])
def draw_groups():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        sb    = get_sb()
        t_row = sb.table('tournaments').select('*').neq('status', 'archived').order('created_at', desc=True).limit(1).execute()
        if not t_row.data:
            return jsonify({'error': 'Aucun tournoi actif'}), 400
        t       = t_row.data[0]
        players = sb.table('players').select('*').execute().data
        if not players:
            return jsonify({'error': 'Aucun joueur inscrit'}), 400
        sb.table('players').update({'group_name': None}).execute()
        random.shuffle(players)
        ppg        = t['players_per_group']
        groups_map = {}
        letters    = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        for i, player in enumerate(players):
            gname = f"Groupe {letters[i // ppg]}"
            groups_map.setdefault(gname, []).append(player)
            sb.table('players').update({'group_name': gname}).eq('id', player['id']).execute()
        sb.table('tournaments').update({'status': 'in_progress'}).eq('id', t['id']).execute()
        for gname, members in groups_map.items():
            for p in members:
                try: email_group_assigned(p, gname, members)
                except: pass
        return jsonify({'success': True, 'groups_created': list(groups_map.keys())})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── GROUPS ────────────────────────────────────

@app.route('/api/groups')
def get_groups():
    try:
        sb  = get_sb()
        res = sb.table('players').select('pseudo,ff_id,email,group_name,score').execute()
        groups = {}
        for p in res.data:
            gname = p.get('group_name')
            if not gname: continue
            groups.setdefault(gname, []).append({
                'pseudo': p['pseudo'], 'ff_id': p['ff_id'],
                'email': p['email'],   'score': p.get('score') or 0
            })
        for g in groups:
            groups[g].sort(key=lambda x: x['score'], reverse=True)
        return jsonify({'groups': {k: {'members': v} for k, v in sorted(groups.items())}})
    except:
        return jsonify({'groups': {}})

# ── SCORES ────────────────────────────────────

@app.route('/api/score', methods=['POST'])
def set_score():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    body  = request.json or {}
    email = body.get('email', '').strip().lower()
    score = int(body.get('score', 0))
    try:
        sb  = get_sb()
        res = sb.table('players').select('*').eq('email', email).execute()
        if not res.data:
            return jsonify({'error': 'Joueur introuvable'}), 404
        player = res.data[0]
        sb.table('players').update({'score': score}).eq('email', email).execute()
        try:
            if player.get('group_name'):
                email_score_updated(player, score, player['group_name'])
        except: pass
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── PLAYERS ──────────────────────────────────

@app.route('/api/players')
def get_players():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        sb  = get_sb()
        res = sb.table('players').select('pseudo,ff_id,email,whatsapp,group_name,score,created_at').order('created_at').execute()
        return jsonify({'players': res.data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/players/<path:player_email>', methods=['DELETE'])
def delete_player(player_email):
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        get_sb().table('players').delete().eq('email', player_email).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        sb  = get_sb()
        res = sb.table('players').select('pseudo,ff_id,group_name,score').not_.is_('group_name', 'null').order('score', desc=True).limit(20).execute()
        return jsonify({'leaderboard': res.data})
    except:
        return jsonify({'leaderboard': []})
