import React, { useState, useEffect } from 'react';

// ── Colour palette (matches App.js) ──────────────────────────────────────────
const DARK_M = {
  bg:      '#050d1a', panel:   '#0a1628', border:  '#0d2040', borderHi: '#1a4080',
  accent:  '#00d4ff', green:   '#00ff88', yellow:  '#ffd600', red:      '#ff3366',
  orange:  '#ff7c00', purple:  '#9d4edd', teal:    '#00e5cc', pink:     '#ff6eb4',
  dim:     '#0d2040', text:    '#c8e0ff', textDim: '#4a6080',
  mono: "'JetBrains Mono', monospace", sans: "'Space Grotesk', sans-serif",
  tabActive: '#0a1628', tabInactive: '#030a14', headerBg: '#030a14', panelHd: '#071020',
  codeBg: '#1A1A2E', codeText: '#00FF88',
};

const LIGHT_M = {
  bg:      '#f0f4fa', panel:   '#ffffff', border:  '#d0ddf0', borderHi: '#4a80c0',
  accent:  '#0066cc', green:   '#00994d', yellow:  '#b38600', red:      '#cc1144',
  orange:  '#cc5500', purple:  '#6a1fb5', teal:    '#007a6e', pink:     '#cc3388',
  dim:     '#c0cfe0', text:    '#1a2a3a', textDim: '#6a80a0',
  mono: "'JetBrains Mono', monospace", sans: "'Space Grotesk', sans-serif",
  tabActive: '#ffffff', tabInactive: '#eef2fa', headerBg: '#1e3a5f', panelHd: '#f8faff',
  codeBg: '#f0f4fa', codeText: '#006600',
};

// Module-level theme reference — set by PacketStructureModal before any render
let C = DARK_M;

// ── Field color assignments by layer ─────────────────────────────────────────
// Theme-aware field colors (functions so they read current C at render time)
const IP_COLOR  = () => C.bg === '#050d1a' ? '#1a3a6a' : '#dce8f8';
const TCP_COLOR = () => C.bg === '#050d1a' ? '#1a2a5a' : '#d8e4f4';
const UDP_COLOR = () => C.bg === '#050d1a' ? '#1a4a3a' : '#d4f0e8';
const FLAG_ON   = () => C.red;
const FLAG_OFF  = () => C.bg === '#050d1a' ? '#1a2040' : '#e8eef8';

// ── Bit ruler ─────────────────────────────────────────────────────────────────
function BitRuler() {
  return (
    <div style={{ display: 'flex', marginBottom: 2, paddingLeft: 80 }}>
      {Array.from({ length: 32 }, (_, i) => (
        <div key={i} style={{
          flex: 1, textAlign: 'center',
          fontFamily: C.mono, fontSize: 8,
          color: i % 8 === 0 ? C.accent : C.textDim,
          borderLeft: i % 8 === 0 ? `1px solid ${C.accent}44` : 'none',
          paddingBottom: 2,
        }}>{i}</div>
      ))}
    </div>
  );
}

