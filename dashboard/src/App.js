import React, { useState, useEffect, useRef } from 'react';
import {
  Area, AreaChart, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Line
} from 'recharts';
import { wsManager } from './websocket';
import PacketStructureModal from './components/PacketStructureModal';

// ── Theme definitions ─────────────────────────────────────────────────────────
const DARK = {
  bg:       '#050d1a', panel:   '#0a1628', border:  '#0d2040', borderHi: '#1a4080',
  headerBg: '#030a14', panelHd: '#071020',
  accent:   '#00d4ff', green:   '#00ff88', yellow:  '#ffd600', red:     '#ff3366',
  orange:   '#ff7c00', purple:  '#9d4edd', teal:    '#00e5cc',
  dim:      '#2a4060', text:    '#c8e0ff', textDim: '#4a6080',
  scrollThumb: '#1a4080',
  rowAlt:   '#ffffff05', rowHover: '#00d4ff11',
  mono: "'JetBrains Mono', monospace", sans: "'Space Grotesk', sans-serif",
};

const LIGHT = {
  bg:       '#f0f4fa', panel:   '#ffffff', border:  '#d0ddf0', borderHi: '#4a80c0',
  headerBg: '#1e3a5f', panelHd: '#f8faff',
  accent:   '#0066cc', green:   '#00994d', yellow:  '#b38600', red:     '#cc1144',
  orange:   '#cc5500', purple:  '#6a1fb5', teal:    '#007a6e',
  dim:      '#c0cfe0', text:    '#1a2a3a', textDim: '#6a80a0',
  scrollThumb: '#4a80c0',
  rowAlt:   '#f8faff', rowHover: '#e6f0ff',
  mono: "'JetBrains Mono', monospace", sans: "'Space Grotesk', sans-serif",
};

const ENDPOINTS = ['/auth', '/payments', '/inventory'];
const EP_LABEL  = { '/auth': 'Auth', '/payments': 'Payments', '/inventory': 'Inventory' };

function epColor(ep, C) {
  return ep === '/auth' ? C.accent : ep === '/payments' ? C.green : C.yellow;
}

