from flask import Flask, request, jsonify, session, render_template_string
import os, random, hashlib, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from supabase import create_client, Client

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.secret_key = os.environ.get('SECRET_KEY', 'ff-tournament-secret-2025')

ADMIN_EMAIL    = 'valdotankou11@gmail.com'
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '22joelva010708')

# ══════════════════════════════════════════════
#  Supabase client
# ══════════════════════════════════════════════

def get_sb() -> Client:
    url = os.environ.get('SUPABASE_URL', 'https://gaeakeqcyrwaklecztap.supabase.co')
    key = os.environ.get('SUPABASE_KEY', 'sb_secret_1ghJ65gQEKet3FrANJRryQ_H_F_-1pk')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL et SUPABASE_KEY doivent être définis')
    return create_client(url, key)

# ══════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def safe_player(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != 'password'}

# ══════════════════════════════════════════════
#  Email
# ══════════════════════════════════════════════

def send_email(to_list: list, subject: str, html: str) -> bool:
    host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    port = int(os.environ.get('SMTP_PORT', 587))
    user = os.environ.get('SMTP_USER', 'valdotankou11@gmail.com')
    pw   = os.environ.get('SMTP_PASS', '2667 6648 0909 1566')
    if not user:
        print('[EMAIL] SMTP non configuré')
        return False
    try:
        msg            = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = user
        msg['To']      = ', '.join(to_list)
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(host, port) as s:
            s.ehlo(); s.starttls(); s.login(user, pw)
            s.sendmail(user, to_list, msg.as_string())
        return True
    except Exception as e:
        print(f'[EMAIL] Erreur: {e}')
        return False


def email_new_registration(player: dict):
    subject = f"🎮 Nouvelle inscription — {player['pseudo']}"
    rows = ''.join(
        f"<tr style='border-bottom:1px solid #1e1e1e'>"
        f"<td style='padding:10px 8px;color:#888;width:140px'>{k}</td>"
        f"<td style='padding:10px 8px;color:#fff;font-weight:600'>{v}</td></tr>"
        for k, v in [
            ('Pseudo FF', player['pseudo']),
            ('ID Free Fire', player['ff_id']),
            ('Email', player['email']),
            ('WhatsApp', player['whatsapp']),
            ('Date', datetime.now().strftime('%d/%m/%Y à %H:%M')),
        ]
    )
    html = f"""
    <div style="font-family:Arial;background:#0f0f0f;color:#f0f0f0;padding:28px;
                border-radius:12px;max-width:520px;border:1px solid #2a2a2a">
      <div style="border-bottom:2px solid #f5a623;padding-bottom:12px;margin-bottom:20px">
        <h2 style="margin:0;color:#f5a623">🔥 Tournoi Free Fire</h2>
        <p style="margin:4px 0 0;color:#888;font-size:13px">Nouvelle inscription reçue</p>
      </div>
      <table style="width:100%;border-collapse:collapse">{rows}</table>
    </div>"""
    send_email([ADMIN_EMAIL], subject, html)


def email_group_assigned(player: dict, group_name: str, members: list):
    rivals = ''.join(
        f"<li style='padding:8px 0;border-bottom:1px solid #1e1e1e'>"
        f"<span style='color:#f5a623;font-weight:700'>{m['pseudo']}</span>"
        f"<span style='color:#666;font-size:12px;margin-left:10px'>ID: {m['ff_id']}</span></li>"
        for m in members if m['email'] != player['email']
    )
    subject = f"🏆 Ton groupe : {group_name} — Tournoi Free Fire"
    html = f"""
    <div style="font-family:Arial;background:#0f0f0f;color:#f0f0f0;padding:28px;
                border-radius:12px;max-width:520px;border:1px solid #2a2a2a">
      <h2 style="color:#f5a623;margin:0 0 4px">🔥 TOURNOI FREE FIRE</h2>
      <p style="color:#888;font-size:13px;margin:0 0 20px">Tirage au sort des poules</p>
      <p>Salut <strong style="color:#f5a623">{player['pseudo']}</strong> !</p>
      <p style="font-size:18px">Tu es dans le <strong style="color:#fff">{group_name}</strong> 🎯</p>
      <div style="background:#1a1a1a;border-radius:8px;padding:16px;margin-top:16px">
        <h3 style="color:#f5a623;margin:0 0 12px;font-size:13px;letter-spacing:2px">TES ADVERSAIRES</h3>
        <ul style="list-style:none;padding:0;margin:0">{rivals}</ul>
      </div>
      <p style="color:#555;font-size:12px;margin-top:20px;text-align:center">
        Connecte-toi sur le site pour suivre les scores en temps réel.
      </p>
    </div>"""
    send_email([player['email']], subject, html)