// ── Single header row ─────────────────────────────────────────────────────────
// fields: [{ label, bits, value, color, description }]
function HeaderRow({ rowLabel, fields, totalBits = 32 }) {
  const [hovered, setHovered] = useState(null);

  return (
    <div style={{ display: 'flex', alignItems: 'stretch', marginBottom: 2 }}>
      {/* Row label */}
      <div style={{
        width: 80, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
        paddingRight: 8,
        fontFamily: C.mono, fontSize: 9, color: C.textDim,
      }}>{rowLabel}</div>

      {/* Fields */}
      <div style={{ flex: 1, display: 'flex' }}>
        {fields.map((field, i) => {
          const widthPct = (field.bits / totalBits) * 100;
          const isHovered = hovered === i;
          return (
            <div
              key={i}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
              title={field.description || field.label}
              style={{
                width: `${widthPct}%`,
                minHeight: 44,
                background: isHovered
                  ? (field.color || IP_COLOR) + 'dd'
                  : (field.color || IP_COLOR) + '99',
                border: `1px solid ${isHovered ? C.accent : C.border}`,
                borderRadius: 3,
                margin: '0 1px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '2px 3px',
                cursor: 'default',
                transition: 'all 0.15s ease',
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              {/* Bit count badge */}
              <div style={{
                position: 'absolute', top: 2, right: 3,
                fontFamily: C.mono, fontSize: 7, color: C.textDim,
              }}>{field.bits}b</div>

              {/* Field name */}
              <div style={{
                fontFamily: C.mono, fontSize: field.bits <= 4 ? 7 : field.bits <= 8 ? 8 : 9,
                color: C.text, fontWeight: 600, textAlign: 'center',
                lineHeight: 1.2, wordBreak: 'break-all',
              }}>{field.label}</div>

              {/* Field value */}
              {field.value !== undefined && field.value !== null && (
                <div style={{
                  fontFamily: C.mono,
                  fontSize: field.bits <= 4 ? 7 : 9,
                  color: field.highlight ? C.yellow : C.accent,
                  marginTop: 2, textAlign: 'center',
                  wordBreak: 'break-all',
                }}>{field.value}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── TCP Flags row ─────────────────────────────────────────────────────────────
function TCPFlagsRow({ flagsStr }) {
  const flagList = ['CWR','ECE','URG','ACK','PSH','RST','SYN','FIN'];
  const activeFlags = (flagsStr || '').split(',').map(f => f.trim().toUpperCase());

  return (
    <div style={{ marginTop: 12, marginBottom: 12 }}>
      <div style={{
        fontFamily: C.mono, fontSize: 10, color: C.textDim,
        marginBottom: 6, letterSpacing: 1,
      }}>TCP CONTROL FLAGS — DECODED</div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {flagList.map(flag => {
          const active = activeFlags.includes(flag);
          const descriptions = {
            SYN: 'Synchronize — initiates connection',
            ACK: 'Acknowledgment — confirms receipt',
            PSH: 'Push — deliver data immediately',
            FIN: 'Finish — terminates connection',
            RST: 'Reset — aborts connection',
            URG: 'Urgent — urgent data present',
            ECE: 'ECN Echo — congestion notification',
            CWR: 'Congestion Window Reduced',
          };
          return (
            <div key={flag} title={descriptions[flag]} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              padding: '6px 10px', borderRadius: 4,
              border: `1px solid ${active ? FLAG_ON() : C.border}`,
              background: active ? FLAG_ON + '22' : FLAG_OFF,
              minWidth: 52,
            }}>
              <div style={{
                fontFamily: C.mono, fontSize: 16, fontWeight: 700,
                color: active ? FLAG_ON : C.textDim,
              }}>{active ? '1' : '0'}</div>
              <div style={{
                fontFamily: C.mono, fontSize: 9,
                color: active ? FLAG_ON : C.textDim,
                marginTop: 2,
              }}>{flag}</div>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {activeFlags.filter(f => flagList.includes(f)).map(flag => {
          const descriptions = {
            SYN: 'Initiating new TCP connection',
            ACK: 'Acknowledgment number is valid',
            PSH: 'Receiver should pass data to application immediately',
            FIN: 'Sender has finished sending data',
            RST: 'Connection is being forcibly reset',
            URG: 'Urgent pointer field is significant',
            ECE: 'ECN-Echo: peer is ECN capable',
            CWR: 'Sender reduced congestion window',
          };
          return (
            <div key={flag} style={{
              fontFamily: C.sans, fontSize: 11,
              color: C.text, padding: '3px 10px',
              background: FLAG_ON() + '15',
              border: `1px solid ${FLAG_ON()}44`,
              borderRadius: 4,
            }}>
              <span style={{ color: FLAG_ON(), fontWeight: 700 }}>{flag}</span>
              {' — '}{descriptions[flag]}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── IP Header visualization ───────────────────────────────────────────────────
function IPHeader({ packet }) {
  const protocol_num = packet.protocol?.includes('TCP') ? 6
    : packet.protocol?.includes('UDP') ? 17
    : packet.protocol?.includes('ICMP') ? 1
    : 6;

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontFamily: C.mono, fontSize: 11, color: C.accent,
        letterSpacing: 2, marginBottom: 8, paddingBottom: 4,
        borderBottom: `1px solid ${C.accent}33`,
      }}>
        ▸ INTERNET PROTOCOL (IP) HEADER — IPv{packet.ip_version || 4} — RFC 791
      </div>
      <BitRuler />

      {/* Row 1: Version | IHL | DSCP | Total Length */}
      <HeaderRow rowLabel="bits 0–31" fields={[
        { label: 'Ver', bits: 4, value: packet.ip_version || 4, color: IP_COLOR(), description: 'IP Version (4=IPv4)' },
        { label: 'IHL', bits: 4, value: '5', color: IP_COLOR(), description: 'Internet Header Length (5×4=20 bytes)' },
        { label: 'DSCP / ECN', bits: 8, value: '0x00', color: IP_COLOR(), description: 'Differentiated Services / ECN bits' },
        { label: 'Total Length', bits: 16, value: packet.ip_length || (packet.resp_size + 20) || 0, color: IP_COLOR(), highlight: true, description: 'Total packet size in bytes including header' },
      ]} />

      {/* Row 2: Identification | Flags | Fragment Offset */}
      <HeaderRow rowLabel="bits 32–63" fields={[
        { label: 'Identification', bits: 16, value: `0x${(packet.seq_num || 0).toString(16).slice(-4).toUpperCase()}`, color: IP_COLOR(), description: 'Unique ID for fragment reassembly' },
        { label: 'Flg', bits: 3, value: 'DF', color: IP_COLOR(), description: 'Flags: DF=Don\'t Fragment' },
        { label: 'Fragment Offset', bits: 13, value: '0', color: IP_COLOR(), description: 'Position of this fragment (0 = not fragmented)' },
      ]} />

      {/* Row 3: TTL | Protocol | Header Checksum */}
      <HeaderRow rowLabel="bits 64–95" fields={[
        { label: 'TTL', bits: 8, value: packet.ttl || 64, color: UDP_COLOR(), highlight: true, description: 'Time To Live — hops remaining before discard' },
        { label: 'Protocol', bits: 8, value: `${protocol_num} (${packet.protocol?.includes('UDP') ? 'UDP' : 'TCP'})`, color: IP_COLOR(), highlight: true, description: `Protocol number: 6=TCP, 17=UDP, 1=ICMP` },
        { label: 'Header Checksum', bits: 16, value: '0xB861', color: IP_COLOR(), description: 'Error detection checksum for IP header' },
      ]} />

      {/* Row 4: Source IP */}
      <HeaderRow rowLabel="bits 96–127" fields={[
        { label: `Source IP Address — ${packet.src_ip || '127.0.0.1'}`, bits: 32, value: packet.src_ip || '127.0.0.1', color: IP_COLOR(), highlight: true, description: 'Origin IP address (32 bits = 4 octets)' },
      ]} />

      {/* Row 5: Destination IP */}
      <HeaderRow rowLabel="bits 128–159" fields={[
        { label: `Destination IP Address — ${packet.dst_ip || '127.0.0.1'}`, bits: 32, value: packet.dst_ip || '127.0.0.1', color: IP_COLOR(), highlight: true, description: 'Destination IP address (32 bits = 4 octets)' },
      ]} />
    </div>
  );
}

// ── TCP Header visualization ──────────────────────────────────────────────────
function TCPHeader({ packet }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontFamily: C.mono, fontSize: 11, color: C.green,
        letterSpacing: 2, marginBottom: 8, paddingBottom: 4,
        borderBottom: `1px solid ${C.green}33`,
      }}>
        ▸ TRANSMISSION CONTROL PROTOCOL (TCP) HEADER — RFC 793
      </div>
      <BitRuler />

      {/* Row 1: Src Port | Dst Port */}
      <HeaderRow rowLabel="bits 0–31" fields={[
        { label: 'Source Port', bits: 16, value: packet.src_port, color: IP_COLOR(), highlight: true, description: 'Ephemeral source port (49152–65535 for client)' },
        { label: 'Destination Port', bits: 16, value: packet.dst_port, color: IP_COLOR(), highlight: true, description: 'Service port (9001=Auth, 9002=Payments, 9003=Inventory, 443=HTTPS)' },
      ]} />

      {/* Row 2: Sequence Number */}
      <HeaderRow rowLabel="bits 32–63" fields={[
        { label: 'Sequence Number', bits: 32, value: packet.seq_num?.toLocaleString(), color: IP_COLOR(), highlight: true, description: 'Position of first data byte in this segment' },
      ]} />

      {/* Row 3: Acknowledgment Number */}
      <HeaderRow rowLabel="bits 64–95" fields={[
        { label: 'Acknowledgment Number', bits: 32, value: packet.ack_num?.toLocaleString(), color: TCP_COLOR(), highlight: true, description: 'Next expected sequence number from sender' },
      ]} />

      {/* Row 4: Data Offset | Reserved | Flags | Window */}
      <HeaderRow rowLabel="bits 96–127" fields={[
        { label: 'Offset', bits: 4, value: '5', color: IP_COLOR(), description: 'Data offset: header length in 32-bit words (5×4=20 bytes)' },
        { label: 'Res', bits: 3, value: '000', color: TCP_COLOR(), description: 'Reserved — must be zero' },
        { label: 'CWR', bits: 1, value: (packet.tcp_flags||'').includes('CWR')?'1':'0', color: (packet.tcp_flags||'').includes('CWR')?'#ff336633':'#1a2a4a', description: 'Congestion Window Reduced' },
        { label: 'ECE', bits: 1, value: (packet.tcp_flags||'').includes('ECE')?'1':'0', color: TCP_COLOR(), description: 'ECN Echo' },
        { label: 'URG', bits: 1, value: (packet.tcp_flags||'').includes('URG')?'1':'0', color: TCP_COLOR(), description: 'Urgent pointer significant' },
        { label: 'ACK', bits: 1, value: (packet.tcp_flags||'').includes('ACK')?'1':'0', color: (packet.tcp_flags||'').includes('ACK')?'#00ff8833':'#1a2a4a', description: 'Acknowledgment field significant' },
        { label: 'PSH', bits: 1, value: (packet.tcp_flags||'').includes('PSH')?'1':'0', color: (packet.tcp_flags||'').includes('PSH')?'#ffd60033':'#1a2a4a', description: 'Push function — deliver data immediately' },
        { label: 'RST', bits: 1, value: (packet.tcp_flags||'').includes('RST')?'1':'0', color: (packet.tcp_flags||'').includes('RST')?'#ff336633':'#1a2a4a', description: 'Reset connection' },
        { label: 'SYN', bits: 1, value: (packet.tcp_flags||'').includes('SYN')?'1':'0', color: (packet.tcp_flags||'').includes('SYN')?'#00d4ff33':'#1a2a4a', description: 'Synchronize sequence numbers' },
        { label: 'FIN', bits: 1, value: (packet.tcp_flags||'').includes('FIN')?'1':'0', color: TCP_COLOR(), description: 'No more data from sender' },
        { label: 'Window Size', bits: 16, value: (packet.window_size || 65535).toLocaleString(), color: IP_COLOR(), highlight: true, description: 'Receive buffer size — flow control' },
      ]} />

      {/* Row 5: Checksum | Urgent Pointer */}
      <HeaderRow rowLabel="bits 128–159" fields={[
        { label: 'Checksum', bits: 16, value: '0xA4C2', color: IP_COLOR(), description: 'Error detection for TCP header + data' },
        { label: 'Urgent Pointer', bits: 16, value: '0x0000', color: TCP_COLOR(), description: 'Points to urgent data (only valid if URG flag set)' },
      ]} />

      {/* Flags decoded */}
      <TCPFlagsRow flagsStr={packet.tcp_flags} />
    </div>
  );
}

// ── UDP Header visualization ──────────────────────────────────────────────────
function UDPHeader({ packet }) {
  const udpLen = (packet.payload_size || packet.resp_size || 0) + 8;
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontFamily: C.mono, fontSize: 11, color: C.teal,
        letterSpacing: 2, marginBottom: 8, paddingBottom: 4,
        borderBottom: `1px solid ${C.teal}33`,
      }}>
        ▸ USER DATAGRAM PROTOCOL (UDP) HEADER — RFC 768
      </div>
      <BitRuler />

      {/* Row 1: Src Port | Dst Port */}
      <HeaderRow rowLabel="bits 0–31" fields={[
        { label: 'Source Port', bits: 16, value: packet.src_port, color: UDP_COLOR(), highlight: true, description: 'Source port number' },
        { label: 'Destination Port', bits: 16, value: packet.dst_port, color: UDP_COLOR(), highlight: true, description: 'Destination port number' },
      ]} />

      {/* Row 2: Length | Checksum */}
      <HeaderRow rowLabel="bits 32–63" fields={[
        { label: 'Length', bits: 16, value: `${udpLen} bytes`, color: UDP_COLOR(), highlight: true, description: 'Length of UDP header + data in bytes (minimum 8)' },
        { label: 'Checksum', bits: 16, value: '0xD4E1', color: UDP_COLOR(), description: 'Optional error detection (0 = disabled)' },
      ]} />

      <div style={{
        marginTop: 10, padding: '8px 12px',
        background: C.teal + '11', border: `1px solid ${C.teal}33`,
        borderRadius: 4, fontFamily: C.sans, fontSize: 11, color: C.text,
      }}>
        <span style={{ color: C.teal, fontWeight: 700 }}>UDP Note: </span>
        UDP has no connection establishment (no SYN/ACK), no sequencing, no retransmission.
        It is connectionless and faster — used for DNS, QUIC (YouTube/HTTP3), streaming.
        {packet.protocol?.includes('QUIC') && (
          <span style={{ color: C.yellow }}> This packet uses QUIC over UDP — Google's transport for YouTube.</span>
        )}
      </div>
    </div>
  );
}

// ── Application layer note ────────────────────────────────────────────────────
function AppLayerNote({ packet }) {
  const proto = (packet.protocol || '').toUpperCase();
  const isHTTPS = proto.includes('HTTPS') || proto.includes('TLS') || packet.dst_port === 443;
  const isHTTP  = proto.includes('HTTP') && !isHTTPS;
  const isDNS   = proto.includes('DNS') || packet.dst_port === 53;
  const isQUIC  = proto.includes('QUIC');

  let note = null;

  if (isHTTPS) {
    note = {
      color: C.purple,
      title: 'TLS / HTTPS APPLICATION LAYER',
      text: 'Application data is encrypted by TLS 1.3. The TCP payload contains encrypted ciphertext — cannot be read without the session keys. This is normal for all HTTPS traffic (YouTube, banking, APIs).',
      fields: [
        { label: 'Content Type', value: '23 (Application Data)' },
        { label: 'TLS Version', value: '0x0303 (TLS 1.3)' },
        { label: 'Payload', value: '[ENCRYPTED]' },
      ]
    };
  } else if (isQUIC) {
    note = {
      color: C.yellow,
      title: 'QUIC APPLICATION LAYER (HTTP/3)',
      text: 'QUIC is Google\'s transport protocol running over UDP. Used by YouTube for faster video streaming. Combines TLS encryption with transport in a single layer.',
      fields: [
        { label: 'Header Form', value: '0 (Short Header)' },
        { label: 'Payload', value: '[QUIC ENCRYPTED]' },
      ]
    };
  } else if (isDNS) {
    note = {
      color: C.yellow,
      title: 'DNS APPLICATION LAYER',
      text: 'Domain Name System query/response. Resolves domain names to IP addresses.',
      fields: [
        { label: 'Type', value: packet.dst_port === 53 ? 'Query →' : '← Response' },
      ]
    };
  } else if (isHTTP) {
    note = {
      color: C.green,
      title: 'HTTP/1.1 APPLICATION LAYER',
      text: 'Plaintext HTTP — our API proxy traffic. Full request/response visible.',
      fields: [
        { label: 'Method', value: packet.method || 'GET' },
        { label: 'Endpoint', value: packet.endpoint || '/' },
        { label: 'Status', value: packet.status_code || 200 },
        { label: 'Payload Size', value: `${packet.resp_size || 0} bytes` },
      ]
    };
  }

  if (!note) return null;

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        fontFamily: C.mono, fontSize: 11, color: note.color,
        letterSpacing: 2, marginBottom: 8, paddingBottom: 4,
        borderBottom: `1px solid ${note.color}33`,
      }}>
        ▸ {note.title}
      </div>
      <div style={{
        padding: '10px 14px',
        background: note.color + '0f',
        border: `1px solid ${note.color}33`,
        borderRadius: 4,
      }}>
        <div style={{ fontFamily: C.sans, fontSize: 12, color: C.text, marginBottom: 8 }}>
          {note.text}
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {note.fields.map((f, i) => (
            <div key={i} style={{ fontFamily: C.mono, fontSize: 11 }}>
              <span style={{ color: C.textDim }}>{f.label}: </span>
              <span style={{ color: note.color, fontWeight: 700 }}>{f.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Packet summary bar ────────────────────────────────────────────────────────
function PacketSummary({ packet }) {
  const proto = packet.protocol || 'TCP/HTTP';
  const protoColor = proto.includes('HTTPS') || proto.includes('TLS') ? C.purple
    : proto.includes('UDP') || proto.includes('QUIC') ? C.teal
    : proto.includes('DNS') ? C.yellow
    : C.green;

  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: 16,
      padding: '10px 14px', marginBottom: 20,
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 6, fontFamily: C.mono, fontSize: 11,
    }}>
      {[
        { label: 'Packet #',   value: packet.packet_id,                            color: C.accent },
        { label: 'Protocol',   value: proto,                                        color: protoColor },
        { label: 'Src',        value: `${packet.src_ip}:${packet.src_port}`,        color: C.text },
        { label: 'Dst',        value: `${packet.dst_ip || '127.0.0.1'}:${packet.dst_port}`, color: C.text },
        { label: 'Flags',      value: packet.tcp_flags || '—',                     color: C.yellow },
        { label: 'TTL',        value: packet.ttl || 64,                             color: C.textDim },
        { label: 'Latency',    value: packet.latency_ms ? `${packet.latency_ms.toFixed(1)}ms` : '—', color: packet.latency_ms > 500 ? C.red : C.green },
        { label: 'Payload',    value: `${packet.resp_size || packet.payload_size || 0}B`, color: C.textDim },
      ].map(({ label, value, color }) => (
        <div key={label}>
          <span style={{ color: C.textDim }}>{label}: </span>
          <span style={{ color, fontWeight: 600 }}>{value}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main Modal ────────────────────────────────────────────────────────────────
export default function PacketStructureModal({ packet, onClose, darkMode = true }) {
  // Set module-level C so all sub-components pick up the right theme
  C = darkMode ? DARK_M : LIGHT_M;
  const [activeTab, setActiveTab] = useState('structure');

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  if (!packet) return null;

  const proto = (packet.protocol || '').toUpperCase();
  const isUDP = proto.includes('UDP') || proto.includes('QUIC') || proto.includes('DNS');
  const source = packet.source === 'real_capture' ? 'REAL CAPTURE' : 'PROXY CAPTURE';
  const sourceColor = packet.source === 'real_capture' ? C.purple : C.green;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: '#000000cc',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        backdropFilter: 'blur(4px)',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '92vw', maxWidth: 1100, maxHeight: '90vh',
          background: C.bg,
          border: `1px solid ${C.borderHi || '#1a4080'}`,
          borderRadius: 10, overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
          boxShadow: `0 0 60px ${C.accent}22`,
        }}
      >
        {/* Modal Header */}
        <div style={{
          padding: '12px 20px',
          background: C.headerBg,
          borderBottom: `1px solid ${C.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ fontFamily: C.sans, fontWeight: 700, fontSize: 14, color: C.accent }}>
              PACKET STRUCTURE ANALYSIS
            </div>
            <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, marginTop: 2 }}>
              <span style={{ color: sourceColor, fontWeight: 700 }}>[{source}]</span>
              {' '}Packet #{packet.packet_id} · {new Date((packet.timestamp || 0) * 1000).toLocaleTimeString()} · {packet.protocol}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim }}>
              Press ESC or click outside to close
            </div>
            <button onClick={onClose} style={{
              background: 'none', border: `1px solid ${C.border}`,
              color: C.text, borderRadius: 4, padding: '4px 12px',
              cursor: 'pointer', fontFamily: C.mono, fontSize: 12,
            }}>✕ Close</button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex', gap: 0,
          borderBottom: `1px solid ${C.border}`,
          background: C.panelHd || C.headerBg,
        }}>
          {[
            { id: 'structure', label: 'Packet Structure' },
            { id: 'hex',       label: 'Hex View' },
            { id: 'about',     label: 'Protocol Info' },
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
              padding: '10px 20px',
              background: activeTab === tab.id ? C.tabActive : C.tabInactive,
              border: 'none',
              borderBottom: activeTab === tab.id ? `2px solid ${C.accent}` : '2px solid transparent',
              color: activeTab === tab.id ? C.accent : C.textDim,
              fontFamily: C.mono, fontSize: 11, cursor: 'pointer',
              letterSpacing: 1,
            }}>{tab.label}</button>
          ))}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>

          {activeTab === 'structure' && (
            <div>
              <PacketSummary packet={packet} />
              <IPHeader packet={packet} />
              {isUDP ? <UDPHeader packet={packet} /> : <TCPHeader packet={packet} />}
              <AppLayerNote packet={packet} />
            </div>
          )}

          {activeTab === 'hex' && (
            <HexView packet={packet} />
          )}

          {activeTab === 'about' && (
            <ProtocolInfo packet={packet} isUDP={isUDP} />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Hex View ──────────────────────────────────────────────────────────────────
function HexView({ packet }) {
  // Simulate hex dump of IP+TCP headers from available fields
  const srcPort  = packet.src_port  || 0;
  const dstPort  = packet.dst_port  || 0;
  const seq      = packet.seq_num   || 0;
  const ack      = packet.ack_num   || 0;
  const ttl      = packet.ttl       || 64;
  const proto    = (packet.protocol||'').includes('UDP') ? 17 : 6;
  const totalLen = (packet.resp_size || 0) + 40;

  // Build simulated header bytes
  const bytes = [
    // IP Header
    0x45, 0x00,
    (totalLen >> 8) & 0xFF, totalLen & 0xFF,
    0x00, 0x01, 0x40, 0x00,
    ttl, proto, 0x00, 0x00,
    127, 0, 0, 1,   // src IP 127.0.0.1
    127, 0, 0, 1,   // dst IP 127.0.0.1
    // TCP Header
    (srcPort >> 8) & 0xFF, srcPort & 0xFF,
    (dstPort >> 8) & 0xFF, dstPort & 0xFF,
    (seq >> 24) & 0xFF, (seq >> 16) & 0xFF, (seq >> 8) & 0xFF, seq & 0xFF,
    (ack >> 24) & 0xFF, (ack >> 16) & 0xFF, (ack >> 8) & 0xFF, ack & 0xFF,
    0x50, 0x18, 0xFF, 0xFF,
    0x00, 0x00, 0x00, 0x00,
  ];

  const sections = [
    { start: 0,  end: 19, color: C.accent,  label: 'IP Header (20 bytes)' },
    { start: 20, end: 39, color: C.green,   label: 'TCP Header (20 bytes)' },
  ];

  function getColor(i) {
    for (const s of sections) {
      if (i >= s.start && i <= s.end) return s.color;
    }
    return C.textDim;
  }

  const rows = [];
  for (let i = 0; i < bytes.length; i += 16) {
    rows.push(bytes.slice(i, i + 16));
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
        {sections.map(s => (
          <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: s.color }} />
            <span style={{ fontFamily: C.mono, fontSize: 10, color: s.color }}>{s.label}</span>
          </div>
        ))}
      </div>

      <div style={{ fontFamily: C.mono, fontSize: 12 }}>
        <div style={{ display: 'flex', marginBottom: 4, color: C.textDim, fontSize: 10 }}>
          <div style={{ width: 60 }}>Offset</div>
          <div style={{ flex: 1 }}>{'00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F'}</div>
          <div style={{ width: 140, paddingLeft: 16 }}>ASCII</div>
        </div>
        {rows.map((row, ri) => (
          <div key={ri} style={{ display: 'flex', marginBottom: 3 }}>
            <div style={{ width: 60, color: C.textDim }}>
              {(ri * 16).toString(16).padStart(4, '0').toUpperCase()}
            </div>
            <div style={{ flex: 1 }}>
              {row.map((byte, bi) => {
                const idx = ri * 16 + bi;
                return (
                  <span key={bi}>
                    <span style={{ color: getColor(idx), fontWeight: 600 }}>
                      {byte.toString(16).padStart(2, '0').toUpperCase()}
                    </span>
                    <span style={{ color: C.textDim }}>{bi === 7 ? '  ' : ' '}</span>
                  </span>
                );
              })}
            </div>
            <div style={{ width: 140, paddingLeft: 16, color: C.textDim }}>
              {row.map((byte, bi) => {
                const idx = ri * 16 + bi;
                const ch = byte >= 32 && byte < 127 ? String.fromCharCode(byte) : '.';
                return <span key={bi} style={{ color: getColor(idx) }}>{ch}</span>;
              })}
            </div>
          </div>
        ))}
      </div>
      <div style={{
        marginTop: 12, padding: '8px 12px',
        background: C.yellow + '11', border: `1px solid ${C.yellow}33`,
        borderRadius: 4, fontFamily: C.sans, fontSize: 11, color: C.textDim,
      }}>
        Note: Header bytes are reconstructed from captured fields. Payload bytes omitted (application data).
      </div>
    </div>
  );
}

// ── Protocol Info tab ─────────────────────────────────────────────────────────
function ProtocolInfo({ packet, isUDP }) {
  const proto = (packet.protocol || '').toUpperCase();

  const tcpInfo = [
    { q: 'What is TCP?', a: 'Transmission Control Protocol — a connection-oriented, reliable transport layer protocol.' },
    { q: 'Connection setup', a: '3-way handshake: SYN → SYN-ACK → ACK. Ensures both sides are ready before data transfer.' },
    { q: 'Reliability', a: 'Every segment is acknowledged. Lost packets are retransmitted. Sequence numbers track order.' },
    { q: 'Flow control', a: 'Window size field limits how much data sender can send before receiving an ACK.' },
    { q: 'Why used here', a: 'Our APIs use HTTP/1.1 over TCP. Reliability matters for payment and auth data.' },
  ];

  const udpInfo = [
    { q: 'What is UDP?', a: 'User Datagram Protocol — connectionless, unreliable but fast transport layer protocol.' },
    { q: 'No handshake', a: 'Packets are sent without establishing a connection. No SYN/ACK sequence.' },
    { q: 'No guarantee', a: 'Packets may arrive out of order, be duplicated, or be lost. Application handles this.' },
    { q: 'Speed advantage', a: 'No handshake overhead, no ACK waiting. Ideal for video streaming, DNS, gaming.' },
    { q: 'QUIC (YouTube)', a: 'YouTube uses QUIC over UDP. QUIC adds reliability and encryption at the application layer.' },
  ];

  const info = isUDP ? udpInfo : tcpInfo;

  return (
    <div>
      <div style={{
        fontFamily: C.mono, fontSize: 11,
        color: isUDP ? C.teal : C.green,
        letterSpacing: 2, marginBottom: 16,
      }}>
        {isUDP ? 'UDP PROTOCOL REFERENCE' : 'TCP PROTOCOL REFERENCE'} — OSI Layer 4
      </div>
      {info.map((item, i) => (
        <div key={i} style={{
          marginBottom: 10, padding: '10px 14px',
          background: C.panel,
          border: `1px solid ${C.border}`,
          borderLeft: `3px solid ${isUDP ? C.teal : C.green}`,
          borderRadius: 4,
        }}>
          <div style={{ fontFamily: C.sans, fontSize: 12, fontWeight: 700, color: C.text, marginBottom: 4 }}>
            {item.q}
          </div>
          <div style={{ fontFamily: C.sans, fontSize: 12, color: C.textDim }}>
            {item.a}
          </div>
        </div>
      ))}

      <div style={{
        marginTop: 16, padding: '12px 16px',
        background: C.accent + '0a',
        border: `1px solid ${C.accent}33`,
        borderRadius: 6,
      }}>
        <div style={{ fontFamily: C.mono, fontSize: 10, color: C.accent, marginBottom: 8, letterSpacing: 1 }}>
          OSI MODEL POSITION
        </div>
        {['Application (HTTP/TLS)', 'Transport (TCP/UDP)', 'Network (IP)', 'Data Link (Ethernet)', 'Physical'].map((layer, i) => (
          <div key={i} style={{
            padding: '4px 10px', marginBottom: 2, borderRadius: 3,
            background: (layer.includes('TCP') || layer.includes('UDP'))
              ? (isUDP ? C.teal : C.green) + '22'
              : layer.includes('IP') ? C.accent + '22' : 'transparent',
            border: `1px solid ${
              (layer.includes('TCP') || layer.includes('UDP'))
                ? (isUDP ? C.teal : C.green) + '44'
                : layer.includes('IP') ? C.accent + '44' : C.border
            }`,
            fontFamily: C.mono, fontSize: 11,
            color: (layer.includes('TCP') || layer.includes('UDP'))
              ? (isUDP ? C.teal : C.green)
              : layer.includes('IP') ? C.accent : C.textDim,
          }}>
            Layer {5 - i}: {layer}
          </div>
        ))}
      </div>
    </div>
  );
}
