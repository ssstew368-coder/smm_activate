from telethon import TelegramClient, events
import asyncio
import os
import time
import re
import json
from datetime import datetime
from instagrapi import Client
from instagrapi.exceptions import ClientError, ClientLoginRequired
import random
import logging
import sys
import select
import collections
import uuid
# -- imports ajoutés pour le système de licence (pas de doublons) --
import requests
import hashlib
from email.utils import parsedate_to_datetime

# ================================================================
#  BLOC LICENCE
# ================================================================

_GITHUB_TOKEN = "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"   # ← Ton token GitHub ici
_GITHUB_USER  = "ssstew368-coder"
_GITHUB_REPO  = "license_smm"

_KEY_FILE   = ".smm_key"
_CACHE_FILE = ".smm_lic"
_CACHE_TTL  = 88400  # 24h


def _get_machine_id():
    return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:16]


def _get_server_time():
    """Heure réelle depuis GitHub — non falsifiable par le client."""
    resp = requests.get(
        "https://api.github.com",
        headers={"Authorization": f"token {_GITHUB_TOKEN}"},
        timeout=10
    )
    date_str = resp.headers.get("Date")
    return parsedate_to_datetime(date_str).replace(tzinfo=None)


def _check_github(license_key, machine_id):
    url = (
        f"https://api.github.com/repos/{_GITHUB_USER}/{_GITHUB_REPO}"
        f"/contents/{license_key}.json"
    )
    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": f"token {_GITHUB_TOKEN}",
                "Accept":        "application/vnd.github.v3.raw",
            },
            timeout=10
        )
    except requests.exceptions.ConnectionError:
        return None, "Pas de connexion"

    if resp.status_code == 404:
        return False, "Clé de licence inconnue"
    if resp.status_code != 200:
        return None, f"Serveur inaccessible (code {resp.status_code})"

    try:
        lic = json.loads(resp.text)
    except json.JSONDecodeError:
        return None, "Réponse invalide du serveur"

    if not lic.get("active", False):
        return False, "Abonnement suspendu — contactez l'administrateur"

    try:
        now     = _get_server_time()
        expires = datetime.fromisoformat(lic["expires"])
    except Exception:
        return None, "Erreur lecture date d'expiration"

    if now > expires:
        jours = (now - expires).days
        return False, f"Abonnement expiré depuis {jours} jour(s) — renouvelez votre abonnement"

    stored_machine = lic.get("machine_id")
    if stored_machine is None:
        print("\n" + "=" * 55)
        print("  ⚠️  PREMIÈRE ACTIVATION REQUISE")
        print("=" * 55)
        print(f"\n  Votre Machine ID : {machine_id}")
        print("\n  Envoyez ce code à l'administrateur")
        print("  pour finaliser l'activation de votre licence.\n")
        print("=" * 55 + "\n")
        sys.exit(0)

    if stored_machine != machine_id:
        return False, "Machine non autorisée — contactez l'administrateur"

    jours_restants = (expires - now).days
    return True, (expires.isoformat(), jours_restants)


def _load_cache(license_key, machine_id):
    if not os.path.exists(_CACHE_FILE):
        return False
    try:
        with open(_CACHE_FILE, "r") as f:
            cache = json.load(f)
        if cache.get("key") != license_key:
            return False
        if cache.get("machine_id") != machine_id:
            return False
        if time.time() - cache.get("timestamp", 0) > _CACHE_TTL:
            return False
        if datetime.now() > datetime.fromisoformat(cache.get("expires", "2000-01-01")):
            return False
        return True
    except Exception:
        return False


def _save_cache(license_key, machine_id, expires_iso):
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump({
                "key":        license_key,
                "machine_id": machine_id,
                "expires":    expires_iso,
                "timestamp":  time.time(),
            }, f)
    except Exception:
        pass


def _verify():
    machine_id = _get_machine_id()

    # Charger la clé sauvegardée ou la demander
    license_key = ""
    if os.path.exists(_KEY_FILE):
        try:
            with open(_KEY_FILE, "r") as f:
                license_key = f.read().strip()
        except Exception:
            license_key = ""

    if not license_key:
        print("\n🔑 Entrez votre clé de licence : ", end="")
        license_key = input().strip()
        if not license_key:
            print("❌ Clé vide — arrêt.")
            sys.exit(1)

    print("🔄 Vérification de la licence...", end=" ", flush=True)

    valid, result = _check_github(license_key, machine_id)

    if valid is True:
        expires_iso, jours_restants = result
        _save_cache(license_key, machine_id, expires_iso)
        try:
            with open(_KEY_FILE, "w") as f:
                f.write(license_key)
        except Exception:
            pass
        if jours_restants <= 7:
            print(f"✅ Valide — ⚠️  expire dans {jours_restants} jour(s) !")
        else:
            print(f"✅ Valide — expire dans {jours_restants} jour(s)")
        return

    if valid is False:
        print(f"\n\n❌ Accès refusé — {result}\n")
        sys.exit(1)

    # GitHub inaccessible → essayer le cache
    print("⚠️  GitHub inaccessible")
    print("🔄 Vérification du cache local...", end=" ", flush=True)
    if _load_cache(license_key, machine_id):
        print("✅ Cache valide — démarrage hors ligne")
        return

    print("\n\n❌ Pas de cache valide.")
    print("   Une connexion internet est requise pour le premier lancement.\n")
    sys.exit(1)

# ================================================================
#  FIN BLOC LICENCE
# ================================================================

# ================= FICHIER DE CONFIGURATION EXTERNE =================

# ===== USER AGENTS =====
INSTAGRAM_USER_AGENTS = {
    "samsung_s21": "Instagram 312.0.0.30.111 Android (33/13; 420dpi; 1080x2340; samsung; SM-G991B; o1s; exynos2100; fr_FR; 544477369)",
    "oneplus_9": "Instagram 311.0.0.40.120 Android (32/12; 480dpi; 1080x2400; OnePlus; LE2123; OnePlus9Pro; qcom; fr_FR; 543661450)",
    "xiaomi_mi11": "Instagram 310.0.0.50.115 Android (31/12; 440dpi; 1080x2340; Xiaomi; M2102J20SG; venus; qcom; fr_FR; 542850432)",
    "pixel_7": "Instagram 309.0.0.30.105 Android (33/13; 420dpi; 1080x2400; Google; Pixel 7; panther; tensor; fr_FR; 541922301)"
}

CONFIG_FILE = "smm_config_second.json"  # Fichier différent pour éviter conflit

def load_config():
    """Charge la configuration depuis un fichier JSON externe"""
    if not os.path.exists(CONFIG_FILE):
        # Configuration par défaut si le fichier n'existe pas
        default_config = {
            "instagram_accounts": {
                "bifsteak58": {
                    "username": "bifsteak58",
                    "password": "enfoire58"
                },
                "bifsteak57": {
                    "username": "bifsteak57",
                    "password": "enfoire57"
                },
                "bifsteak56": {
                    "username": "bifsteak56",
                    "password": "enfoire56"
                }
            },
            "api_id": 30930720,
            "api_hash": "b17b4f5712c32e64e3e2772871e3589c",
            "phone": "+261341318531",
            "bot_id": "@SmmKingdomTasksBot",
            "force_relog": [],  # Par défaut comme dans ton script
            "cashcoin_values": {
                "like": 0.5,
                "follow": 1.25,
                "video": 0.5  # Ajout pour la nouvelle tâche vidéo
            },
            "enabled_tasks": {
                "like": True,
                "follow": True,
                "video": True  # Ajout pour la nouvelle tâche vidéo
            },
            "mode": "normal",
            "current_user_agent": "samsung_s21"
        }
        save_config(default_config)
        return default_config
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erreur de chargement de la config: {e}")
        return None