def email_score_updated(player: dict, score: int, group_name: str):
    subject = f"📊 Ton score mis à jour — {group_name}"
    html = f"""
    <div style="font-family:Arial;background:#0f0f0f;color:#f0f0f0;padding:28px;
                border-radius:12px;max-width:480px;border:1px solid #2a2a2a">
      <h2 style="color:#f5a623;margin:0 0 16px">📊 Score mis à jour</h2>
      <p>Salut <strong style="color:#f5a623">{player['pseudo']}</strong> !</p>
      <p>Ton score dans le <strong>{group_name}</strong> a été mis à jour.</p>
      <div style="text-align:center;padding:24px;background:#1a1a1a;border-radius:8px;margin:16px 0">
        <div style="font-size:52px;font-weight:900;color:#f5a623">{score}</div>
        <div style="color:#888;font-size:12px;letter-spacing:3px">POINTS</div>
      </div>
      <p style="color:#555;font-size:12px;text-align:center">
        Connecte-toi pour voir ton classement dans ta poule.
      </p>
    </div>"""
    send_email([player['email']], subject, html)

# ══════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════

@app.route('/')
def index():
    tpl = os.path.join(BASE_DIR, 'templates', 'index.html')
    return render_template_string(open(tpl).read())

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
            return jsonify({'error': 'Cet email est déjà utilisé'}), 400

        if sb.table('players').select('id').eq('ff_id', ff_id).execute().data:
            return jsonify({'error': 'Cet ID Free Fire est déjà enregistré'}), 400

        t_row = (sb.table('tournaments')
                   .select('*')
                   .in_('status', ['open', 'in_progress'])
                   .order('created_at', desc=True).limit(1).execute())
        if t_row.data:
            cnt = sb.table('players').select('id', count='exact').execute()
            if (cnt.count or 0) >= t_row.data[0]['max_players']:
                return jsonify({'error': 'Le tournoi est complet !'}), 400

        res = sb.table('players').insert({
            'pseudo': pseudo, 'ff_id': ff_id, 'email': email,
            'whatsapp': whatsapp, 'password': hash_pw(password),
            'group_name': None, 'score': 0,
        }).execute()

        player = res.data[0]
        session['user_email'] = email
        session['is_admin']   = False

        try: email_new_registration(player)
        except Exception: pass

        return jsonify({'success': True, 'player': safe_player(player)})

    except Exception as e:
        print(f'[REGISTER] {e}')
        return jsonify({'error': 'Erreur serveur, réessayez'}), 500


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
        return jsonify({'success': True, 'is_admin': False, 'player': safe_player(player)})
    except Exception as e:
        print(f'[LOGIN] {e}')
        return jsonify({'error': 'Erreur serveur'}), 500


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
        return jsonify({'logged_in': True, 'is_admin': False, 'player': safe_player(res.data[0])})
    except Exception:
        return jsonify({'logged_in': False})

# ── TOURNAMENT ────────────────────────────────

