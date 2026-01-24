from flask import *
from datetime import datetime
import json
import sqlite3
import webbrowser
import os
import psycopg2

app = Flask(__name__)
DB_URL = "postgres://avnadmin:AVNS__GlfxlePDxDk14ehlKA@pg-368b4833-bastianbary17-5fbd.e.aivencloud.com:18969/defaultdb?sslmode=require"
app.secret_key = "une_cle_secrete"

def get_connection():
    return psycopg2.connect(DB_URL)

def get_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if "," in ip:
        ip = ip.split(",")[0].strip()
    return ip.strip()


@app.route("/")
def home():
    ip = get_ip()
    print(f"[INFO] IP détectée : {ip}")
    
    # Vérifier si l'utilisateur est inscrit en base de données
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT nom, prenom FROM visiteurs WHERE ip = %s", (ip,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()
        
        # Si pas d'utilisateur OU nom/prénom vides → rediriger vers inscription
        if not user_data or not user_data[0] or not user_data[1]:
            print(f"[INFO] Utilisateur non inscrit ou incomplet pour IP {ip} - Redirection")
            return redirect('/inscription')
        
        print(f"[INFO] Utilisateur trouvé : {user_data[1]} {user_data[0]}")
        
    except Exception as e:
        print(f"[ERREUR] Vérification utilisateur : {e}")
        return redirect('/inscription')
    
    # Mettre à jour le nombre de visites
    if ip != "127.0.0.1":
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE visiteurs 
                SET nb_visites = nb_visites + 1,
                    date_derniere_visite = CURRENT_TIMESTAMP
                WHERE ip = %s
            """, (ip,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print("⚠️ Erreur mise à jour visites :", e)

    # Date du jour (jour et mois)
    today_key = datetime.now().strftime("%d-%m")  # Format pour chercher dans events.json (ex: "16-12")
    
    # Date formatée pour l'affichage (ex: "16 décembre")
    mois_francais = {
        "01": "janvier", "02": "février", "03": "mars", "04": "avril",
        "05": "mai", "06": "juin", "07": "juillet", "08": "août",
        "09": "septembre", "10": "octobre", "11": "novembre", "12": "décembre"
    }
    jour = datetime.now().strftime("%d").lstrip("0")  # Enlève le 0 devant (ex: "16" au lieu de "16")
    mois_num = datetime.now().strftime("%m")
    mois = mois_francais.get(mois_num, "")
    today_display = f"{jour} {mois}"  # Ex: "16 décembre"

    # Charger les événements depuis events.json
    with open("events.json", "r", encoding="utf-8") as f:
       events = json.load(f)

    # Récupérer les événements correspondants à la date du jour
    todays_events = events.get(today_key, ["Aucun événement pour aujourd'hui"])
    return render_template("index.html", events=todays_events, aujourdhui=today_display)

@app.route("/enregistrer_avis", methods=["POST"])
def enregistrer_avis():
    avis = request.form.get("avis")
    note = request.form.get("note")
    ip = get_ip()

    if avis or note:
        contenu = f"{note} étoiles : {avis}"

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO avis (texte, utilisateur_ip) VALUES (%s, %s)", (contenu,ip))
        conn.commit()
        conn.close()

        flash("✅ Votre avis a bien été enregistré !", "success")

    return redirect("/")

@app.route("/avis")
def afficher_avis():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.texte, v.nom, v.prenom
        FROM avis a
        LEFT JOIN visiteurs v
        ON a.utilisateur_ip = v.ip
        ORDER BY a.id DESC
    """)
    data = cur.fetchall()
    conn.close()
    
    return render_template("avis.html", avis_list=data)

@app.route("/reset_avis")
def reset_avis():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE avis RESTART IDENTITY;")
        conn.commit()
        conn.close()
        flash("✅ Tous les avis ont été supprimés avec succès !")
    except Exception as e:
        flash(f"⚠️ Erreur : {e}")
    return redirect("/avis")

@app.route('/statistiques_visiteurs')
def statistiques_visiteurs():
    ip = get_ip()

    print(f"[ADMIN PAGE] Accès tenté depuis IP : {ip}")

    TON_ADRESSE_IP = "127.0.0.1"

    #if ip != TON_ADRESSE_IP:
        #return "⛔ Accès refusé", 403

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT nom, prenom, ip, nb_visites, date_derniere_visite
            FROM visiteurs
            ORDER BY date_derniere_visite DESC
        """)
        visiteurs = cur.fetchall()

        cur.execute("SELECT AVG(nb_visites) FROM visiteurs")
        moyenne = cur.fetchone()[0]
        conn.close()

        return render_template('admin_visiteurs.html', visiteurs=visiteurs, moyenne=moyenne)

    except Exception as e:
        print("⚠️ Erreur chargement admin :", e)
        return "Erreur lors du chargement des visiteurs", 500

@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    print(f"[INSCRIPTION] Méthode : {request.method}")
    
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        ip = get_ip()
        
        print(f"[INSCRIPTION] Tentative : nom='{nom}', prenom='{prenom}', ip={ip}")

        # Vérifier que nom et prénom sont bien remplis
        if not nom or not prenom or len(nom) < 2 or len(prenom) < 2:
            flash("⚠️ Veuillez renseigner votre nom ET prénom (minimum 2 caractères).", "error")
            return redirect("/inscription")

        try:
            conn = get_connection()
            cur = conn.cursor()
            
            # Insérer ou mettre à jour l'utilisateur
            cur.execute("""
                INSERT INTO visiteurs (nom, prenom, ip, nb_visites, date_derniere_visite)
                VALUES (%s, %s, %s, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (ip)
                DO UPDATE SET
                    nom = EXCLUDED.nom,
                    prenom = EXCLUDED.prenom,
                    date_derniere_visite = CURRENT_TIMESTAMP;
            """, (nom, prenom, ip))
            conn.commit()
            
            print(f"[INSCRIPTION] ✅ Inscription réussie pour {prenom} {nom}")
            
            cur.close()
            conn.close()

            # Rediriger vers la page d'accueil
            flash(f"✅ Bienvenue {prenom} {nom} !", "success")
            return redirect("/")

        except Exception as e:
            print(f"[INSCRIPTION] ❌ Erreur : {e}")
            flash("⚠️ Une erreur est survenue lors de l'inscription. Veuillez réessayer. Et me le signaler par message au 07 87 33 84 32", "error")
            return redirect("/inscription")

    return render_template("inscription.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