def save_config(config):
    """Sauvegarde la configuration dans un fichier JSON"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"❌ Erreur de sauvegarde: {e}")
        return False

# ================= FICHIER DE LOGS =================
LOG_FILE = "smm_logs_second.json"

def load_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    return []

def save_logs(logs):
    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=4)

def reset_logs():
    save_logs([])

# ================= MONITEUR STATISTIQUES =================
class TaskMonitor:
    def __init__(self):
        self.reset_all()
    
    def reset_all(self):
        """Réinitialise toutes les stats"""
        self.total_tasks = 0
        self.likes_attempted = 0
        self.likes_success = 0
        self.follows_attempted = 0
        self.follows_success = 0
        self.videos_attempted = 0  # Ajout pour vidéo
        self.videos_success = 0    # Ajout pour vidéo
        self.failed_tasks = 0
        self.cashcoins = 0.0
        self.current_chain = 0
        self.max_chain = 0
        self.last_account = ""
        self.account_stats = {}
    
    def reset_current_account(self, account_name):
        """Réinitialise les stats pour un nouveau compte"""
        if account_name not in self.account_stats:
            self.account_stats[account_name] = {
                'tasks': 0,
                'likes_attempted': 0,
                'likes_success': 0,
                'follows_attempted': 0,
                'follows_success': 0,
                'videos_attempted': 0,  # Ajout pour vidéo
                'videos_success': 0,    # Ajout pour vidéo
                'failed': 0,
                'cashcoins': 0.0,
                'chains': 0,
                'likes_count': 0,
                'follows_count': 0,
                'videos_count': 0,      # Ajout pour vidéo
                'like_pause_until': 0,
                'follow_pause_until': 0,
                'video_pause_until': 0  # Ajout pour vidéo
            }
        self.last_account = account_name
    
    def add_task(self, task_type, success=True, cashcoins=0.0):
        """Ajoute une tâche traitée"""
        self.total_tasks += 1
        
        if task_type == 'like':
            self.likes_attempted += 1
            if success:
                self.likes_success += 1
                self.cashcoins += cashcoins
                
                if self.last_account in self.account_stats:
                    self.account_stats[self.last_account]['tasks'] += 1
                    self.account_stats[self.last_account]['likes_attempted'] += 1
                    self.account_stats[self.last_account]['likes_success'] += 1
                    self.account_stats[self.last_account]['cashcoins'] += cashcoins
            else:
                self.failed_tasks += 1
                if self.last_account in self.account_stats:
                    self.account_stats[self.last_account]['failed'] += 1
        
        elif task_type == 'follow':
            self.follows_attempted += 1
            if success:
                self.follows_success += 1
                self.cashcoins += cashcoins
                
                if self.last_account in self.account_stats:
                    self.account_stats[self.last_account]['tasks'] += 1
                    self.account_stats[self.last_account]['follows_attempted'] += 1
                    self.account_stats[self.last_account]['follows_success'] += 1
                    self.account_stats[self.last_account]['cashcoins'] += cashcoins
            else:
                self.failed_tasks += 1
                if self.last_account in self.account_stats:
                    self.account_stats[self.last_account]['failed'] += 1
        
        elif task_type == 'video':  # Ajout pour vidéo
            self.videos_attempted += 1
            if success:
                self.videos_success += 1
                self.cashcoins += cashcoins
                
                if self.last_account in self.account_stats:
                    self.account_stats[self.last_account]['tasks'] += 1
                    self.account_stats[self.last_account]['videos_attempted'] += 1
                    self.account_stats[self.last_account]['videos_success'] += 1
                    self.account_stats[self.last_account]['cashcoins'] += cashcoins
            else:
                self.failed_tasks += 1
                if self.last_account in self.account_stats:
                    self.account_stats[self.last_account]['failed'] += 1
        
        # Gestion des chaînes
        if success:
            self.current_chain += 1
            if self.current_chain > self.max_chain:
                self.max_chain = self.current_chain
        else:
            self.current_chain = 0
    
    def get_current_stats_display(self, current_account, current_tour, total_tours=15):
        """Retourne l'affichage du moniteur"""
        likes_display = f"{self.likes_success}/{self.likes_attempted}" if self.likes_attempted > 0 else "0/0"
        follows_display = f"{self.follows_success}/{self.follows_attempted}" if self.follows_attempted > 0 else "0/0"
        videos_display = f"{self.videos_success}/{self.videos_attempted}" if self.videos_attempted > 0 else "0/0"  # Ajout
        
        failed_str = "🚫 0"
        if self.account_stats:
            failed_accounts = [f"{acc[:8]}:{stats['failed']}" for acc, stats in self.account_stats.items() if stats.get('failed', 0) > 0]
            if failed_accounts:
                failed_str = "🚫 " + " ".join(failed_accounts)
                if len(failed_str) > 50:
                    failed_str = failed_str[:50] + "..."
        
        return (
            f"┌──────────────────────────────────────────────────────────┐\n"
            f"│ 📊 [{current_account[:10]:10}] | Tour: {current_tour:2d}/{total_tours} | 🔗 {self.current_chain:1d} │\n"
            f"│ ❤️ {likes_display:6} | 👥 {follows_display:6} | 📹 {videos_display:6} | 💰 {self.cashcoins:5.1f}cc │\n"
            f"│ {failed_str.ljust(56)} │\n"
            f"└──────────────────────────────────────────────────────────┘"
        )
    
    def get_account_performance(self, account_name):
        """Retourne les performances d'un compte spécifique"""
        if account_name not in self.account_stats:
            return "Aucune donnée"
        
        stats = self.account_stats[account_name]
        total_attempted = stats['likes_attempted'] + stats['follows_attempted'] + stats['videos_attempted']
        total_success = stats['likes_success'] + stats['follows_success'] + stats['videos_success']
        
        if total_attempted == 0:
            return "0% (0/0)"
        
        success_rate = (total_success / total_attempted) * 100
        return f"{success_rate:.0f}% ({total_success}/{total_attempted})"

# Variables globales
current_account_index = 0
tour_count = 0
task_found = False
security_check_detected = False  # Nouvelle variable pour détecter la vérification de sécurité

# Initialiser le moniteur
task_monitor = TaskMonitor()

# ================= SAFE TELEGRAM CLIENT (NOUVEAU - Anti-flood) =================
class SafeTelegramClient:
    """Wrapper autour du client Telegram avec cache et anti-flood"""
    
    def __init__(self, client):
        self.client = client
        self.cache = {}
        self.last_request_time = {}
        self.min_request_interval = 1.5  # Réduit de 3.0 à 1.5 secondes (juste un peu plus lent que 1.0)
        self.cache_ttl = 2.0  # Cache valide 2 secondes (au lieu de 3)
    
    async def get_messages_safe(self, entity, **kwargs):
        """Version safe de get_messages avec cache et anti-flood"""
        from telethon.errors import FloodWaitError
        
        # Créer une clé unique pour le cache
        cache_key = f"{entity}_{json.dumps(kwargs, sort_keys=True)}"
        current_time = time.time()
        
        # 1. Vérifier le cache
        if cache_key in self.cache:
            cached_data, cache_time = self.cache[cache_key]
            if current_time - cache_time < self.cache_ttl:
                return cached_data
        
        # 2. Respecter l'intervalle minimum entre requêtes
        if entity in self.last_request_time:
            time_since_last = current_time - self.last_request_time[entity]
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)
        
        # 3. Faire la requête avec catcher de flood
        retries = 3
        for attempt in range(retries):
            try:
                self.last_request_time[entity] = time.time()
                result = await self.client.get_messages(entity, **kwargs)
                
                # Mettre en cache
                self.cache[cache_key] = (result, time.time())
                return result
                
            except FloodWaitError as e:
                wait_time = e.seconds + 2  # +2 secondes de marge
                print(f"⏳ FloodWait: attente {wait_time}s (tentative {attempt+1}/{retries})")
                await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                print(f"⚠️ Erreur get_messages: {e}")
                if attempt == retries - 1:
                    return None
                await asyncio.sleep(2)
                continue
        
        return None
    
    async def send_message_safe(self, entity, message, **kwargs):
        """Version safe de send_message avec anti-flood"""
        from telethon.errors import FloodWaitError
        
        # Respecter l'intervalle minimum
        if entity in self.last_request_time:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time[entity]
            if time_since_last < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - time_since_last)
        
        # Faire la requête avec catcher de flood
        retries = 3
        for attempt in range(retries):
            try:
                self.last_request_time[entity] = time.time()
                result = await self.client.send_message(entity, message, **kwargs)
                return result
                
            except FloodWaitError as e:
                wait_time = e.seconds + 2
                print(f"⏳ FloodWait sur send_message: attente {wait_time}s")
                await asyncio.sleep(wait_time)
                continue
            except Exception as e:
                print(f"⚠️ Erreur send_message: {e}")
                if attempt == retries - 1:
                    return None
                await asyncio.sleep(2)
                continue
        
        return None
    
    def clear_cache(self, entity=None):
        """Vide le cache (optionnel)"""
        if entity:
            keys_to_delete = [k for k in self.cache.keys() if str(entity) in k]
            for key in keys_to_delete:
                del self.cache[key]
        else:
            self.cache.clear()

# Variables globales pour le safe client
safe_client = None