@app.route('/api/tournament', methods=['GET'])
def get_tournament():
    try:
        sb    = get_sb()
        t_row = (sb.table('tournaments').select('*')
                   .neq('status', 'archived')
                   .order('created_at', desc=True).limit(1).execute())
        cnt   = sb.table('players').select('id', count='exact').execute()
        return jsonify({'tournament': t_row.data[0] if t_row.data else None,
                        'players_count': cnt.count or 0})
    except Exception as e:
        print(f'[GET_TOURNAMENT] {e}')
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
        t_row = (sb.table('tournaments').select('id')
                   .neq('status', 'archived')
                   .order('created_at', desc=True).limit(1).execute())
        if not t_row.data:
            return jsonify({'error': 'Aucun tournoi actif'}), 404
        allowed = {'name', 'date', 'max_players', 'players_per_group',
                   'prize_1', 'prize_2', 'prize_3', 'status'}
        update  = {k: v for k, v in body.items() if k in allowed}
        sb.table('tournaments').update(update).eq('id', t_row.data[0]['id']).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tournament/draw', methods=['POST'])
def draw_groups():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        sb    = get_sb()
        t_row = (sb.table('tournaments').select('*')
                   .neq('status', 'archived')
                   .order('created_at', desc=True).limit(1).execute())
        if not t_row.data:
            return jsonify({'error': 'Aucun tournoi actif'}), 400
        t = t_row.data[0]

        players = sb.table('players').select('*').execute().data
        if not players:
            return jsonify({'error': 'Aucun joueur inscrit'}), 400

        sb.table('players').update({'group_name': None}).execute()
        random.shuffle(players)
        ppg        = t['players_per_group']
        letters    = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        groups_map = {}

        for i, player in enumerate(players):
            gi    = i // ppg
            gname = f"Groupe {letters[gi]}"
            groups_map.setdefault(gname, []).append(player)
            sb.table('players').update({'group_name': gname}).eq('id', player['id']).execute()

        sb.table('tournaments').update({'status': 'in_progress'}).eq('id', t['id']).execute()

        for gname, members in groups_map.items():
            for p in members:
                try: email_group_assigned(p, gname, members)
                except Exception: pass

        return jsonify({'success': True, 'groups_created': list(groups_map.keys())})
    except Exception as e:
        print(f'[DRAW] {e}')
        return jsonify({'error': str(e)}), 500

# ── GROUPS ────────────────────────────────────

@app.route('/api/groups', methods=['GET'])
def get_groups():
    try:
        sb  = get_sb()
        res = sb.table('players').select('pseudo,ff_id,email,group_name,score').execute()
        groups: dict = {}
        for p in res.data:
            gname = p.get('group_name')
            if not gname:
                continue
            groups.setdefault(gname, []).append({
                'pseudo': p['pseudo'], 'ff_id': p['ff_id'],
                'email': p['email'],   'score': p.get('score') or 0,
            })
        for g in groups:
            groups[g].sort(key=lambda x: x['score'], reverse=True)
        ordered = {k: {'members': v} for k, v in sorted(groups.items())}
        return jsonify({'groups': ordered})
    except Exception as e:
        print(f'[GET_GROUPS] {e}')
        return jsonify({'groups': {}})

# ── SCORES ────────────────────────────────────

@app.route('/api/score', methods=['POST'])
def set_score():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    body  = request.json or {}
    email = body.get('email', '').strip().lower()
    score = int(body.get('score', 0))
    if not email:
        return jsonify({'error': 'Email requis'}), 400
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
        except Exception: pass
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── PLAYERS (admin) ───────────────────────────

@app.route('/api/players', methods=['GET'])
def get_players():
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        sb  = get_sb()
        res = (sb.table('players')
                 .select('pseudo,ff_id,email,whatsapp,group_name,score,created_at')
                 .order('created_at', desc=False).execute())
        return jsonify({'players': res.data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/players/<path:player_email>', methods=['DELETE'])
def delete_player(player_email):
    if not session.get('is_admin'):
        return jsonify({'error': 'Non autorisé'}), 403
    try:
        sb = get_sb()
        sb.table('players').delete().eq('email', player_email).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── LEADERBOARD (public) ──────────────────────

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        sb  = get_sb()
        res = (sb.table('players')
                 .select('pseudo,ff_id,group_name,score')
                 .not_.is_('group_name', 'null')
                 .order('score', desc=True).limit(20).execute())
        return jsonify({'leaderboard': res.data})
    except Exception:
        return jsonify({'leaderboard': []})


if __name__ == '__main__':
    app.run(debug=True)
