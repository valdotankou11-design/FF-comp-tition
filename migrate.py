#!/usr/bin/env python3
"""
migrate.py — Migration FF-comp-tition (Supabase) → FF Tournoi v3 (Vercel KV)

Usage :
  1. pip install supabase requests
  2. Remplis les variables ci-dessous (ou exporte-les en env)
  3. python migrate.py
"""

import os, json, hashlib, urllib.request

# ══════════════════════════════════════════════
#  🔧 CONFIGURATION — à remplir
# ══════════════════════════════════════════════

# ── Supabase (FF-comp-tition) ──
SUPABASE_URL   = os.environ.get("OLD_SUPABASE_URL",   "https://gaeakeqcyrwaklecztap.supabase.co/rest/v1/")
SUPABASE_KEY   = os.environ.get("OLD_SUPABASE_KEY",   "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdhZWFrZXFjeXJ3YWtsZWN6dGFwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODkzMzI2NSwiZXhwIjoyMDk0NTA5MjY1fQ.N97NlsoT3vtRZQZz8n5EuMoh6m_2a8lN7cfifB8RaLU")   # anon ou service_role key
# ── Vercel KV (FF Tournoi v3) ──
KV_REST_API_URL   = os.environ.get("KV_REST_API_URL",   "https://XXXX.kv.vercel-storage.com")
KV_REST_API_TOKEN = os.environ.get("KV_REST_API_TOKEN", "XXXX")

# ══════════════════════════════════════════════
#  Supabase — lecture de la table players
# ══════════════════════════════════════════════

def fetch_supabase_players():
    url = f"{SUPABASE_URL}/rest/v1/players?select=*"
    req = urllib.request.Request(url, headers={
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

# ══════════════════════════════════════════════
#  Vercel KV — écriture
# ══════════════════════════════════════════════

def kv_request(method, path, body=None):
    url  = f"{KV_REST_API_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {KV_REST_API_TOKEN}",
        "Content-Type":  "application/json",
    }, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

def kv_get(key):
    try:
        res = kv_request("GET", f"/get/{key}")
        raw = res.get("result")
        if raw is None:
            return None
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None

def kv_set(key, value):
    kv_request("POST", "/set", [key, json.dumps(value)])

# ══════════════════════════════════════════════
#  Mapping des colonnes Supabase → format KV
#
#  Adapte ce mapping si tes colonnes ont
#  des noms différents dans Supabase.
# ══════════════════════════════════════════════

FIELD_MAP = {
    # Supabase column  →  KV field
    "pseudo":         "pseudo",
    "ff_id":          "ff_id",
    "email":          "email",
    "whatsapp":       "whatsapp",
    "password":       "password",       # déjà hashé SHA-256 ? sinon voir ci-dessous
    "group":          "group",
    "score":          "score",
    "registered_at":  "registered_at",
    # Aliases courants
    "username":       "pseudo",
    "game_id":        "ff_id",
    "phone":          "whatsapp",
    "groupe":         "group",
    "created_at":     "registered_at",
}

def map_player(row):
    """Convertit une ligne Supabase vers le format attendu par ff-v2-new."""
    p = {
        "pseudo":        "",
        "ff_id":         "",
        "email":         "",
        "whatsapp":      "",
        "password":      hashlib.sha256(b"changeme").hexdigest(),  # mot de passe temporaire
        "group":         None,
        "score":         0,
        "registered_at": "",
    }
    for src_key, val in row.items():
        dst_key = FIELD_MAP.get(src_key)
        if dst_key:
            p[dst_key] = val

    # Normalise l'email en minuscules
    p["email"] = (p["email"] or "").strip().lower()

    # Si le mot de passe n'est pas hashé (< 64 chars), on le hashe
    pw = p.get("password") or ""
    if pw and len(pw) != 64:
        p["password"] = hashlib.sha256(pw.encode()).hexdigest()

    # Score : s'assure que c'est un int
    try:
        p["score"] = int(p.get("score") or 0)
    except (ValueError, TypeError):
        p["score"] = 0

    return p

# ══════════════════════════════════════════════
#  Migration principale
# ══════════════════════════════════════════════

def migrate():
    print("=" * 55)
    print("  Migration FF-comp-tition → FF Tournoi v3")
    print("=" * 55)

    # 1. Récupère les joueurs depuis Supabase
    print("\n📥 Lecture de Supabase...")
    try:
        rows = fetch_supabase_players()
    except Exception as e:
        print(f"  ❌ Impossible de lire Supabase : {e}")
        print("     → Vérifie SUPABASE_URL et SUPABASE_KEY")
        return

    print(f"  ✓ {len(rows)} joueur(s) trouvé(s)")

    if not rows:
        print("  ℹ️  Aucun joueur à migrer. Terminé.")
        return

    # 2. Charge les joueurs déjà dans le KV (pour ne pas écraser)
    print("\n📦 Lecture du Vercel KV existant...")
    existing = kv_get("players") or {}
    print(f"  ✓ {len(existing)} joueur(s) déjà dans KV")

    # 3. Fusion
    added    = 0
    skipped  = 0
    errors   = []

    for row in rows:
        try:
            p = map_player(row)

            if not p["email"]:
                errors.append(f"Ligne sans email ignorée : {row}")
                continue

            if p["email"] in existing:
                print(f"  ⏭️  {p['pseudo']} ({p['email']}) — déjà présent, ignoré")
                skipped += 1
                continue

            existing[p["email"]] = p
            print(f"  ➕ {p['pseudo']} ({p['email']}) — ajouté")
            added += 1

        except Exception as e:
            errors.append(f"Erreur sur ligne {row}: {e}")

    # 4. Sauvegarde dans KV
    if added > 0:
        print(f"\n💾 Sauvegarde de {len(existing)} joueur(s) dans Vercel KV...")
        try:
            kv_set("players", existing)
            print("  ✓ Sauvegarde réussie")
        except Exception as e:
            print(f"  ❌ Erreur KV : {e}")
            return
    else:
        print("\n  ℹ️  Aucun nouveau joueur à ajouter.")

    # 5. Rapport
    print("\n" + "=" * 55)
    print(f"  ✅ Migration terminée")
    print(f"     Ajoutés  : {added}")
    print(f"     Ignorés  : {skipped} (déjà présents)")
    print(f"     Erreurs  : {len(errors)}")
    if errors:
        print("\n  ⚠️  Détail des erreurs :")
        for err in errors:
            print(f"     - {err}")
    print("=" * 55)
    print()
    print("  ⚠️  Mot de passe temporaire : 'changeme'")
    print("     Les joueurs migrés devront le réinitialiser.")
    print("     (Tu peux personnaliser le mot de passe dans FIELD_MAP)")
    print()

if __name__ == "__main__":
    migrate()