# ================= MENU PRINCIPAL ET INTERFACE =================
def clear_screen():
    """Efface l'écran du terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')

def manage_user_agent():
    config = load_config()
    if not config:
        return
    clear_screen()
    print("📱 USER AGENT")
    current = config.get("current_user_agent", "samsung_s21")
    print(f"Actuel: {current}")
    for i, k in enumerate(INSTAGRAM_USER_AGENTS.keys(), 1):
        print(f"{i}. {k}")
    c = input("Choix: ").strip()
    try:
        idx = int(c) - 1
        keys = list(INSTAGRAM_USER_AGENTS.keys())
        if 0 <= idx < len(keys):
            config["current_user_agent"] = keys[idx]
            save_config(config)
            print("✅ Changé")
    except:
        pass
    input("Entrée...")

def show_main_menu():
    """Affiche le menu principal interactif"""
    while True:
        clear_screen()
        print(f"{'='*60}")
        print("🤖 SMM BOT - COMPTE SECOND - MENU PRINCIPAL".center(60))
        print(f"{'='*60}")
        print("\n📋 Options disponibles :")
        print("  1. ▶️  Lancer le bot en mode automatique")
        print("  2. 📱 Gérer les comptes Instagram")
        print("  3. 🔄 Forcer la reconnexion d'un compte (force_relog)")
        print("  4. 📊 Afficher les statistiques actuelles")
        print("  5. ⚙️  Paramètres avancés")
        print("  6. Gérer l'activation des tâches")
        print("  7. Afficher le rapport de logs")
        print("  8. 🔄 Choisir le mode de fonctionnement")
        print("  9. 📱 User Agent")
        print("  0. 🚪 Quitter")
        print(f"{'='*60}")
        
        choix = input("\n👉 Votre choix [0-9] : ").strip()
        
        if choix == "1":
            return "run_bot"
        elif choix == "2":
            manage_instagram_accounts()
        elif choix == "3":
            manage_force_relog()
        elif choix == "4":
            show_current_stats()
        elif choix == "5":
            show_advanced_settings()
        elif choix == "6":
            manage_task_activations()
        elif choix == "7":
            show_log_report()
        elif choix == "8":
            manage_mode()
        elif choix == "9":
            manage_user_agent()
        elif choix == "0":
            print("\n👋 Au revoir !")
            exit(0)
        else:
            print("❌ Choix invalide. Appuyez sur Entrée...")
            input()

def manage_mode():
    config = load_config()
    if not config:
        print("❌ Impossible de charger la configuration")
        input("Appuyez sur Entrée...")
        return
    
    while True:
        clear_screen()
        print(f"{'='*60}")
        print("🔄 GESTION MODE DE FONCTIONNEMENT".center(60))
        print(f"{'='*60}")
        
        mode = config.get('mode', 'normal')
        
        print("\n📋 Mode actuel :")
        print(f"  • {'Lente et sûre' if mode == 'safe' else 'Normale'}")
        
        print("\n🔧 Options :")
        print("  1. Mode lente et sûre (25 likes max, 15 follows max par compte, pause 1h par action)")
        print("  2. Mode normale (sans limitation)")
        print("  0. Retour au menu principal")
        print(f"{'='*60}")
        
        choix = input("\n👉 Votre choix [0-2] : ").strip()
        
        if choix == "1":
            config['mode'] = 'safe'
            if save_config(config):
                print("✅ Mode mis à jour : lente et sûre")
        elif choix == "2":
            config['mode'] = 'normal'
            if save_config(config):
                print("✅ Mode mis à jour : normale")
        elif choix == "0":
            return
        else:
            print("❌ Choix invalide")
        
        input("Appuyez sur Entrée...")

def manage_task_activations():
    config = load_config()
    if not config:
        print("❌ Impossible de charger la configuration")
        input("Appuyez sur Entrée...")
        return
    
    while True:
        clear_screen()
        print(f"{'='*60}")
        print("⚙️ GESTION ACTIVATION TÂCHES".center(60))
        print(f"{'='*60}")
        
        enabled = config.get('enabled_tasks', {'like': True, 'follow': True, 'video': True})
        
        print("\n📋 Statut actuel :")
        print(f"  • Like : {'Activé' if enabled['like'] else 'Désactivé'}")
        print(f"  • Follow : {'Activé' if enabled['follow'] else 'Désactivé'}")
        print(f"  • Video : {'Activé' if enabled.get('video', True) else 'Désactivé'}")
        
        print("\n🔧 Options :")
        print("  1. Basculer Like")
        print("  2. Basculer Follow")
        print("  3. Basculer Video")
        print("  0. Retour au menu principal")
        print(f"{'='*60}")
        
        choix = input("\n👉 Votre choix [0-3] : ").strip()
        
        if choix == "1":
            enabled['like'] = not enabled['like']
            config['enabled_tasks'] = enabled
            if save_config(config):
                print("✅ Statut mis à jour")
        elif choix == "2":
            enabled['follow'] = not enabled['follow']
            config['enabled_tasks'] = enabled
            if save_config(config):
                print("✅ Statut mis à jour")
        elif choix == "3":
            enabled['video'] = not enabled.get('video', True)
            config['enabled_tasks'] = enabled
            if save_config(config):
                print("✅ Statut mis à jour")
        elif choix == "0":
            return
        else:
            print("❌ Choix invalide")
        
        input("Appuyez sur Entrée...")

def show_log_report():
    clear_screen()
    print(f"{'='*60}")
    print("📋 RAPPORT DE LOGS - DERNIÈRE SESSION".center(60))
    print(f"{'='*60}")
    
    logs = load_logs()
    if not logs:
        print("\n✅ Aucune erreur enregistrée dans la dernière session")
    else:
        print(f"\n📈 Total échecs: {len(logs)}")
        
        from collections import Counter
        account_fails = Counter(log['account'] for log in logs)
        print("\n📊 Échecs par compte:")
        for acc, count in account_fails.most_common():
            print(f"  • {acc}: {count}")
        
        print("\n🔍 Détails des erreurs:")
        for log in logs:
            print(f"  [{log['timestamp']}] {log['account']} - {log['task_type'].upper()}")
            print(f"    Raison: {log['reason']}")
            if 'link' in log:
                print(f"    Lien: {log['link']}")
            print()
    
    input("\n👈 Appuyez sur Entrée pour revenir...")

def manage_instagram_accounts():
    """Gestion des comptes Instagram"""
    config = load_config()
    if not config:
        print("❌ Impossible de charger la configuration")
        input("Appuyez sur Entrée...")
        return
    
    while True:
        clear_screen()
        print(f"{'='*60}")
        print("📱 GESTION DES COMPTES INSTAGRAM".center(60))
        print(f"{'='*60}")
        
        accounts = config.get('instagram_accounts', {})
        
        if not accounts:
            print("\n⚠️  Aucun compte configuré")
        else:
            print("\n📋 Comptes actuellement configurés :")
            for i, (telegram_user, creds) in enumerate(accounts.items(), 1):
                print(f"  {i}. {telegram_user}")
                print(f"     👤 Instagram: {creds.get('username', 'N/A')}")
                print(f"     🔐 Mot de passe: {'*' * len(creds.get('password', ''))}")
                print()
        
        print("\n🔧 Options :")
        print("  1. Ajouter un nouveau compte")
        print("  2. Modifier un compte existant")
        print("  3. Supprimer un compte")
        print("  0. Retour au menu principal")
        print(f"{'='*60}")
        
        choix = input("\n👉 Votre choix [0-3] : ").strip()
        
        if choix == "1":
            add_instagram_account(config)
        elif choix == "2":
            edit_instagram_account(config)
        elif choix == "3":
            delete_instagram_account(config)
        elif choix == "0":
            if save_config(config):
                print("✅ Configuration sauvegardée")
            input("Appuyez sur Entrée...")
            return
        else:
            print("❌ Choix invalide")
            input("Appuyez sur Entrée...")

def manage_force_relog():
    """Gestion de l'option force_relog"""
    config = load_config()
    if not config:
        print("❌ Impossible de charger la configuration")
        input("Appuyez sur Entrée...")
        return
    
    while True:
        clear_screen()
        print(f"{'='*60}")
        print("🔄 FORCE RELOG - RECONNEXION FORCÉE".center(60))
        print(f"{'='*60}")
        
        force_relog_list = config.get('force_relog', [])
        accounts = list(config.get('instagram_accounts', {}).keys())
        
        print("\n📋 Comptes Instagram disponibles :")
        for i, account in enumerate(accounts, 1):
            status = "✅ FORCÉ" if account in force_relog_list else "⚠️  Normal"
            print(f"  {i}. {account} - {status}")
        
        print("\n🔧 Options :")
        print("  1. Activer/désactiver force_relog pour un compte")
        print("  2. Tout désactiver (vider la liste)")
        print("  0. Retour au menu principal")
        print(f"{'='*60}")
        
        choix = input("\n👉 Votre choix [0-2] : ").strip()
        
        if choix == "1":
            print("\n👉 Entrez le numéro du compte à modifier :")
            try:
                num = int(input("Numéro : ").strip())
                if 1 <= num <= len(accounts):
                    account = accounts[num-1]
                    if account in force_relog_list:
                        config['force_relog'].remove(account)
                        print(f"✅ {account} retiré de force_relog")
                    else:
                        if 'force_relog' not in config:
                            config['force_relog'] = []
                        config['force_relog'].append(account)
                        print(f"✅ {account} ajouté à force_relog")
                    
                    save_config(config)
                else:
                    print("❌ Numéro invalide")
            except ValueError:
                print("❌ Veuillez entrer un numéro valide")
        
        elif choix == "2":
            config['force_relog'] = []
            save_config(config)
            print("✅ Liste force_relog vidée")
        
        elif choix == "0":
            return
        
        else:
            print("❌ Choix invalide")
        
        input("\nAppuyez sur Entrée...")