function ts(t) {
  const d = new Date(t * 1000);
  return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}:${d.getSeconds().toString().padStart(2,'0')}`;
}

// ── Panel wrapper ─────────────────────────────────────────────────────────────
function Panel({ title, children, style = {}, badge = null, badgeColor, C }) {
  const bc = badgeColor || C.accent;
  return (
    <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8, overflow: 'hidden', ...style }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 14px', borderBottom: `1px solid ${C.border}`, background: C.panelHd }}>
        <span style={{ fontFamily: C.sans, fontSize: 11, fontWeight: 600, letterSpacing: 2, color: C.textDim, textTransform: 'uppercase' }}>{title}</span>
        {badge !== null && (
          <span style={{ fontFamily: C.mono, fontSize: 11, color: bc, background: bc + '22', padding: '2px 8px', borderRadius: 4 }}>{badge}</span>
        )}
      </div>
      <div style={{ padding: 14 }}>{children}</div>
    </div>
  );
}

function Dot({ color, pulse = false }) {
  return (
    <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: color, boxShadow: pulse ? `0 0 8px ${color}` : 'none', animation: pulse ? 'pulse 1.5s ease-in-out infinite' : 'none' }} />
  );
}

// ── Packet Viewer ─────────────────────────────────────────────────────────────
function PacketViewer({ packets, onPacketClick, C }) {
  const tbodyRef = useRef(null);
  useEffect(() => {
    if (tbodyRef.current) tbodyRef.current.scrollTop = 0;
  }, [packets]);

  return (
    <Panel title="Live Packet Stream" badge={packets.length} C={C} style={{ gridColumn: 'span 2' }}>
      <div ref={tbodyRef} style={{ overflowY: 'auto', maxHeight: 220, fontFamily: C.mono, fontSize: 11 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ color: C.textDim, borderBottom: `1px solid ${C.border}` }}>
              {['#','Time','Method','Endpoint','Status','Latency','Flags','Src Port','Dst Port','Seq Num','Size'].map(h => (
                <th key={h} style={{ padding: '4px 8px', textAlign: 'left', fontWeight: 500, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {packets.slice(-50).reverse().map((p, i) => {
              const statusColor = p.status_code >= 500 ? C.red : p.status_code >= 400 ? C.orange : C.green;
              const latColor    = p.latency_ms > 500 ? C.red : p.latency_ms > 200 ? C.yellow : C.green;
              const flags = (p.tcp_flags || '').split(',');
              return (
                <tr key={i}
                  onClick={() => onPacketClick && onPacketClick(p)}
                  style={{ borderBottom: `1px solid ${C.border}20`, background: i%2===0 ? 'transparent' : C.rowAlt, cursor: 'pointer', transition: 'background 0.1s' }}
                  onMouseEnter={e => e.currentTarget.style.background = C.rowHover}
                  onMouseLeave={e => e.currentTarget.style.background = i%2===0 ? 'transparent' : C.rowAlt}
                >
                  <td style={{ padding: '3px 8px', color: C.textDim }}>{p.packet_id}</td>
                  <td style={{ padding: '3px 8px', color: C.textDim, whiteSpace: 'nowrap' }}>{ts(p.timestamp)}</td>
                  <td style={{ padding: '3px 8px', color: C.accent }}>{p.method}</td>
                  <td style={{ padding: '3px 8px', color: C.text, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.endpoint}</td>
                  <td style={{ padding: '3px 8px', color: statusColor, fontWeight: 700 }}>{p.status_code || 'TMO'}</td>
                  <td style={{ padding: '3px 8px', color: latColor }}>{p.latency_ms?.toFixed(1)}ms</td>
                  <td style={{ padding: '3px 8px' }}>
                    {flags.map(f => <span key={f} style={{ color: f==='RST'?C.red:f==='SYN'?C.green:f==='PSH'?C.yellow:C.text, marginRight: 3 }}>{f}</span>)}
                  </td>
                  <td style={{ padding: '3px 8px', color: C.textDim }}>{p.src_port}</td>
                  <td style={{ padding: '3px 8px', color: C.textDim }}>{p.dst_port}</td>
                  <td style={{ padding: '3px 8px', color: C.purple }}>{p.seq_num?.toLocaleString()}</td>
                  <td style={{ padding: '3px 8px', color: C.textDim }}>{p.resp_size}B</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {packets.length === 0 && (
          <div style={{ textAlign: 'center', color: C.textDim, padding: 30 }}>Waiting for traffic... Start the traffic generator.</div>
        )}
      </div>
      <div style={{ marginTop: 6, fontFamily: C.mono, fontSize: 9, color: C.textDim, textAlign: 'right' }}>
        Click any row to view full packet structure
      </div>
    </Panel>
  );
}

// ── Metrics Chart ─────────────────────────────────────────────────────────────
function MetricsChart({ metricsHistory, selectedEndpoint, onSelect, C }) {
  const data = metricsHistory[selectedEndpoint] || [];
  const epc  = epColor(selectedEndpoint, C);

  return (
    <Panel title="Metrics Timeline" badge={EP_LABEL[selectedEndpoint]} badgeColor={epc} C={C} style={{ gridColumn: 'span 2' }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {ENDPOINTS.map(ep => (
          <button key={ep} onClick={() => onSelect(ep)} style={{
            padding: '4px 12px', borderRadius: 4,
            border: `1px solid ${selectedEndpoint === ep ? epColor(ep,C) : C.border}`,
            background: selectedEndpoint === ep ? epColor(ep,C) + '22' : 'transparent',
            color: selectedEndpoint === ep ? epColor(ep,C) : C.textDim,
            fontFamily: C.mono, fontSize: 11, cursor: 'pointer',
          }}>{EP_LABEL[ep]}</button>
        ))}
      </div>
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, marginBottom: 4 }}>LATENCY (ms) — adaptive baseline band</div>
        <ResponsiveContainer width="100%" height={120}>
          <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={epc} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={epc} stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={C.dim} stopOpacity={0.4}/>
                <stop offset="95%" stopColor={C.dim} stopOpacity={0.1}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
            <XAxis dataKey="time" tick={{ fill: C.textDim, fontSize: 9, fontFamily: C.mono }} />
            <YAxis tick={{ fill: C.textDim, fontSize: 9, fontFamily: C.mono }} />
            <Tooltip contentStyle={{ background: C.panel, border: `1px solid ${C.border}`, fontFamily: C.mono, fontSize: 11 }} labelStyle={{ color: C.textDim }} />
            <Area type="monotone" dataKey="baseline_upper" stroke="none" fill="url(#bandGrad)" name="Upper Band" />
            <Area type="monotone" dataKey="baseline_lower" stroke="none" fill={C.bg} name="Lower Band" />
            <Line type="monotone" dataKey="baseline" stroke={C.dim} strokeWidth={1} dot={false} strokeDasharray="4 4" name="Baseline" />
            <Area type="monotone" dataKey="latency_ms" stroke={epc} fill="url(#latGrad)" strokeWidth={2} dot={false} name="Latency" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, marginBottom: 4 }}>ERROR RATE %</div>
          <ResponsiveContainer width="100%" height={60}>
            <AreaChart data={data}>
              <Area type="monotone" dataKey="error_rate_pct" stroke={C.red} fill={C.red + '22'} strokeWidth={1.5} dot={false} />
              <YAxis hide domain={[0,'auto']} />
              <Tooltip contentStyle={{ background: C.panel, border: `1px solid ${C.border}`, fontFamily: C.mono, fontSize: 10 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div>
          <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, marginBottom: 4 }}>THROUGHPUT (rps)</div>
          <ResponsiveContainer width="100%" height={60}>
            <AreaChart data={data}>
              <Area type="monotone" dataKey="throughput_rps" stroke={C.purple} fill={C.purple + '22'} strokeWidth={1.5} dot={false} />
              <YAxis hide domain={[0,'auto']} />
              <Tooltip contentStyle={{ background: C.panel, border: `1px solid ${C.border}`, fontFamily: C.mono, fontSize: 10 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Panel>
  );
}

// ── API Health Graph ──────────────────────────────────────────────────────────
function ApiHealthGraph({ graph, C }) {
  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const pos   = { '/auth': {x:120,y:40}, '/payments': {x:40,y:140}, '/inventory': {x:200,y:140} };

  return (
    <Panel title="API Dependency Graph" C={C}>
      <svg width="100%" viewBox="0 0 260 200" style={{ fontFamily: C.mono }}>
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill={C.dim} />
          </marker>
        </defs>
        {edges.map((e, i) => {
          const s = pos[e.source], t = pos[e.target];
          if (!s || !t) return null;
          return <line key={i} x1={s.x} y1={s.y+20} x2={t.x} y2={t.y-10} stroke={C.dim} strokeWidth={1.5} strokeDasharray="4 3" markerEnd="url(#arrow)" />;
        })}
        {nodes.map((n, i) => {
          const p = pos[n.id]; if (!p) return null;
          const isAno = n.status === 'anomalous';
          const color = isAno ? C.red : C.green;
          return (
            <g key={i}>
              <circle cx={p.x} cy={p.y} r={28} fill={color+'15'} stroke={color} strokeWidth={isAno?2:1} />
              {isAno && <circle cx={p.x} cy={p.y} r={32} fill="none" stroke={color} strokeWidth={0.5} opacity={0.4} />}
              <text x={p.x} y={p.y+4} textAnchor="middle" fill={color} fontSize={12} fontWeight={600}>{n.label}</text>
              {isAno && <text x={p.x} y={p.y+46} textAnchor="middle" fill={C.red} fontSize={9}>⚠ ANOMALY</text>}
            </g>
          );
        })}
      </svg>
      <div style={{ display: 'flex', gap: 16, marginTop: 8, justifyContent: 'center' }}>
        <span style={{ fontFamily: C.mono, fontSize: 10, color: C.green }}><Dot color={C.green} /> Healthy</span>
        <span style={{ fontFamily: C.mono, fontSize: 10, color: C.red }}><Dot color={C.red} pulse /> Anomalous</span>
      </div>
    </Panel>
  );
}

// ── Anomaly Alerts ────────────────────────────────────────────────────────────
function AnomalyAlerts({ alerts, C }) {
  const scrollRef = useRef(null);
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = 0; }, [alerts.length]);
  const levelColor = { critical: C.red, warning: C.yellow, normal: C.green };
  const levelIcon  = { critical: '🔴', warning: '🟡', normal: '🟢' };

  return (
    <Panel title="Anomaly Alerts" badge={alerts.length} badgeColor={alerts.length > 0 ? C.red : C.green} C={C}>
      <div ref={scrollRef} style={{ overflowY: 'auto', maxHeight: 260 }}>
        {alerts.length === 0 ? (
          <div style={{ textAlign: 'center', color: C.green, fontFamily: C.mono, fontSize: 12, padding: 20 }}>✓ All systems normal</div>
        ) : (
          alerts.slice(0, 20).map((a, i) => (
            <div key={i} style={{ marginBottom: 8, padding: '8px 12px', borderRadius: 6, border: `1px solid ${levelColor[a.level]||C.yellow}44`, background: (levelColor[a.level]||C.yellow) + '0a' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontFamily: C.mono, fontSize: 11, color: levelColor[a.level], fontWeight: 700 }}>
                  {levelIcon[a.level]} {a.anomaly_type?.toUpperCase().replace('_',' ')}
                </span>
                <span style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim }}>{ts(a.timestamp)}</span>
              </div>
              <div style={{ fontFamily: C.sans, fontSize: 11, color: C.text, marginBottom: 4 }}>{a.description}</div>
              <div style={{ display: 'flex', gap: 12 }}>
                <span style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim }}>Z={a.z_score?.toFixed(2)}</span>
                <span style={{ fontFamily: C.mono, fontSize: 10, color: C.accent }}>{a.endpoint}</span>
                {a.correlated_apis?.length > 0 && (
                  <span style={{ fontFamily: C.mono, fontSize: 10, color: C.orange }}>⟷ {a.correlated_apis.join(', ')}</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </Panel>
  );
}

// ── Severity Gauge ────────────────────────────────────────────────────────────
function SeverityGauge({ severity, C }) {
  const score = severity?.score || 0;
  const sla   = severity?.sla_breach_probability || 0;
  const level = severity?.level || 'normal';
  const trend = severity?.trend || 'stable';
  const color = score >= 7 ? C.red : score >= 4 ? C.yellow : C.green;
  const trendIcon  = { rising: '↑', falling: '↓', stable: '→' }[trend];
  const trendColor = { rising: C.red, falling: C.green, stable: C.textDim }[trend];

  return (
    <Panel title="Severity & SLA" C={C}>
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ fontFamily: C.mono, fontSize: 48, fontWeight: 700, color, lineHeight: 1 }}>{score.toFixed(1)}</div>
        <div style={{ fontFamily: C.sans, fontSize: 11, color: C.textDim }}>/ 10.0</div>
        <div style={{ fontFamily: C.sans, fontSize: 13, color, fontWeight: 600, textTransform: 'uppercase', marginTop: 4 }}>{level}</div>
      </div>
      <div style={{ background: C.dim, borderRadius: 4, height: 8, marginBottom: 12, overflow: 'hidden' }}>
        <div style={{ width: `${(score/10)*100}%`, height: '100%', borderRadius: 4, background: `linear-gradient(90deg, ${C.green}, ${color})`, transition: 'width 0.5s ease', boxShadow: `0 0 8px ${color}` }} />
      </div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, marginBottom: 4 }}>SLA BREACH PROBABILITY</div>
        <div style={{ background: C.dim, borderRadius: 4, height: 6, overflow: 'hidden' }}>
          <div style={{ width: `${sla}%`, height: '100%', borderRadius: 4, background: sla>70?C.red:sla>40?C.orange:C.yellow, transition: 'width 0.5s ease' }} />
        </div>
        <div style={{ fontFamily: C.mono, fontSize: 12, color: sla>70?C.red:C.yellow, marginTop: 4, textAlign: 'right' }}>{sla.toFixed(1)}%</div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: C.mono, fontSize: 11 }}>
        <span style={{ color: C.textDim }}>Trend</span>
        <span style={{ color: trendColor, fontWeight: 700 }}>{trendIcon} {trend.toUpperCase()}</span>
      </div>
      {severity?.primary_metric && severity.primary_metric !== 'none' && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: C.mono, fontSize: 11, marginTop: 6 }}>
          <span style={{ color: C.textDim }}>Driver</span>
          <span style={{ color: C.accent }}>{severity.primary_metric}</span>
        </div>
      )}
    </Panel>
  );
}

// ── Fault Injector with Timer ─────────────────────────────────────────────────
function FaultInjector({ C }) {
  const [selectedApi, setSelectedApi] = useState('payments');
  const [loading, setLoading]         = useState(false);
  // activeFaults: { portKey: { label, endsAt, duration, remaining } }
  const [activeFaults, setActiveFaults] = useState({});
  const timerRef = useRef(null);

  const FAULTS = [
    { id: 'latency_spike', label: 'Latency Spike',  desc: '+1500ms instant',   color: C.orange, payload: { fault:'latency_spike', spike_ms:1500, duration_seconds:60 } },
    { id: 'latency_drift', label: 'Latency Drift',  desc: 'Gradual +30ms/req', color: C.yellow, payload: { fault:'latency_drift', start_ms:50, increment_ms:30, max_ms:2000, duration_seconds:90 } },
    { id: 'error_rate',    label: 'Error Surge',    desc: '60% HTTP 503s',     color: C.red,    payload: { fault:'error_rate', error_pct:60, duration_seconds:60 } },
    { id: 'packet_loss',   label: 'Packet Loss',    desc: '40% dropped',       color: C.red,    payload: { fault:'packet_loss', loss_pct:40, duration_seconds:60 } },
    { id: 'cpu_overload',  label: 'CPU Overload',   desc: 'Random jitter',     color: C.purple, payload: { fault:'cpu_overload', duration_seconds:60 } },
    { id: 'retry_storm',   label: 'Retry Storm',    desc: '60% intermittent',  color: C.orange, payload: { fault:'retry_storm', duration_seconds:45 } },
  ];

  const API_PORTS = { auth:[9001], payments:[9002], inventory:[9003], all:[9001,9002,9003] };

  // Tick countdown every second
  useEffect(() => {
    timerRef.current = setInterval(() => {
      const now = Date.now();
      setActiveFaults(prev => {
        const updated = { ...prev };
        let changed = false;
        for (const key of Object.keys(updated)) {
          const f = updated[key];
          const remaining = Math.max(0, Math.ceil((f.endsAt - now) / 1000));
          if (remaining !== f.remaining) {
            changed = true;
            if (remaining === 0) {
              delete updated[key];  // Auto-expired — remove from UI
            } else {
              updated[key] = { ...f, remaining };
            }
          }
        }
        return changed ? updated : prev;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, []);

  async function injectFault(fault) {
    setLoading(true);
    const ports = API_PORTS[selectedApi] || [9002];
    const now   = Date.now();
    const dur   = fault.payload.duration_seconds;

    for (const port of ports) {
      try {
        await fetch(`http://localhost:${port}/control`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(fault.payload),
        });
        const key = `${port}_${fault.id}`;
        setActiveFaults(prev => ({
          ...prev,
          [key]: { label: fault.label, port, api: selectedApi, color: fault.color, endsAt: now + dur * 1000, duration: dur, remaining: dur }
        }));
      } catch (e) {}
    }
    setLoading(false);
  }

  async function resetAll() {
    setLoading(true);
    for (const port of [9001, 9002, 9003]) {
      try {
        await fetch(`http://localhost:${port}/control`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fault: 'reset' }),
        });
      } catch (e) {}
    }
    setActiveFaults({});  // Clear all timers immediately
    setLoading(false);
  }

  const faultEntries = Object.entries(activeFaults);

  return (
    <Panel title="Fault Injection" badge="DEMO CONTROL" badgeColor={C.orange} C={C}>
      {/* API Selector */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {['auth','payments','inventory','all'].map(api => (
          <button key={api} onClick={() => setSelectedApi(api)} style={{
            flex: 1, padding: '4px 0', borderRadius: 4,
            border: `1px solid ${selectedApi===api ? C.orange : C.border}`,
            background: selectedApi===api ? C.orange+'22' : 'transparent',
            color: selectedApi===api ? C.orange : C.textDim,
            fontFamily: C.mono, fontSize: 10, cursor: 'pointer', textTransform: 'uppercase',
          }}>{api}</button>
        ))}
      </div>

      {/* Fault buttons */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 10 }}>
        {FAULTS.map(fault => (
          <button key={fault.id} onClick={() => injectFault(fault)} disabled={loading} style={{
            padding: '8px 10px', borderRadius: 6, cursor: 'pointer', textAlign: 'left',
            border: `1px solid ${fault.color}66`, background: fault.color + '11',
          }}>
            <div style={{ fontFamily: C.sans, fontSize: 12, fontWeight: 600, color: fault.color }}>{fault.label}</div>
            <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim }}>{fault.desc}</div>
          </button>
        ))}
      </div>

      {/* Active fault timers */}
      {faultEntries.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, letterSpacing: 1, marginBottom: 6 }}>ACTIVE FAULTS</div>
          {faultEntries.map(([key, f]) => {
            const pct = (f.remaining / f.duration) * 100;
            const col = f.remaining < 10 ? C.green : f.remaining < 20 ? C.yellow : f.color;
            return (
              <div key={key} style={{ marginBottom: 6, padding: '6px 8px', borderRadius: 4, border: `1px solid ${f.color}44`, background: f.color + '0a' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontFamily: C.sans, fontSize: 11, fontWeight: 600, color: f.color }}>
                    ⚡ {f.label}
                  </span>
                  <span style={{ fontFamily: C.mono, fontSize: 11, color: col, fontWeight: 700 }}>
                    {f.remaining}s {f.remaining < 10 ? '← expiring' : ''}
                  </span>
                </div>
                <div style={{ background: C.dim, borderRadius: 3, height: 4, overflow: 'hidden' }}>
                  <div style={{ width: `${pct}%`, height: '100%', background: col, transition: 'width 1s linear', borderRadius: 3 }} />
                </div>
                <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, marginTop: 3 }}>
                  Port {f.port} · {f.api} · Auto-off in {f.remaining}s
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Reset */}
      <button onClick={resetAll} disabled={loading} style={{
        width: '100%', padding: '8px', borderRadius: 6,
        border: `1px solid ${C.green}66`, background: C.green + '11',
        color: C.green, fontFamily: C.sans, fontSize: 13, fontWeight: 700, cursor: 'pointer',
      }}>
        ✓ RESET ALL — Restore Normal
      </button>

      {faultEntries.length === 0 && (
        <div style={{ marginTop: 8, fontFamily: C.mono, fontSize: 10, color: C.green, textAlign: 'center' }}>
          ✓ No active faults
        </div>
      )}
    </Panel>
  );
}

