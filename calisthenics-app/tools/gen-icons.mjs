/* ============================================================================
 * Cali100 — Generatore icone PWA (PNG puro, senza dipendenze)
 * Disegna un'icona: sfondo scuro sfumato + barre ascendenti (progressione 0→100)
 * in gradiente lime→cyan. Anti-aliasing tramite supersampling.
 *   Uso:  node tools/gen-icons.mjs
 * ==========================================================================*/
import { deflateSync } from 'node:zlib';
import { writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'assets', 'icons');
mkdirSync(OUT, { recursive: true });

// ---- Palette ----
const BG_TL = [0x14, 0x22, 0x2f];   // alto-sinistra
const BG_BR = [0x0a, 0x0e, 0x13];   // basso-destra
const GLOW  = [0xc6, 0xff, 0x3d];   // lime
const LIME  = [0xc6, 0xff, 0x3d];
const CYAN  = [0x22, 0xd3, 0xee];

const lerp = (a, b, t) => a + (b - a) * t;
const mix = (c1, c2, t) => [lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// ---- CRC32 per i chunk PNG ----
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length, 0);
  const typeBuf = Buffer.from(type, 'ascii');
  const body = Buffer.concat([typeBuf, data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(body), 0);
  return Buffer.concat([len, body, crc]);
}
function encodePNG(width, height, rgba) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;   // bit depth
  ihdr[9] = 6;   // color type RGBA
  ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  // scanline con filtro 0
  const stride = width * 4;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0;
    rgba.copy(raw, y * (stride + 1) + 1, y * stride, y * stride + stride);
  }
  const idat = deflateSync(raw, { level: 9 });
  return Buffer.concat([sig, chunk('IHDR', ihdr), chunk('IDAT', idat), chunk('IEND', Buffer.alloc(0))]);
}

// ---- Disegno ----
// style: 'rounded' | 'full' (full-bleed per maskable/apple)
function drawIcon(size, style, pad) {
  const ss = 4;                 // supersampling
  const D = size * ss;
  const hi = new Float32Array(D * D * 4);

  const radius = style === 'rounded' ? D * 0.235 : 0; // full => angoli quadrati (li smussa la piattaforma)

  // sfondo
  for (let y = 0; y < D; y++) {
    for (let x = 0; x < D; x++) {
      const idx = (y * D + x) * 4;
      // dentro il rounded-rect?
      let inside = true;
      if (radius > 0) {
        const rx = radius;
        const cx = x < rx ? rx : (x > D - rx ? D - rx : x);
        const cy = y < rx ? rx : (y > D - rx ? D - rx : y);
        const dx = x - cx, dy = y - cy;
        inside = dx * dx + dy * dy <= rx * rx;
      }
      if (!inside) { hi[idx + 3] = 0; continue; }
      // gradiente diagonale
      const t = (x + y) / (2 * D);
      let col = mix(BG_TL, BG_BR, t);
      // glow radiale in alto
      const gx = D * 0.5, gy = D * 0.12, gr = D * 0.55;
      const dg = Math.hypot(x - gx, y - gy) / gr;
      const glow = clamp(1 - dg, 0, 1) * 0.14;
      col = mix(col, GLOW, glow);
      hi[idx] = col[0]; hi[idx + 1] = col[1]; hi[idx + 2] = col[2]; hi[idx + 3] = 255;
    }
  }

  // barre ascendenti dentro l'area contenuto
  const padPx = D * pad;
  const cx0 = padPx, cy0 = padPx, cw = D - 2 * padPx, ch = D - 2 * padPx;
  const N = 4;
  const gap = cw * 0.07;
  const barW = (cw - gap * (N - 1)) / N;
  const heights = [0.42, 0.62, 0.82, 1.0];
  const baseY = cy0 + ch; // baseline in basso
  const barRad = barW * 0.34;

  for (let b = 0; b < N; b++) {
    const bx = cx0 + b * (barW + gap);
    const bh = ch * heights[b];
    const by = baseY - bh;
    const col = mix(LIME, CYAN, b / (N - 1));
    for (let y = Math.floor(by); y < baseY; y++) {
      for (let x = Math.floor(bx); x < bx + barW; x++) {
        if (x < 0 || y < 0 || x >= D || y >= D) continue;
        // angoli arrotondati (solo in alto in modo netto, ma smussiamo tutti e 4)
        const lx = x - bx, ly = y - by;
        let ins = true;
        // corner top-left
        if (lx < barRad && ly < barRad) ins = (barRad - lx) ** 2 + (barRad - ly) ** 2 <= barRad * barRad;
        else if (lx > barW - barRad && ly < barRad) ins = (lx - (barW - barRad)) ** 2 + (barRad - ly) ** 2 <= barRad * barRad;
        if (!ins) continue;
        const idx = (y * D + x) * 4;
        hi[idx] = col[0]; hi[idx + 1] = col[1]; hi[idx + 2] = col[2]; hi[idx + 3] = 255;
      }
    }
  }

  // downsample ss×ss -> size×size
  const out = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let r = 0, g = 0, bl = 0, a = 0;
      for (let sy = 0; sy < ss; sy++) {
        for (let sx = 0; sx < ss; sx++) {
          const idx = ((y * ss + sy) * D + (x * ss + sx)) * 4;
          const pa = hi[idx + 3];
          r += hi[idx] * pa; g += hi[idx + 1] * pa; bl += hi[idx + 2] * pa; a += pa;
        }
      }
      const o = (y * size + x) * 4;
      if (a > 0) { out[o] = Math.round(r / a); out[o + 1] = Math.round(g / a); out[o + 2] = Math.round(bl / a); }
      out[o + 3] = Math.round(a / (ss * ss));
    }
  }
  return out;
}

function make(name, size, style, pad) {
  const rgba = drawIcon(size, style, pad);
  const png = encodePNG(size, size, rgba);
  writeFileSync(join(OUT, name), png);
  console.log('  ✓', name, `(${size}×${size}, ${(png.length / 1024).toFixed(1)} KB)`);
}

console.log('Genero le icone in', OUT);
make('icon-192.png', 192, 'rounded', 0.17);
make('icon-512.png', 512, 'rounded', 0.17);
make('icon-maskable-192.png', 192, 'full', 0.28);
make('icon-maskable-512.png', 512, 'full', 0.28);
make('apple-touch-icon.png', 180, 'full', 0.17);
make('favicon.png', 64, 'rounded', 0.15);
console.log('Fatto.');