def add_instagram_account(config):
    """Ajoute un nouveau compte Instagram"""
    clear_screen()
    print(f"{'='*60}")
    print("➕ AJOUT D'UN NOUVEAU COMPTE".center(60))
    print(f"{'='*60}")
    
    telegram_user = input("\n👉 Nom du compte (pour Telegram) : ").strip()
    if not telegram_user:
        print("❌ Nom invalide")
        input("Appuyez sur Entrée...")
        return
    
    username = input("👉 Nom d'utilisateur Instagram : ").strip()
    password = input("👉 Mot de passe Instagram : ").strip()
    
    if not username or not password:
        print("❌ Identifiants invalides")
        input("Appuyez sur Entrée...")
        return
    
    if 'instagram_accounts' not in config:
        config['instagram_accounts'] = {}
    
    config['instagram_accounts'][telegram_user] = {
        'username': username,
        'password': password
    }
    
    if save_config(config):
        print(f"\n✅ Compte {telegram_user} ajouté avec succès !")
    
    input("Appuyez sur Entrée...")

def edit_instagram_account(config):
    """Modifie un compte Instagram existant"""
    accounts = list(config.get('instagram_accounts', {}).keys())
    
    if not accounts:
        print("❌ Aucun compte à modifier")
        input("Appuyez sur Entrée...")
        return
    
    clear_screen()
    print(f"{'='*60}")
    print("✏️  MODIFICATION D'UN COMPTE".center(60))
    print(f"{'='*60}")
    
    print("\n📋 Sélectionnez le compte à modifier :")
    for i, account in enumerate(accounts, 1):
        print(f"  {i}. {account}")
    
    try:
        num = int(input("\n👉 Numéro du compte : ").strip())
        if 1 <= num <= len(accounts):
            account = accounts[num-1]
            creds = config['instagram_accounts'][account]
            
            print(f"\n📝 Modification de {account}")
            print(f"   Ancien username: {creds['username']}")
            print(f"   Ancien password: {'*' * len(creds['password'])}")
            print("\n   Laissez vide pour ne pas modifier")
            
            new_username = input("   👉 Nouveau username : ").strip()
            new_password = input("   👉 Nouveau password : ").strip()
            
            if new_username:
                creds['username'] = new_username
            if new_password:
                creds['password'] = new_password
            
            if save_config(config):
                print(f"\n✅ Compte {account} modifié avec succès !")
        else:
            print("❌ Numéro invalide")
    except ValueError:
        print("❌ Veuillez entrer un numéro valide")
    
    input("Appuyez sur Entrée...")

def delete_instagram_account(config):
    """Supprime un compte Instagram"""
    accounts = list(config.get('instagram_accounts', {}).keys())
    
    if not accounts:
        print("❌ Aucun compte à supprimer")
        input("Appuyez sur Entrée...")
        return
    
    clear_screen()
    print(f"{'='*60}")
    print("🗑️  SUPPRESSION D'UN COMPTE".center(60))
    print(f"{'='*60}")
    
    print("\n📋 Sélectionnez le compte à supprimer :")
    for i, account in enumerate(accounts, 1):
        print(f"  {i}. {account}")
    
    try:
        num = int(input("\n👉 Numéro du compte : ").strip())
        if 1 <= num <= len(accounts):
            account = accounts[num-1]
            
            confirm = input(f"\n⚠️  Êtes-vous sûr de vouloir supprimer {account} ? (o/N) : ").strip().lower()
            if confirm == 'o' or confirm == 'oui':
                del config['instagram_accounts'][account]
                
                # Retirer aussi de force_relog si présent
                if account in config.get('force_relog', []):
                    config['force_relog'].remove(account)
                
                if save_config(config):
                    print(f"✅ Compte {account} supprimé avec succès !")
            else:
                print("❌ Suppression annulée")
        else:
            print("❌ Numéro invalide")
    except ValueError:
        print("❌ Veuillez entrer un numéro valide")
    
    input("Appuyez sur Entrée...")

def show_current_stats():
    """Affiche les statistiques actuelles"""
    clear_screen()
    print(f"{'='*60}")
    print("📊 STATISTIQUES ACTUELLES".center(60))
    print(f"{'='*60}")
    
    print(f"\n📈 Performances globales :")
    print(f"  • Tâches totales : {task_monitor.total_tasks}")
    print(f"  • Likes : {task_monitor.likes_success}/{task_monitor.likes_attempted}")
    print(f"  • Follows : {task_monitor.follows_success}/{task_monitor.follows_attempted}")
    print(f"  • Videos : {task_monitor.videos_success}/{task_monitor.videos_attempted}")
    print(f"  • CashCoins : {task_monitor.cashcoins:.2f}cc")
    print(f"  • Chaîne max : {task_monitor.max_chain}")
    
    print(f"\n💰 Valeurs CashCoins configurées :")
    config = load_config()
    if config and 'cashcoin_values' in config:
        values = config['cashcoin_values']
        print(f"  • Like : {values.get('like', 0.5)}cc")
        print(f"  • Follow : {values.get('follow', 1.25)}cc")
        print(f"  • Video : {values.get('video', 0.5)}cc")
    
    input("\n👈 Appuyez sur Entrée pour revenir...")

def show_advanced_settings():
    """Affiche les paramètres avancés"""
    clear_screen()
    print(f"{'='*60}")
    print("⚙️  PARAMÈTRES AVANCÉS".center(60))
    print(f"{'='*60}")
    
    config = load_config()
    if not config:
        print("❌ Impossible de charger la configuration")
        input("Appuyez sur Entrée...")
        return
    
    print(f"\n📱 Configuration actuelle :")
    print(f"  • API ID : {config.get('api_id', 'N/A')}")
    print(f"  • Téléphone : {config.get('phone', 'N/A')}")
    print(f"  • Bot ID : {config.get('bot_id', '@SmmKingdomTasksBot')}")
    print(f"  • Force Relog actif : {len(config.get('force_relog', []))} compte(s)")
    
    print(f"\n🔧 Options :")
    print("  1. Modifier les identifiants Telegram")
    print("  2. Modifier les valeurs CashCoins")
    print("  0. Retour")
    
    choix = input("\n👉 Votre choix [0-2] : ").strip()
    
    if choix == "1":
        clear_screen()
        print(f"{'='*60}")
        print("🔐 MODIFICATION TELEGRAM".center(60))
        print(f"{'='*60}")
        
        print(f"\n📝 Valeurs actuelles :")
        print(f"  API ID : {config.get('api_id', '')}")
        print(f"  API Hash : {config.get('api_hash', '')}")
        print(f"  Téléphone : {config.get('phone', '')}")
        print(f"  Bot ID : {config.get('bot_id', '')}")
        
        print("\n   Laissez vide pour ne pas modifier")
        
        new_api_id = input("   👉 Nouvel API ID : ").strip()
        new_api_hash = input("   👉 Nouvel API Hash : ").strip()
        new_phone = input("   👉 Nouveau téléphone : ").strip()
        new_bot_id = input("   👉 Nouveau Bot ID : ").strip()
        
        if new_api_id:
            config['api_id'] = int(new_api_id)
        if new_api_hash:
            config['api_hash'] = new_api_hash
        if new_phone:
            config['phone'] = new_phone
        if new_bot_id:
            config['bot_id'] = new_bot_id
        
        if save_config(config):
            print("\n✅ Configuration Telegram mise à jour !")
    
    elif choix == "2":
        clear_screen()
        print(f"{'='*60}")
        print("💰 VALEURS CASHCOINS".center(60))
        print(f"{'='*60}")
        
        if 'cashcoin_values' not in config:
            config['cashcoin_values'] = {'like': 0.5, 'follow': 1.25, 'video': 0.5}
        
        values = config['cashcoin_values']
        print(f"\n💰 Valeurs actuelles :")
        print(f"  • Like : {values.get('like', 0.5)}cc")
        print(f"  • Follow : {values.get('follow', 1.25)}cc")
        print(f"  • Video : {values.get('video', 0.5)}cc")
        
        print("\n   Entrez les nouvelles valeurs :")
        try:
            new_like = input(f"   👉 Valeur pour Like [{values.get('like', 0.5)}] : ").strip()
            new_follow = input(f"   👉 Valeur pour Follow [{values.get('follow', 1.25)}] : ").strip()
            new_video = input(f"   👉 Valeur pour Video [{values.get('video', 0.5)}] : ").strip()
            
            if new_like:
                config['cashcoin_values']['like'] = float(new_like)
            if new_follow:
                config['cashcoin_values']['follow'] = float(new_follow)
            if new_video:
                config['cashcoin_values']['video'] = float(new_video)
            
            if save_config(config):
                print("\n✅ Valeurs CashCoins mises à jour !")
        except ValueError:
            print("❌ Veuillez entrer des nombres valides")
    
    elif choix == "0":
        return
    
    else:
        print("❌ Choix invalide")
    
    input("\nAppuyez sur Entrée...")