// ── Live Metrics Cards ────────────────────────────────────────────────────────
function MetricCards({ liveMetrics, baselines, C }) {
  const METRICS = [
    { key:'latency_ms',     label:'Latency', unit:'ms',  decimals:1, warn:200, crit:500 },
    { key:'error_rate_pct', label:'Errors',  unit:'%',   decimals:1, warn:5,   crit:20  },
    { key:'throughput_rps', label:'RPS',     unit:'rps', decimals:2, warn:null,crit:null },
    { key:'retry_count',    label:'Retries', unit:'',    decimals:0, warn:2,   crit:5   },
  ];
  return (
    <Panel title="Live Metrics — All Endpoints" C={C}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {ENDPOINTS.map(ep => {
          const epc = epColor(ep, C);
          return (
            <div key={ep} style={{ border: `1px solid ${epc}33`, borderRadius: 6, padding: '8px 10px', background: epc + '08' }}>
              <div style={{ fontFamily: C.sans, fontSize: 11, fontWeight: 600, color: epc, marginBottom: 8 }}>{EP_LABEL[ep]}</div>
              {METRICS.map(m => {
                const val = liveMetrics[ep]?.[m.key];
                const isNum = typeof val === 'number';
                const color = !isNum ? C.textDim : m.crit && val > m.crit ? C.red : m.warn && val > m.warn ? C.yellow : C.text;
                return (
                  <div key={m.key} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim }}>{m.label}</span>
                    <span style={{ fontFamily: C.mono, fontSize: 10, color, fontWeight: color!==C.text?700:400 }}>
                      {isNum ? val.toFixed(m.decimals) + m.unit : '—'}
                    </span>
                  </div>
                );
              })}
              <div style={{ marginTop: 6, borderTop: `1px solid ${C.border}`, paddingTop: 4 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim }}>Baseline</span>
                  <span style={{ fontFamily: C.mono, fontSize: 10, color: baselines[ep]?.is_ready ? C.green : C.yellow }}>
                    {baselines[ep]?.is_ready ? '✓ READY' : '⟳ LEARNING'}
                  </span>
                </div>
                {baselines[ep]?.metrics?.latency_ms && (
                  <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, marginTop: 2 }}>
                    lat μ={baselines[ep].metrics.latency_ms.baseline?.toFixed(1)}ms ±{baselines[ep].metrics.latency_ms.std?.toFixed(1)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

// ── Sniffer Panel ─────────────────────────────────────────────────────────────
function SnifferPanel({ snifferPackets, onPacketClick, C }) {
  return (
    <Panel title="⚡ BONUS — Real-World Packet Capture" badge="LIVE NETWORK" badgeColor={C.purple} C={C} style={{ gridColumn: 'span 3' }}>
      <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, marginBottom: 8 }}>
        Run <span style={{ color: C.accent }}>python bonus/live_sniffer.py --iface "Wi-Fi" --filter "tcp or udp"</span> as Administrator.
        Click any row to see packet structure.
      </div>
      <div style={{ overflowX: 'auto', maxHeight: 160, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: C.mono, fontSize: 11 }}>
          <thead>
            <tr style={{ color: C.textDim, borderBottom: `1px solid ${C.border}` }}>
              {['#','Time','Protocol','Src IP','→','Dst IP','Flags','TTL','IP Len','Payload'].map(h => (
                <th key={h} style={{ padding: '3px 8px', textAlign: 'left', whiteSpace: 'nowrap', fontWeight: 500 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {snifferPackets.slice(-30).reverse().map((p, i) => (
              <tr key={i}
                onClick={() => onPacketClick && onPacketClick(p)}
                style={{ borderBottom: `1px solid ${C.border}20`, background: i%2===0?'transparent':C.rowAlt, cursor:'pointer', transition:'background 0.1s' }}
                onMouseEnter={e => e.currentTarget.style.background = C.purple + '22'}
                onMouseLeave={e => e.currentTarget.style.background = i%2===0?'transparent':C.rowAlt}
              >
                <td style={{ padding:'2px 8px', color:C.textDim }}>{p.packet_id}</td>
                <td style={{ padding:'2px 8px', color:C.textDim, whiteSpace:'nowrap' }}>{ts(p.timestamp)}</td>
                <td style={{ padding:'2px 8px', color:C.purple, fontWeight:700 }}>{p.protocol}</td>
                <td style={{ padding:'2px 8px', color:C.accent }}>{p.src_ip}</td>
                <td style={{ padding:'2px 8px', color:C.dim }}>→</td>
                <td style={{ padding:'2px 8px', color:C.green }}>{p.dst_ip}</td>
                <td style={{ padding:'2px 8px', color:C.yellow }}>{p.tcp_flags||'—'}</td>
                <td style={{ padding:'2px 8px', color:C.textDim }}>{p.ttl}</td>
                <td style={{ padding:'2px 8px', color:C.textDim }}>{p.ip_length}B</td>
                <td style={{ padding:'2px 8px', color:C.text }}>{p.payload_size}B</td>
              </tr>
            ))}
          </tbody>
        </table>
        {snifferPackets.length === 0 && (
          <div style={{ textAlign:'center', color:C.textDim, padding:20 }}>No real-world packets yet. Start the sniffer script above.</div>
        )}
      </div>
    </Panel>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [darkMode, setDarkMode]         = useState(true);
  const [connected, setConnected]       = useState(false);
  const [packets, setPackets]           = useState([]);
  const [snifferPackets, setSnifferPkts]= useState([]);
  const [metricsHistory, setMetHistory] = useState({ '/auth':[], '/payments':[], '/inventory':[] });
  const [liveMetrics, setLiveMetrics]   = useState({});
  const [baselines, setBaselines]       = useState({});
  const [alerts, setAlerts]             = useState([]);
  const [severity, setSeverity]         = useState(null);
  const [graph, setGraph]               = useState({ nodes:[], edges:[] });
  const [selectedEp, setSelectedEp]     = useState('/payments');
  const [uptime, setUptime]             = useState(0);
  const [totalPackets, setTotalPkts]    = useState(0);
  const [showSniffer, setShowSniffer]   = useState(false);
  const [selectedPacket, setSelectedPacket] = useState(null);

  const C = darkMode ? DARK : LIGHT;

  useEffect(() => {
    wsManager.connect(setConnected);
    const unsubs = [
      wsManager.on('packet', (data) => {
        setPackets(prev => [...prev.slice(-200), data]);
        setTotalPkts(prev => prev + 1);
      }),
      wsManager.on('metrics', (data) => {
        const ep = data.endpoint;
        const m  = data.metrics;
        const bl = data.baselines;
        const point = {
          time: new Date().toLocaleTimeString('en', { hour12: false }),
          latency_ms: m.latency_ms,
          error_rate_pct: (m.error_rate * 100).toFixed(2),
          throughput_rps: m.throughput_rps,
          retry_count: m.retry_count,
          baseline: bl?.latency_ms?.baseline || 0,
          baseline_upper: bl?.latency_ms?.upper_band || 0,
          baseline_lower: bl?.latency_ms?.lower_band || 0,
        };
        setMetHistory(prev => ({ ...prev, [ep]: [...(prev[ep]||[]).slice(-60), point] }));
        setLiveMetrics(prev => ({ ...prev, [ep]: { latency_ms: m.latency_ms, error_rate_pct: m.error_rate*100, throughput_rps: m.throughput_rps, retry_count: m.retry_count } }));
        if (bl) setBaselines(prev => ({ ...prev, [ep]: { is_ready: data.baseline_ready, metrics: bl } }));
      }),
      wsManager.on('anomaly',   (data) => setAlerts(prev => [data, ...prev].slice(0, 50))),
      wsManager.on('severity',  (data) => setSeverity(data)),
      wsManager.on('graph',     (data) => setGraph(data)),
      wsManager.on('system',    (data) => {
        if (data.uptime_seconds)   setUptime(data.uptime_seconds);
        if (data.packets_captured) setTotalPkts(data.packets_captured);
      }),
      wsManager.on('sniffer', (data) => {
        if (data.packets) setSnifferPkts(prev => [...prev.slice(-300), ...data.packets]);
        else              setSnifferPkts(prev => [...prev.slice(-300), data]);
      }),
    ];
    return () => unsubs.forEach(u => u && u());
  }, []);

  const severityScore = severity?.score || 0;
  const statusColor   = severityScore >= 7 ? C.red : severityScore >= 4 ? C.yellow : C.green;

  return (
    <div style={{ background: C.bg, minHeight: '100vh', color: C.text, fontFamily: C.sans }}>
      <style>{`
        * { box-sizing: border-box; }
        button { transition: all 0.15s ease; }
        button:hover:not(:disabled) { opacity: 0.85; transform: translateY(-1px); }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${C.scrollThumb}; border-radius: 2px; }
      `}</style>

      {/* Packet Structure Modal */}
      {selectedPacket && (
        <PacketStructureModal packet={selectedPacket} onClose={() => setSelectedPacket(null)} darkMode={darkMode} />
      )}

      {/* ── Header ── */}
      <div style={{ padding: '10px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${C.border}`, background: C.headerBg, position: 'sticky', top: 0, zIndex: 100 }}>
        <div>
          <div style={{ fontFamily: C.sans, fontWeight: 700, fontSize: 14, letterSpacing: 1, color: C.accent }}>ANOMALY DETECTION SYSTEM</div>
          <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim }}>Packet-Level API Traffic Analysis · VIT TYA13</div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {/* Severity pill */}
          <div style={{ padding: '4px 16px', borderRadius: 20, border: `1px solid ${statusColor}66`, background: statusColor+'15', fontFamily: C.mono, fontSize: 12, color: statusColor, fontWeight: 700 }}>
            SEV {severityScore.toFixed(1)} / 10
          </div>

          {/* Stats */}
          <div style={{ fontFamily: C.mono, fontSize: 11, color: C.textDim }}>
            <span style={{ color: C.text }}>{totalPackets}</span> pkts · <span style={{ color: C.text }}>{uptime.toFixed(0)}s</span> uptime
          </div>

          {/* Connection */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Dot color={connected ? C.green : C.red} pulse={connected} />
            <span style={{ fontFamily: C.mono, fontSize: 11, color: connected ? C.green : C.red }}>
              {connected ? 'LIVE' : 'CONNECTING...'}
            </span>
          </div>

          {/* Sniffer toggle */}
          <button onClick={() => setShowSniffer(s => !s)} style={{ padding: '4px 12px', borderRadius: 4, cursor: 'pointer', border: `1px solid ${C.purple}66`, background: showSniffer ? C.purple+'22' : 'transparent', color: C.purple, fontFamily: C.mono, fontSize: 11 }}>
            {showSniffer ? '⚡ Hide Sniffer' : '⚡ Show Sniffer'}
          </button>

          {/* Light / Dark toggle */}
          <button onClick={() => setDarkMode(d => !d)} style={{ padding: '4px 12px', borderRadius: 4, cursor: 'pointer', border: `1px solid ${C.border}`, background: 'transparent', color: C.text, fontFamily: C.mono, fontSize: 11 }}>
            {darkMode ? '☀ Light' : '🌙 Dark'}
          </button>
        </div>
      </div>

      {/* ── Main Grid ── */}
      <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr 1fr 300px', gap: 12 }}>

        <div style={{ gridColumn: 'span 2' }}>
          <PacketViewer packets={packets} onPacketClick={setSelectedPacket} C={C} />
        </div>
        <SeverityGauge severity={severity} C={C} />

        <div style={{ gridColumn: 'span 2' }}>
          <MetricsChart metricsHistory={metricsHistory} selectedEndpoint={selectedEp} onSelect={setSelectedEp} C={C} />
        </div>
        <ApiHealthGraph graph={graph} C={C} />

        <div style={{ gridColumn: 'span 3' }}>
          <MetricCards liveMetrics={liveMetrics} baselines={baselines} C={C} />
        </div>

        <div style={{ gridColumn: 'span 2' }}>
          <AnomalyAlerts alerts={alerts} C={C} />
        </div>
        <FaultInjector C={C} />

        {showSniffer && (
          <div style={{ gridColumn: 'span 3' }}>
            <SnifferPanel snifferPackets={snifferPackets} onPacketClick={setSelectedPacket} C={C} />
          </div>
        )}
      </div>
    </div>
  );
}
