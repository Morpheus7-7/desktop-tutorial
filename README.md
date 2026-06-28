# 🍸 Gin Pass — Gintoneria Club

App fedeltà **giovane e simpatica** per una gintoneria, realizzata come **PWA** (Progressive Web App): si installa sulla home dello smartphone come un'app vera, funziona su iPhone e Android, gira anche offline e non richiede App Store.

Meccanica fedeltà: **punti + livelli + badge** 🏆

## ✨ Funzioni

- **Tessera digitale** con punti, livello e QR code personale da far scansionare al bancone
- **Sistema a punti**: ogni consumazione vale punti (demo: +50)
- **Livelli gamificati**: 🌱 Apprendista → 🍸 Gin Lover → 🧪 Mixologist → 👑 Gin Master → ⚡ Leggenda
- **Badge sbloccabili**: Prima volta, Habitué, Esploratore, Nottambulo, Top Member, Premiato
- **Catalogo premi** riscattabili con i punti (tonica premium, drink omaggio, tasting, ecc.)
- **Carta dei Gin** interattiva con schede e abbinamenti tonica
- **Bonus di benvenuto** e onboarding con compleanno (per il drink omaggio 🎂)
- **Installabile** (Add to Home Screen) e **offline-ready** via service worker

> Demo: i dati sono salvati localmente sul dispositivo (`localStorage`), senza backend.

## 🚀 Come provarla

Serve un piccolo server statico (i service worker richiedono http/https, non `file://`):

```bash
# con Python
python3 -m http.server 8080
# poi apri http://localhost:8080 sul telefono (stessa rete) o sul browser
```

Per simulare l'uso: registra una "consumazione" dalla tessera per accumulare punti, sblocca livelli e badge, e riscatta i premi nella sezione 🎁.

## 🗂️ Struttura

```
index.html              # struttura dell'app (onboarding + tab)
css/styles.css          # stile mobile-first, tema neon/giovanile
js/app.js               # logica: punti, livelli, badge, premi, QR
manifest.webmanifest    # configurazione PWA (installabilità)
sw.js                   # service worker (cache offline)
icons/                  # icone PWA generate
```

## 🔮 Prossimi passi (idee)

- Backend reale (account, punti sincronizzati, app per il barista che scansiona il QR)
- Notifiche push per eventi e serate a tema
- Apple Wallet / Google Wallet pass
- Prenotazione tavoli ed eventi