def display_monitor(current_account, current_tour):
    """Affiche le moniteur en haut de l'écran"""
    print("\033[2J\033[H")  # Clear screen and move cursor to top
    print(task_monitor.get_current_stats_display(current_account, current_tour))
    print()

# ================= INSTAGRAM AUTOMATOR =================
class InstagramAutomator:
    def __init__(self, accounts_config, force_relog_list):
        self.clients = {}
        self.last_action_time = {}
        self.setup_logging()
        self.init_clients(accounts_config, force_relog_list)
        self.min_delay = 25
        self.max_delay = 45
    
    def setup_logging(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def get_current_user_agent(self):
        config = load_config()
        if not config:
            return INSTAGRAM_USER_AGENTS["samsung_s21"]
        ua_key = config.get('current_user_agent', 'samsung_s21')
        return INSTAGRAM_USER_AGENTS.get(ua_key, INSTAGRAM_USER_AGENTS["samsung_s21"])
    
    def init_clients(self, accounts_config, force_relog_list):
        self.logger.info("🔧 Init Instagram...")
        
        for telegram_user, creds in accounts_config.items():
            try:
                client = Client()
                client.delay_range = [2, 5]
                
                user_agent = self.get_current_user_agent()
                client.set_user_agent(user_agent)
                
                session_file = f"session_{telegram_user}.json"
                
                if telegram_user in force_relog_list:
                    print(f"⚠️ FORCE RELOG: {telegram_user}")
                    if os.path.exists(session_file):
                        os.remove(session_file)

                try:
                    if os.path.exists(session_file):
                        client.load_settings(session_file)
                        client.login(creds['username'], creds['password'])
                        print(f"✅ Session: {telegram_user}")
                    else:
                        print(f"🔄 Nouvelle co: {telegram_user}")
                        
                        client.set_device({
                            "manufacturer": "samsung",
                            "model": "SM-G991B",
                            "android_version": 33,
                            "android_release": "13"
                        })
                        client.set_locale("fr_FR")
                        client.set_timezone_offset(10800)
                        
                        client.device_settings['device_id'] = f"android-{uuid.uuid4().hex[:16]}"
                        client.device_settings['uuid'] = str(uuid.uuid4())
                        client.device_settings['advertising_id'] = str(uuid.uuid4())
                        
                        time.sleep(random.uniform(2, 4))
                        client.login(creds['username'], creds['password'])
                        time.sleep(random.uniform(3, 5))
                        
                    client.dump_settings(session_file)
                    print(f"💾 Sauvegardé: {telegram_user}")
                    
                    user_id = client.user_id
                    self.clients[telegram_user] = client
                    self.last_action_time[telegram_user] = 0
                    print(f"✅ {telegram_user} (ID: {user_id})")
                    
                except (ClientLoginRequired, ClientError) as e:
                    print(f"❌ {telegram_user}: {str(e)[:100]}")
                    if os.path.exists(session_file):
                        os.remove(session_file)
                    autor = input(f"Continuer? (o/n): ").strip().lower()
                    if autor != 'o':
                        sys.exit(1)
                    
            except Exception as e:
                print(f"❌ Init {telegram_user}: {e}")
                autor = input(f"Continuer? (o/n): ").strip().lower()
                if autor != 'o':
                    sys.exit(1)
    
    def _wait_if_needed(self, telegram_user):
        current_time = time.time()
        if telegram_user in self.last_action_time:
            elapsed = current_time - self.last_action_time[telegram_user]
            if elapsed < self.min_delay:
                wait = self.min_delay - elapsed
                print(f"⏸️ Attente {wait:.1f}s...")
                time.sleep(wait)
    
    def is_real_task(self, message):
        if not message:
            return False
        
        message_lower = message.lower()
        
        if message_lower.startswith("thank you"):
            return False
        
        if "security check" in message_lower or "verification" in message_lower:
            return False
        
        has_link = "▪️ link :" in message_lower
        has_action = "▪️ action :" in message_lower
        has_task = any(p in message_lower for p in ["follow the profile", "like the post below", "open the video"])
        
        return has_link and has_action and has_task
    
    def extract_task_info(self, message):
        try:
            lines = message.split('\n')
            task_info = {'type': None, 'link': None}
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                if '▪️ link :' in line.lower() and i+1 < len(lines):
                    link = lines[i+1].strip()
                    if link.startswith('http'):
                        task_info['link'] = link
                
                elif '▪️ action :' in line.lower() and i+1 < len(lines):
                    action_line = lines[i+1].strip().lower()
                    if 'follow' in action_line:
                        task_info['type'] = 'follow'
                    elif 'like' in action_line:
                        task_info['type'] = 'like'
                    elif 'open the video' in action_line or 'skip to the end' in action_line:
                        task_info['type'] = 'video'
            
            if task_info['type'] and task_info['link']:
                return task_info
            return None
            
        except Exception as e:
            print(f"❌ Extract: {e}")
            return None
    
    async def execute_task(self, telegram_user, task_type, target_link):
        if telegram_user not in self.clients:
            return False, "Non init"
        
        client = self.clients[telegram_user]
        
        self._wait_if_needed(telegram_user)
        
        success, message = await self._attempt_task(client, task_type, target_link, 1)
        
        if not success:
            print("🔄 2ème...")
            await asyncio.sleep(random.uniform(1, 2))
            success, message = await self._attempt_task(client, task_type, target_link, 2)
        
        self.last_action_time[telegram_user] = time.time()
        
        delay = random.uniform(self.min_delay, self.max_delay)
        print(f"⏳ {delay:.1f}s...")
        await asyncio.sleep(delay)
        
        return success, message
    
    async def _attempt_task(self, client, task_type, target, attempt_num):
        try:
            if task_type == 'like':
                await asyncio.sleep(random.uniform(1, 2))
                
                media_pk = client.media_pk_from_url(target)
                
                try:
                    media_info = client.media_info(media_pk)
                    if hasattr(media_info, 'has_liked') and media_info.has_liked:
                        print("⚠️ Déjà liké")
                        return True, "Déjà liké"
                except:
                    pass
                
                await asyncio.sleep(random.uniform(1.5, 4))
                
                result = client.media_like(media_pk)
                await asyncio.sleep(random.uniform(1.5, 3))
                
                if result:
                    return True, "Like OK"
                else:
                    try:
                        media_info = client.media_info(media_pk)
                        if hasattr(media_info, 'has_liked') and media_info.has_liked:
                            return True, "Like vérifié"
                    except:
                        pass
                    return False, "Like KO"
            
            elif task_type == 'follow':
                await asyncio.sleep(random.uniform(2, 4))
                
                if target.endswith('/'):
                    target = target[:-1]
                username = target.split('/')[-1]
                user_id = client.user_id_from_username(username)
                
                try:
                    friendship = client.user_friendship_v1(user_id)
                    if friendship.get('following', False):
                        print("⚠️ Déjà follow")
                        return True, "Déjà follow"
                except:
                    pass
                
                await asyncio.sleep(random.uniform(2, 4))
                
                result = client.user_follow(user_id)
                await asyncio.sleep(random.uniform(1.5, 2))
                
                if result:
                    return True, "Follow OK"
                else:
                    return False, "Follow KO"
            
            elif task_type == 'video':
                print("🎥 7s...")
                await asyncio.sleep(7)
                return True, "Vidéo OK"
            
            return False, "Type?"
                
        except Exception as e:
            error = str(e)
            if 'spam' in error.lower() or 'feedback_required' in error.lower():
                print("🚨 Spam - 10min")
                await asyncio.sleep(400)
            return False, f"Err: {error[:50]}"


# ================= NOTIFICATIONS TERMUX =================
async def notify_termux(title, content):
    """Fonction de notification standard"""
    try:
        # Notification avec son et vibration
        os.system(f'termux-notification --title "{title}" --content "{content}" --sound --priority high')
        os.system('termux-vibrate -d 500')
        return True
    except:
        return False

async def trigger_security_alert():
    """Fonction spécifique pour le Security Check : Son + Grosse Vibration + Ouverture Directe"""
    try:
        # 1. Vibration longue (1 seconde)
        os.system('termux-vibrate -d 1000')
        
        # 2. Notification avec son forcé
        os.system('termux-notification --title "🚨 ALERTE SÉCURITÉ 🚨" --content "Vérification de sécurité détectée ! Clique pour ouvrir le bot." --sound --priority high --led-color red')
        
        # 3. Ouverture directe du message dans Telegram
        os.system('termux-open-url "tg://resolve?domain=SmmKingdomTasksBot"')
        
        print("🔔 Alerte sonore et vibration envoyées. Telegram ouvert.")
    except Exception as e:
        print(f"⚠️ Erreur notification : {e}")

# ================= GESTION COMPTES =================
def get_next_account(accounts_list):
    """Gère la rotation des comptes Instagram"""
    global current_account_index, tour_count
    
    if not accounts_list:
        return None
    
    tour_count += 1
    current_account = accounts_list[current_account_index]
    
    # Afficher le moniteur avant chaque tour
    display_monitor(current_account, tour_count)
    
    # Réinitialiser les stats pour le nouveau compte si c'est le début
    if tour_count == 1:
        task_monitor.reset_current_account(current_account)
    
    if tour_count >= 15:
        # Afficher mini-résumé avant rotation
        old_account = accounts_list[current_account_index]
        performance = task_monitor.get_account_performance(old_account)
        print(f"\n🔄 Rotation: {old_account} → ", end="")
        
        current_account_index = (current_account_index + 1) % len(accounts_list)
        tour_count = 0
        new_account = accounts_list[current_account_index]
        
        print(f"{new_account} | Performances: {performance}")
        
        # Réinitialiser pour le nouveau compte
        task_monitor.reset_current_account(new_account)
        display_monitor(new_account, tour_count)
        
        return new_account
    
    return current_account

# ================= FONCTIONS TELEGRAM SAFE (MODIFIÉES) =================
async def click_button(client, bot_id, text_to_find):
    """Envoie le texte directement comme message (pas de recherche de bouton)"""
    global safe_client
    
    try:
        print(f"📤 Envoi du message: {text_to_find}")
        await asyncio.sleep(1)  # Réduit de 2 à 1 seconde
        await safe_client.send_message_safe(bot_id, text_to_find)
        print(f"✅ Message envoyé: {text_to_find}")
        return True
        
    except Exception as e:
        print(f"⚠️ Erreur dans click_button: {e}")
        return False

async def get_bot_response(client, bot_id):
    """Lit la DERNIÈRE réponse du bot - Version améliorée"""
    global safe_client
    
    try:
        # Augmenter la limite pour voir plus de messages
        messages = await safe_client.get_messages_safe(bot_id, limit=10)
        
        if not messages or len(messages) == 0:
            print("📭 Aucun message trouvé")
            return None
        
        # Parcourir les messages du plus récent au plus ancien
        for message in messages:
            if message.message:
                msg_text = message.message.lower()
                # Ignorer les messages indésirables
                if msg_text.startswith("thank you"):
                    continue
                # Si c'est un message intéressant, le retourner
                if ("▪️ link :" in msg_text and "▪️ action :" in msg_text) or \
                   "sorry" in msg_text or \
                   "no active tasks" in msg_text or \
                   "security check" in msg_text:
                    return message.message
        
        # Si aucun message intéressant trouvé, retourner le plus récent
        return messages[0].message
        
    except Exception as e:
        print(f"⚠️ Erreur lecture message: {e}")
        return None

async def wait_for_response_with_patience(client, bot_id, timeout=20):
    """Attend patiemment une réponse du bot avec vérifications périodiques"""
    print(f"⏳ Attente réponse (timeout: {timeout}s)...")
    
    start_time = time.time()
    check_interval = 2  # Réduit de 3 à 2 secondes
    
    while time.time() - start_time < timeout:
        response = await get_bot_response(client, bot_id)
        
        if response:
            response_lower = response.lower()
            
            # Vérifier si c'est un message de sécurité
            if "security check" in response_lower:
                print("🛡️ DÉTECTION SÉCURITÉ! Message de vérification trouvé!")
                return response
            
            # Vérifier si c'est une tâche ou "sorry"
            if "▪️ link :" in response_lower or "sorry" in response_lower or "no active tasks" in response_lower:
                print(f"✅ Réponse reçue après {int(time.time() - start_time)}s")
                return response
        
        # Attendre avant de vérifier à nouveau
        await asyncio.sleep(check_interval)
    
    print(f"⚠️ Timeout après {timeout}s")
    return None

async def wait_for_sorry(client, bot_id):
    """Attend UNIQUEMENT le mot 'Sorry' (ignore tout le reste)"""
    print("🕗 En attente du 'Sorry'...")
    
    # D'abord vérifier avec cache
    current_msg = await get_bot_response(client, bot_id)
    if current_msg and "sorry" in current_msg.lower():
        print("✅ 'Sorry' déjà présent")
        return True
    
    event_received = asyncio.Event()
    
    @client.on(events.NewMessage(from_users=bot_id))
    async def handler(event):
        msg_text = event.raw_text.lower()
        if "sorry" in msg_text:
            print("✅ 'Sorry' reçu")
            event_received.set()
        elif "security check" in msg_text:
            print("🛡️ DÉTECTION SÉCURITÉ pendant attente Sorry!")
            # On traitera cette situation dans la boucle principale
            event_received.set()
        else:
            print(f"📄 Message ignoré: {event.raw_text[:50]}...")
    
    try:
        await asyncio.wait_for(event_received.wait(), timeout=180)
        client.remove_event_handler(handler)
        return True
    except asyncio.TimeoutError:
        print("⚠️  Timeout attente Sorry")
        client.remove_event_handler(handler)
        return False

# ================= GESTION SÉCURITÉ =================
def check_security_message(message):
    """Vérifie si c'est un message de vérification de sécurité"""
    if not message:
        return False
    
    msg_lower = message.lower()
    return "security check" in msg_lower and "verification" in msg_lower

async def handle_security_check():
    """Gère la détection d'un message de sécurité avec alerte maximale"""
    global security_check_detected
    
    print("\n" + "!"*60)
    print("🛡️  ALERTE SÉCURITÉ DÉTECTÉE ! ACTION REQUISE".center(60))
    print("!"*60)
    
    security_check_detected = True
    
    # Appel de la nouvelle fonction d'alerte (Son + Vibration + Ouverture)
    await trigger_security_alert()
    
    print("\n⏸️ Script en PAUSE")
    print("👉 Complète la vérification manuellement sur Telegram.")
    print("🔄 Le script reprendra automatiquement après validation.")
    
    # Pause prolongée pour te laisser le temps de répondre au bot
    # On attend que l'utilisateur valide (tu peux aussi mettre une pause infinie ici)
    await asyncio.sleep(60) 
    
    security_check_detected = False
    return True
    
# ================= GESTION TÂCHES SIMPLE =================
async def process_task(client, instagram_automator, task_message, telegram_user, bot_id, cashcoin_values, config):
    """Traite une tâche Instagram"""
    
    task_info = instagram_automator.extract_task_info(task_message)
    
    if not task_info:
        print("❌ Impossible d'extraire les infos")
        await notify_termux("SMM - ERREUR", "Analyse tâche impossible")
        return False
    
    enabled_tasks = config.get('enabled_tasks', {'like': True, 'follow': True, 'video': True})
    if not enabled_tasks.get(task_info['type'], True):
        print(f"⚠️ Tâche {task_info['type']} désactivée - Skip automatique")
        await safe_client.send_message_safe(bot_id, "❌Skip")
        print("📤 Envoyé: ❌Skip")
        await asyncio.sleep(1)  # Ralenti
        
        # 🔥 CORRECTION : Vérifier si une NOUVELLE tâche arrive après le Skip
        print("🔍 Vérification d'une nouvelle tâche après Skip...")
        await asyncio.sleep(2)  # Attendre la réponse du bot
        
        bot_response = await get_bot_response(client, bot_id)
        if bot_response:
            # Vérifier d'abord si c'est un message de sécurité
            if check_security_message(bot_response):
                await handle_security_check()
                return False
            
            # Vérifier si c'est une NOUVELLE tâche
            if instagram_automator.is_real_task(bot_response):
                print("\n🔄 NOUVELLE TÂCHE DÉTECTÉE après Skip!")
                print("🤖 Traitement de la nouvelle tâche...")
                
                # Traiter la nouvelle tâche récursivement
                return await process_task(client, instagram_automator, bot_response, telegram_user, bot_id, cashcoin_values, config)
            
            # Vérifier si c'est "Sorry"
            elif "sorry" in bot_response.lower():
                print("✅ 'Sorry' reçu après Skip.")
                return False
        
        return False
    
    mode = config.get('mode', 'normal')
    if mode == 'safe':
        now = time.time()
        stats = task_monitor.account_stats[telegram_user]
        pause_key = f"{task_info['type']}_pause_until"
        count_key = f"{task_info['type']}s_count"
        max_count = 25 if task_info['type'] == 'like' else 15 if task_info['type'] == 'follow' else 10
        
        if stats.get(pause_key, 0) > now:
            print(f"⏸️ Pause active pour {task_info['type']} jusqu'à {datetime.fromtimestamp(stats[pause_key])}")
            await safe_client.send_message_safe(bot_id, "❌Skip")
            print("📤 Envoyé: ❌Skip (pause active)")
            await asyncio.sleep(1)  # Ralenti
            
            # 🔥 CORRECTION : Même vérification pour les pauses
            print("🔍 Vérification d'une nouvelle tâche après Skip (pause)...")
            await asyncio.sleep(2)
            
            bot_response = await get_bot_response(client, bot_id)
            if bot_response:
                if check_security_message(bot_response):
                    await handle_security_check()
                    return False
                
                if instagram_automator.is_real_task(bot_response):
                    print("\n🔄 NOUVELLE TÂCHE DÉTECTÉE après Skip (pause)!")
                    print("🤖 Traitement de la nouvelle tâche...")
                    return await process_task(client, instagram_automator, bot_response, telegram_user, bot_id, cashcoin_values, config)
                
                elif "sorry" in bot_response.lower():
                    print("✅ 'Sorry' reçu après Skip (pause).")
                    return False
            
            return False

        if stats.get(pause_key, 0) > 0:
            stats[count_key] = 0
            stats[pause_key] = 0

        if stats.get(count_key, 0) >= max_count:
            stats[pause_key] = now + 3600
            print(f"🚫 Limite atteinte pour {task_info['type']}, pause 1h")
            await safe_client.send_message_safe(bot_id, "❌Skip")
            print("📤 Envoyé: ❌Skip (limite atteinte)")
            await asyncio.sleep(1)  # Ralenti
            
            # 🔥 CORRECTION : Même vérification pour les limites
            print("🔍 Vérification d'une nouvelle tâche après Skip (limite)...")
            await asyncio.sleep(2)
            
            bot_response = await get_bot_response(client, bot_id)
            if bot_response:
                if check_security_message(bot_response):
                    await handle_security_check()
                    return False
                
                if instagram_automator.is_real_task(bot_response):
                    print("\n🔄 NOUVELLE TÂCHE DÉTECTÉE après Skip (limite)!")
                    print("🤖 Traitement de la nouvelle tâche...")
                    return await process_task(client, instagram_automator, bot_response, telegram_user, bot_id, cashcoin_values, config)
                
                elif "sorry" in bot_response.lower():
                    print("✅ 'Sorry' reçu après Skip (limite).")
                    return False
            
            return False
    
    print(f"📋 Type: {task_info['type'].upper()}")
    print(f"🔗 Lien: {task_info['link']}")
    print(f"👤 Compte: {telegram_user}")
    
    print("🔄 Exécution...")
    await asyncio.sleep(1.5)  # Ralenti avant exécution
    success, result = await instagram_automator.execute_task(telegram_user, task_info['type'], task_info['link'])
    
    # Valeurs CashCoins depuis la config
    cashcoins = cashcoin_values.get(task_info['type'], 0.5 if task_info['type'] == 'like' else 1.25 if task_info['type'] == 'follow' else 0.5)
    
    if success:
        print(f"✅ Tâche {task_info['type'].upper()} réussie!", end=" ")
        
        # Ajouter aux stats
        task_monitor.add_task(task_info['type'], True, cashcoins)
        
        # Rafraîchir l'affichage
        display_monitor(telegram_user, tour_count)
        
        # Afficher mise à jour
        likes_display = f"{task_monitor.likes_success}/{task_monitor.likes_attempted}"
        follows_display = f"{task_monitor.follows_success}/{task_monitor.follows_attempted}"
        videos_display = f"{task_monitor.videos_success}/{task_monitor.videos_attempted}"
        print(f"(+{cashcoins}cc) [❤️{likes_display} 👥{follows_display} 📹{videos_display} 💰{task_monitor.cashcoins:.1f}cc]")
        
        if mode == 'safe':
            stats[count_key] += 1
            if stats[count_key] >= max_count:
                stats[pause_key] = now + 3600
                print(f"⏰ Pause activée pour {task_info['type']} pendant 1h")
        
        # Envoyer ✅Completed avec version safe
        await asyncio.sleep(1.5)  # Ralenti
        await safe_client.send_message_safe(bot_id, "✅Completed")
        print("📤 Envoyé: ✅Completed")
        
        # Vérifier la réponse du bot avec cache
        print("🔄 Vérification réponse bot...")
        await asyncio.sleep(2)  # Ralenti
        
        bot_response = await get_bot_response(client, bot_id)
        
        if bot_response:
            # Vérifier d'abord si c'est un message de sécurité
            if check_security_message(bot_response):
                await handle_security_check()
                return True
            
            # Vérifier si c'est une NOUVELLE tâche
            if instagram_automator.is_real_task(bot_response):
                print("\n🔄 NOUVELLE TÂCHE DÉTECTÉE!")
                print("🤖 Traitement en chaîne...")
                
                return await process_task(client, instagram_automator, bot_response, telegram_user, bot_id, cashcoin_values, config)
            
            # Vérifier si c'est "Sorry"
            elif "sorry" in bot_response.lower():
                print("✅ 'Sorry' reçu. Fin de traitement.")
                return True
            
            # Sinon, attendre le Sorry
            else:
                print(f"📄 Message reçu: {bot_response[:50]}...")
                print("🕗 Attente du 'Sorry'...")
                await wait_for_sorry(client, bot_id)
                return True
        else:
            # Pas de réponse, attendre le Sorry
            print("⏳ Pas de réponse, attente du 'Sorry'...")
            await wait_for_sorry(client, bot_id)
            return True
    
    else:
        # ÉCHEC de la tâche
        print(f"❌ Échec: {result}", end=" ")
        
        # Ajouter aux stats (échec)
        task_monitor.add_task(task_info['type'], False, 0)
        
        # Rafraîchir l'affichage
        display_monitor(telegram_user, tour_count)
        
        likes_display = f"{task_monitor.likes_success}/{task_monitor.likes_attempted}"
        follows_display = f"{task_monitor.follows_success}/{task_monitor.follows_attempted}"
        videos_display = f"{task_monitor.videos_success}/{task_monitor.videos_attempted}"
        print(f"[❤️{likes_display} 👥{follows_display} 📹{videos_display} 💰{task_monitor.cashcoins:.1f}cc]")
        
        logs = load_logs()
        logs.append({
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'account': telegram_user,
            'task_type': task_info['type'],
            'reason': result,
            'link': task_info['link']
        })
        save_logs(logs)
        
        await asyncio.sleep(1)  # Ralenti
        await safe_client.send_message_safe(bot_id, "❌Skip")
        print("📤 Envoyé: ❌Skip")
        
        # 🔥 CORRECTION : Vérifier aussi après un Skip d'échec
        print("🔍 Vérification d'une nouvelle tâche après Skip (échec)...")
        await asyncio.sleep(2)
        
        bot_response = await get_bot_response(client, bot_id)
        if bot_response:
            if check_security_message(bot_response):
                await handle_security_check()
                return False
            
            if instagram_automator.is_real_task(bot_response):
                print("\n🔄 NOUVELLE TÂCHE DÉTECTÉE après Skip (échec)!")
                print("🤖 Traitement de la nouvelle tâche...")
                return await process_task(client, instagram_automator, bot_response, telegram_user, bot_id, cashcoin_values, config)
            
            elif "sorry" in bot_response.lower():
                print("✅ 'Sorry' reçu après Skip (échec).")
                return False
        
        return False

# ================= BOUCLE PRINCIPALE SIMPLE =================
async def main_bot():
    """Fonction principale du bot (exécutée quand on choisit "Lancer le bot")"""
    global task_found, current_account_index, tour_count, safe_client, security_check_detected
    
    # Charger la configuration
    config = load_config()
    if not config:
        print("❌ Impossible de charger la configuration")
        return
    
    reset_logs()
    
    # Initialiser les variables depuis la config
    api_id = config.get('api_id', 30930720)
    api_hash = config.get('api_hash', "b17b4f5712c32e64e3e2772871e3589c")
    phone = config.get('phone', "+261341318531")
    bot_id = config.get('bot_id', "@SmmKingdomTasksBot")
    instagram_accounts = config.get('instagram_accounts', {})
    force_relog = config.get('force_relog', ["bifsteak56"])
    cashcoin_values = config.get('cashcoin_values', {'like': 0.5, 'follow': 1.25, 'video': 0.5})
    
    if not instagram_accounts:
        print("❌ Aucun compte Instagram configuré")
        input("Appuyez sur Entrée pour revenir...")
        return
    
    # Réinitialiser les variables globales
    current_account_index = 0
    tour_count = 0
    task_found = False
    security_check_detected = False
    
    # ⚠️ IMPORTANT : Je garde le même nom de session que ton script original
    session_name = "smm_session"
    
    print(f"\n📁 Session Telegram: {session_name}")
    print(f"📱 Numéro: {phone}")
    print(f"🤖 Bot: {bot_id}")
    print(f"📊 {len(instagram_accounts)} compte(s) Instagram configuré(s)")
    print(f"🔄 Force Relog: {len(force_relog)} compte(s)")
    
    # Initialiser le client Telegram (SANS modification du nom de session)
    client = TelegramClient(session_name, api_id, api_hash)
    
    # Initialiser le safe client (NOUVEAU)
    safe_client = SafeTelegramClient(client)
    print("🔒 SafeTelegramClient initialisé (anti-flood activé)")
    
    # Initialiser l'automateur Instagram
    instagram_automator = InstagramAutomator(instagram_accounts, force_relog)
    
    await notify_termux("SMM BOT", "Démarrage du bot...")
    
    current_state = "debut"
    target_accounts = list(instagram_accounts.keys())
    
    while True:
        try:
            # Vérifier si une alerte de sécurité est active
            if security_check_detected:
                print("⏸️ Script en pause pour vérification de sécurité...")
                await asyncio.sleep(10)
                continue
            
            # === ÉTAT 1: DÉBUT / RECONNEXION ===
            if current_state == "debut" or not client.is_connected():
                print("\n🔗 Connexion Telegram...")
                
                # Connexion simple sans force_sms
                await client.start(phone=phone)
                
                print(f"✅ CONNECTÉ: {phone}")
                
                print("🚀 /start au bot...")
                await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                await safe_client.send_message_safe(bot_id, "/start")
                await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                current_state = "menu_principal"
            
            # === ÉTAT 2: MENU PRINCIPAL (après /start) ===
            if current_state == "menu_principal":
                print("\n📝 Envoi de '📝Tasks📝'...")
                await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                if await click_button(client, bot_id, "📝Tasks📝"):
                    await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                    current_state = "menu_tasks"
                else:
                    print("❌ Échec Tasks. Retour /start...")
                    await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                    await safe_client.send_message_safe(bot_id, "/start")
                    await asyncio.sleep(2)  # Réduit de 3 à 2 secondes
                    continue
            
            # === ÉTAT 3: MENU TASKS ===
            if current_state == "menu_tasks":
                print("\n📸 Envoi de 'Instagram'...")
                await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                if await click_button(client, bot_id, "Instagram"):
                    await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                    current_state = "menu_instagram"
                else:
                    print("❌ Échec Instagram. Retour /start...")
                    await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                    await safe_client.send_message_safe(bot_id, "/start")
                    await asyncio.sleep(2)  # Réduit de 3 à 2 secondes
                    current_state = "menu_principal"
                    continue
            
            # === ÉTAT 4: MENU INSTAGRAM (choix du compte) ===
            if current_state == "menu_instagram":
                current_target = get_next_account(target_accounts)
                
                if not current_target:
                    print("❌ Erreur: aucune cible disponible")
                    current_state = "menu_tasks"
                    continue
                
                print(f"\n{'─'*30}")
                print(f"📱 Compte: {current_target}")
                print(f"{'─'*30}")
                
                print(f"➡️ Envoi de {current_target}...")
                await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                if await click_button(client, bot_id, current_target):
                    await asyncio.sleep(1.5)  # Réduit de 2 à 1.5 secondes
                    current_state = "verif_tache"
                else:
                    print("❌ Échec sélection compte. Retour menu Instagram...")
                    current_state = "menu_instagram"
                    continue
            
            # === ÉTAT 5: VÉRIFICATION TÂCHE ===
            if current_state == "verif_tache":
                print("\n🔍 Vérification réponse bot (avec patience)...")
                
                # Attendre patiemment une réponse
                bot_response = await wait_for_response_with_patience(client, bot_id, timeout=20)
                
                if not bot_response:
                    print("❌ Pas de réponse du bot après attente. Retour menu Instagram...")
                    current_state = "menu_tasks"
                    continue
                
                # Vérifier si c'est un message de sécurité
                if check_security_message(bot_response):
                    await handle_security_check()
                    current_state = "menu_tasks"
                    continue
                
                bot_response_lower = bot_response.lower()
                
                if "sorry" in bot_response_lower or "no active tasks" in bot_response_lower:
                    print("⛔ Pas de tâche disponible")
                    current_state = "menu_tasks"
                    continue
                
                if bot_response_lower.startswith("thank you"):
                    print("⛔ Message 'Thank you' ignoré - recherche d'une vraie tâche...")
                    # Continuer à chercher une vraie tâche
                    continue
                
                if instagram_automator.is_real_task(bot_response):
                    print("\n" + "="*50)
                    print("🎯 TÂCHE DÉTECTÉE !")
                    print("="*50)
                    
                    task_found = True
                    
                    task_success = await process_task(client, instagram_automator, bot_response, current_target, bot_id, cashcoin_values, config)
                    
                    print("\n🔄 Retour au menu Instagram...")
                    task_found = False
                    current_state = "menu_tasks"
                    await asyncio.sleep(1.5)  # Ralenti
                    continue
                
                # Message inattendu - ignorer et continuer
                print(f"📄 Message inattendu ignoré: {bot_response[:50]}...")
                print("🔄 Retour au menu Instagram...")
                current_state = "menu_tasks"
                continue
            
            await asyncio.sleep(1)  # Réduit de 2 à 1 seconde
            
        except Exception as e:
            print(f"\n❌ ERREUR: {e}")
            import traceback
            traceback.print_exc()
            print("🔄 Reconnexion dans 10s...")
            
            try:
                await client.disconnect()
            except:
                pass
            
            await asyncio.sleep(10)
            current_state = "debut"

# ================= POINT D'ENTRÉE PRINCIPAL =================
async def main():
    """Point d'entrée principal avec menu interactif"""
    
    # Afficher le menu principal
    choix = show_main_menu()
    
    if choix == "run_bot":
        # Lancer le bot
        await main_bot()
        
        # Quand le bot s'arrête (erreur ou Ctrl+C)
        print("\n" + "="*50)
        print("📊 STATISTIQUES DE LA SESSION :")
        print("="*50)
        print(f"├─ Tâches totales: {task_monitor.total_tasks}")
        print(f"├─ Likes: {task_monitor.likes_success}/{task_monitor.likes_attempted}")
        print(f"├─ Follows: {task_monitor.follows_success}/{task_monitor.follows_attempted}")
        print(f"├─ Videos: {task_monitor.videos_success}/{task_monitor.videos_attempted}")
        print(f"├─ CashCoins totaux: {task_monitor.cashcoins:.2f}")
        print(f"├─ Chaîne max: {task_monitor.max_chain}")
        print(f"└─ Taux réussite: ", end="")
        
        total_attempted = task_monitor.likes_attempted + task_monitor.follows_attempted + task_monitor.videos_attempted
        total_success = task_monitor.likes_success + task_monitor.follows_success + task_monitor.videos_success
        if total_attempted > 0:
            print(f"{(total_success/total_attempted)*100:.1f}%")
        else:
            print("0%")
        
        input("\n👈 Appuyez sur Entrée pour revenir au menu...")
        
        # Retour au menu principal
        await main()

# ================= LANCEMENT =================
if __name__ == "__main__":
    _verify()  # ← vérification licence (bloque si invalide/expirée)
    print("🤖 SMM BOT - COMPTE SECOND - VERSION AMÉLIORÉE")
    print("📊 Interface interactive avec moniteur et gestion des comptes")
    print("💰 Like: 0.5cc | Follow: 1.25cc | Video: 0.5cc")
    print("🔄 Force Relog disponible via menu")
    print("🔒 Système anti-flood activé")
    print("🛡️ Détection de sécurité intégrée")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du programme.")
    except Exception as e:
        print(f"\n💥 Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        input("\nAppuyez sur Entrée pour quitter...")
