from flask import Flask, render_template, request, redirect, url_for, flash
import json
import os
import time
import psutil

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

# Keep last network counters to compute per-second rates
LAST_NET = {'timestamp': None, 'pernic': {}}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {'host': '0.0.0.0', 'port': 4242, 'display': 'gauges', 'theme': 'light', 'time_format': '24', 'show_update_time': True}
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)

app = Flask(__name__)
# Secret key for flashing messages. In production, set this via env var.
app.secret_key = 'dev-secret'


# Make config available in all templates
@app.context_processor
def inject_config():
    try:
        cfg = load_config()
    except Exception:
        cfg = {'host': '0.0.0.0', 'port': 4242, 'display': 'gauges', 'theme': 'light', 'time_format': '24', 'show_update_time': True}
    # ensure keys exist (safe defaults) so templates don't get Undefined
    cfg.setdefault('time_format', '24')
    cfg.setdefault('show_update_time', True)
    cfg.setdefault('theme', 'light')
    cfg.setdefault('display', 'gauges')
    # network defaults
    cfg.setdefault('net_interface', None)
    cfg.setdefault('net_baseline_mbps', 1000)
    return dict(config=cfg)

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    # Display Hello World
    return render_template('dashboard.html')


@app.route('/api/stats')
def api_stats():
    """Return basic CPU and RAM stats as JSON."""
    # Sample per-core briefly and compute an average for the overall CPU percent
    try:
        per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        if per_core:
            cpu_percent = sum(per_core) / len(per_core)
        else:
            cpu_percent = 0.0
    except Exception:
        cpu_percent = psutil.cpu_percent(interval=None)
        per_core = []
    vm = psutil.virtual_memory()
    stats = {
        'cpu_percent': cpu_percent,
        'cpu_count': psutil.cpu_count(logical=True),
        'cpu_freq': None,
        'per_core': per_core,
        'memory': {
            'total': vm.total,
            'available': vm.available,
            'used': vm.used,
            'percent': vm.percent,
        },
        'timestamp': int(time.time())
    }
    # Add CPU frequency if available
    try:
        freq = psutil.cpu_freq()
        if freq and hasattr(freq, 'current'):
            stats['cpu_freq'] = round(freq.current / 1000.0, 2)  # GHz
    except Exception:
        pass
    # Add network counters and approximate per-second rates (per-interface)
    try:
        now = time.time()
        pernic = psutil.net_io_counters(pernic=True)
        # list of interface names
        iface_names = list(pernic.keys()) if pernic else []
        # load selected interface and baseline from config (non-blocking)
        try:
            cfg = load_config()
        except Exception:
            cfg = {}
        selected_iface = cfg.get('net_interface')
        baseline_mbps = cfg.get('net_baseline_mbps', 1000)

        # helper to compute totals for a given iface name (or aggregate when iface is None)
        def _get_counters(iface=None):
            if iface and pernic and iface in pernic:
                nic = pernic[iface]
                return getattr(nic, 'bytes_sent', 0), getattr(nic, 'bytes_recv', 0)
            # aggregate
            s = 0
            r = 0
            if pernic:
                for n, val in pernic.items():
                    s += getattr(val, 'bytes_sent', 0)
                    r += getattr(val, 'bytes_recv', 0)
            return s, r

        bytes_sent, bytes_recv = _get_counters(selected_iface)
        sent_per_sec = None
        recv_per_sec = None
        if LAST_NET.get('timestamp'):
            dt = now - LAST_NET['timestamp']
            if dt > 0:
                prev = LAST_NET.get('pernic', {})
                prev_sent = 0
                prev_recv = 0
                if selected_iface:
                    prev_vals = prev.get(selected_iface, {})
                    prev_sent = prev_vals.get('bytes_sent', 0) or 0
                    prev_recv = prev_vals.get('bytes_recv', 0) or 0
                else:
                    # aggregate previous
                    for k, v in prev.items():
                        prev_sent += v.get('bytes_sent', 0) or 0
                        prev_recv += v.get('bytes_recv', 0) or 0
                sent_per_sec = (bytes_sent - prev_sent) / dt
                recv_per_sec = (bytes_recv - prev_recv) / dt

        # store latest pernic snapshot
        LAST_NET['timestamp'] = now
        LAST_NET['pernic'] = {}
        if pernic:
            for n, val in pernic.items():
                LAST_NET['pernic'][n] = {'bytes_sent': getattr(val, 'bytes_sent', 0), 'bytes_recv': getattr(val, 'bytes_recv', 0)}

        stats['network'] = {
            'bytes_sent': bytes_sent,
            'bytes_recv': bytes_recv,
            'sent_per_sec': sent_per_sec,
            'recv_per_sec': recv_per_sec,
            'interfaces': iface_names,
            'selected_interface': selected_iface,
            'baseline_mbps': baseline_mbps,
        }
    except Exception:
        stats['network'] = {'bytes_sent': 0, 'bytes_recv': 0, 'sent_per_sec': None, 'recv_per_sec': None, 'interfaces': [], 'selected_interface': None, 'baseline_mbps': 1000}
    return json.dumps(stats)


