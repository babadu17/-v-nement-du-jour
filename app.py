from flask import *
from datetime import datetime
import json
import sqlite3
import webbrowser
import os
import psycopg2

app = Flask(__name__)
DB_URL = "postgres://avnadmin:AVNS__GlfxlePDxDk14ehlKA@pg-368b4833-bastianbary17-5fbd.e.aivencloud.com:18969/defaultdb?sslmode=require"  # Obligatoire pour flash
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
    user_registered = request.cookies.get('user_registered')
    ip = get_ip()
    print(f"[INFO] IP détectée : {ip}")
    
    if not user_registered:
        return redirect('/inscription')
    
    # Met à jour le nombre de visites et la date de dernière visite
    if ip != "127.0.0.1":  # on ignore les visites locales
        try:
            conn = get_connection()
            cur = conn.cursor()

            # Met à jour le compteur sans créer de doublon (PostgreSQL)
            cur.execute("""
                INSERT INTO visiteurs (nom, prenom, ip, nb_visites)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (ip)
                DO UPDATE SET 
                    nb_visites = visiteurs.nb_visites + 1,
                    date_derniere_visite = CURRENT_TIMESTAMP;
            """, ("", "", ip))  # nom et prénom vides si déjà connus

            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print("⚠️ Erreur mise à jour visites :", e)

    # Date du jour (jour et mois)
    today = datetime.now().strftime("%d-%m")

    # Charger les événements depuis events.json
    with open("events.json", "r", encoding="utf-8") as f:
       events = json.load(f)

    # Récupérer les événements correspondants à la date du jour
    todays_events = events.get(today, ["Aucun événement pour aujourd'hui"])
    return render_template("index.html", events=todays_events, aujourdhui=today)

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

    # 💡 Étape 1 : afficher ton IP dans la console la première fois
    print(f"[ADMIN PAGE] Accès tenté depuis IP : {ip}")

    # 💡 Étape 2 : une fois ton IP connue
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
    if request.method == "POST":
        nom = request.form.get("nom")
        prenom = request.form.get("prenom")
        ip = get_ip()

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO visiteurs (nom, prenom, ip, nb_visites, date_derniere_visite)
                VALUES (%s, %s, %s, 1, CURRENT_TIMESTAMP)
            """, (nom, prenom, ip))
            conn.commit()
            cur.close()
            conn.close()

            resp = make_response(redirect("/"))
            resp.set_cookie('user_registered', 'yes', max_age=60*60*24*365)
            return resp

        except Exception as e:
            print("⚠️ Erreur inscription visiteur :", e)
            flash("⚠️ Une erreur est survenue lors de l'inscription. Veuillez réessayer.", "error")
            return redirect("/inscription")

    return render_template("inscription.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