@app.route('/api/net_interface', methods=['POST'])
def set_net_interface():
    """Set selected network interface (JSON body: {iface: name|null, baseline_mbps: number})"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return json.dumps({'ok': False, 'error': 'invalid-json'}), 400
    cfg = load_config()
    # allow null to mean aggregate
    iface = data.get('iface') if isinstance(data.get('iface'), str) else None
    baseline = data.get('baseline_mbps')
    if baseline is None:
        baseline = cfg.get('net_baseline_mbps', 1000)
    try:
        baseline = int(baseline)
    except Exception:
        baseline = cfg.get('net_baseline_mbps', 1000)
    cfg['net_interface'] = iface
    cfg['net_baseline_mbps'] = baseline
    save_config(cfg)
    return json.dumps({'ok': True, 'iface': iface, 'baseline_mbps': baseline})


# Some browser extensions inject scripts that reference source maps (e.g. injection-tss-mv3.js.map)
# which cause noisy 404s in the DevTools console. Serve a small empty JSON response for that
# known filename so the browser won't log a missing source map for our dev server.
@app.route('/injection-tss-mv3.js.map')
def injection_map():
    # Return a minimal, valid source map to satisfy browser parsers
    sm = {
        'version': 3,
        'file': '',
        'sources': [],
        'names': [],
        'mappings': ''
    }
    return json.dumps(sm), 200, {'Content-Type': 'application/json'}


# Catch any top-level .map requests and return an empty JSON body so browser DevTools
# won't log 404s for stray source-map URLs injected by extensions.
@app.route('/<path:fname>.map')
def catch_all_map(fname):
    # Return a minimal, valid source map for any top-level .map request to avoid noisy 404s
    sm = {
        'version': 3,
        'file': '',
        'sources': [],
        'names': [],
        'mappings': ''
    }
    return json.dumps(sm), 200, {'Content-Type': 'application/json'}

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    cfg = load_config()
    if request.method == 'POST':
        host = request.form.get('host', cfg.get('host'))
        port = request.form.get('port', cfg.get('port'))
        display = request.form.get('display', cfg.get('display', 'gauges'))
        time_format = request.form.get('time_format', cfg.get('time_format', '24'))
        show_update_time = True if request.form.get('show_update_time') == 'on' else False
        theme = request.form.get('theme', cfg.get('theme', 'light'))
        # network settings from the form (optional)
        # Only override if the form submitted the fields; otherwise preserve current cfg values
        if 'net-interface' in request.form:
            val = request.form.get('net-interface')
            net_iface = val if val not in (None, '') else None
        else:
            net_iface = cfg.get('net_interface')
        if 'net-baseline' in request.form:
            net_baseline = request.form.get('net-baseline')
        else:
            net_baseline = cfg.get('net_baseline_mbps', 1000)
        try:
            port = int(port)
        except ValueError:
            port = cfg.get('port', 4242)
        try:
            net_baseline = int(net_baseline)
        except Exception:
            net_baseline = cfg.get('net_baseline_mbps', 1000)
        # update existing cfg to preserve other keys
        cfg['host'] = host
        cfg['port'] = port
        cfg['display'] = display
        cfg['theme'] = theme
        cfg['time_format'] = time_format
        cfg['show_update_time'] = show_update_time
        cfg['net_interface'] = net_iface
        cfg['net_baseline_mbps'] = net_baseline
        save_config(cfg)
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html', config=cfg)

if __name__ == '__main__':
    cfg = load_config()
    # Allow enabling debug mode via env var for development; otherwise run cleanly without the auto-reloader
    debug_mode = os.environ.get('JELLY_DEBUG', '0') in ('1', 'true', 'True')
    app.run(host=cfg.get('host', '0.0.0.0'), port=int(cfg.get('port', 4242)), debug=debug_mode)
