---
name: Deal Combined
description: Gestionale e palestra commerciale per reti di consulenti assicurativi
colors:
  copertina: "#1d3b30"
  copertina-inchiostro: "#e6eee8"
  copertina-attenuato: "#a9bcb1"
  verde-azione: "#24533f"
  verde-azione-scuro: "#1b4333"
  verde-velato: "#dcebe1"
  nastro: "#9f1239"
  pagina: "#f2f5f1"
  foglio: "#ffffff"
  foglio-2: "#e9efe8"
  filetto: "#d6dfd5"
  inchiostro: "#16211b"
  inchiostro-attenuato: "#4d5c54"
  pericolo: "#b42318"
  avviso: "#a15c07"
  successo: "#15803d"
  info: "#0e6178"
  copertina-buio: "#0c1c15"
  pagina-buio: "#101814"
  foglio-buio: "#17211c"
  inchiostro-buio: "#e4ebe6"
  verde-azione-buio: "#7fd1a9"
  nastro-buio: "#be123c"
typography:
  display:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "4.6rem"
    fontWeight: 750
    lineHeight: 0.82
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 72"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
    fontVariation: "'wdth' 94"
  title:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  numeri:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 700
    lineHeight: 1.15
    fontFeature: "'tnum' 1"
    fontVariation: "'wdth' 80"
  label:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 650
    letterSpacing: "0.06em"
rounded:
  chip: "0.3rem"
  controllo: "0.45rem"
  card: "0.6rem"
  pillola: "999px"
spacing:
  riga: "0.7rem"
  card: "1.25rem"
  pagina: "2rem"
  pagina-mobile: "1rem"
components:
  button-primary:
    backgroundColor: "{colors.verde-azione}"
    textColor: "{colors.foglio}"
    rounded: "{rounded.controllo}"
  button-primary-hover:
    backgroundColor: "{colors.verde-azione-scuro}"
    textColor: "{colors.foglio}"
  button-secondary:
    backgroundColor: "{colors.foglio}"
    textColor: "{colors.inchiostro-attenuato}"
    rounded: "{rounded.controllo}"
  card:
    backgroundColor: "{colors.foglio}"
    textColor: "{colors.inchiostro}"
    rounded: "{rounded.card}"
  rail:
    backgroundColor: "{colors.copertina}"
    textColor: "{colors.copertina-attenuato}"
    width: "15rem"
  rail-item-active:
    textColor: "{colors.copertina-inchiostro}"
    rounded: "{rounded.controllo}"
  search:
    backgroundColor: "{colors.foglio}"
    textColor: "{colors.inchiostro}"
    rounded: "{rounded.pillola}"
  nastro:
    backgroundColor: "{colors.nastro}"
    textColor: "{colors.foglio}"
    typography: "{typography.label}"
    height: "1.7rem"
---

# Design System: Deal Combined

## Overview

**Creative North Star: "Il nastro sul prossimo passo"**

Deal Combined è l'agenda annuale del consulente, resa come strumento di lavoro contemporaneo. La barra laterale è la copertina in tela verde bottiglia, il contenuto è la pagina: bianca, appena velata di verde, scritta in inchiostro verde-nero. Su ogni schermata c'è un solo nastro segnalibro rosso, che marca il prossimo passo: la prossima attività di oggi, la trattativa da muovere, il prossimo follow-up del cliente, la prossima lezione.

La densità è media, perché lo strumento serve sia al consulente esperto sia a chi è in formazione. Il mondo dell'agenda presta solo caratteri, palette, densità e il nastro: navigazione, pulsanti, tabelle e campi restano i comandi standard che chiunque sa usare. Al buio l'agenda è chiusa: stesse regole, fondo verde quasi nero. La carta stampata è sempre chiara.

**Key Characteristics:**
- Copertina verde come guscio dell'app; il colore fa un lavoro, non decora.
- Date e numeri grandi, condensati e tabellari, come nella pagina del giorno.
- Un nastro rosso per schermata, sempre sul prossimo passo.
- Componenti Bootstrap standard, ritinti dai token; nessun costume del mondo.
- Tema chiaro e scuro con gli stessi ruoli; la stampa resta chiara.

## Colors

Restrained ma con un guscio colorato: neutri tinti di verde, un verde d'azione e un solo rosso, riservato al nastro.

### Primary
- **Verde copertina** (copertina): fondo della barra laterale e del menu su mobile. È il marchio senza bisogno di un logo.
- **Verde azione** (verde-azione): pulsanti primari, link e voce attiva dell'Accademia. Al buio diventa un verde chiaro (verde-azione-buio) con testo scuro sopra.

### Secondary
- **Rosso nastro** (nastro): solo il nastro segnalibro. Al buio passa a un cremisi più acceso (nastro-buio), che regge il testo bianco.

### Neutral
- **Pagina velata** (pagina): sfondo del contenuto. È bianco tinto di verde, non crema.
- **Foglio** (foglio) e **Foglio 2** (foglio-2): card e campi; foglio-2 per chip, righe evidenziate e sfondi secondari.
- **Filetto** (filetto): bordi, divisori delle righe e linea sotto la barra superiore.
- **Inchiostro** (inchiostro) e **Inchiostro attenuato** (inchiostro-attenuato): testo principale e secondario, almeno 4.5:1 sulla pagina.
- Gli stati (pericolo, avviso, successo, info) sono tonalità scure da inchiostro, leggibili come testo su bianco. Ognuno ha una versione "soft" per gli sfondi delle righe e degli alert.

### Named Rules
**The One Ribbon Rule.** Il rosso nastro compare una sola volta per schermata e solo sul prossimo passo. Se non c'è un prossimo passo, non c'è nastro.

**The Two Reds Rule.** Il pericolo (ritardi, scadute, eliminazioni) usa un rosso diverso dal nastro. Il nastro indica una direzione, il pericolo uno stato: non confonderli.

## Typography

**Display Font:** Archivo variabile (con system-ui), servito in locale.
**Body Font:** Archivo variabile (con system-ui).

**Character:** un'unica famiglia grottesca che cambia larghezza invece di cambiare carattere: condensata e pesante per date e numeri, normale per leggere.

### Hierarchy
- **Display** (750, 4.6rem, larghezza 72%): solo il numero del giorno nella pagina «Oggi».
- **Headline** (650, 1.75rem, larghezza 94%): titoli di pagina.
- **Title** (600, 1rem): intestazioni delle card e titoli delle voci.
- **Body** (400, 1rem, 1.5): testo corrente. Le lezioni dell'Accademia hanno una misura massima di 36em (circa 75 caratteri).
- **Numeri** (700, larghezza 78-85%, cifre tabellari): importi, conteggi, «−12 gg», KPI.
- **Label** (650, 0.78rem, maiuscolo, spaziatura 0.06em): gruppi della lista «Oggi», intestazioni delle tabelle, gruppi del menu.

### Named Rules
**The Width Not Weight Rule.** Per dare enfasi a un numero si stringe la larghezza (font-stretch) e si alza il peso; non si cambia famiglia e non si usa il corsivo.

## Layout

Guscio a due zone. Da 992 px in su c'è la barra laterale fissa da 15rem; sotto quella soglia diventa un menu offcanvas aperto dall'hamburger. Il contenuto ha una barra superiore fissa (ricerca, tema, notifiche), padding di 2rem (1rem su mobile) e una larghezza massima di 1480px. La pagina «Oggi» mette la lista a sinistra e la colonna laterale (trattative, portafoglio, allenamento) a destra da 768 px in su. Sotto i 768 px tutto va in colonna, con l'azione di ogni voce che scende sotto il testo. Sui pieghevoli con cerniera (horizontal-viewport-segments: 2) le due colonne si allineano ai due pannelli e la piega resta libera. Le tabelle scorrono dentro la propria card, mai l'intera pagina.

## Elevation & Depth

Profondità quasi piatta. In tema chiaro le card hanno un'ombra ambientale leggerissima, con offset reale; in tema scuro le ombre spariscono e la profondità viene solo dai toni (pagina, foglio, foglio-2) e dai filetti. L'unico elemento che "sporge" è il nastro, che esce dal bordo sinistro della card con la coda a V.

### Shadow Vocabulary
- **Foglio** (`box-shadow: 0 1px 2px rgba(22,33,27,.06), 0 2px 8px rgba(22,33,27,.05)`): card a riposo, solo in tema chiaro.
- **Sollevato** (`box-shadow: 0 6px 18px rgba(22,33,27,.1)`): passaggio del mouse sulle card dei moduli dell'Accademia.

### Named Rules
**The Flat Dark Rule.** Al buio niente ombre: la profondità è affidata ai toni e ai filetti.

## Shapes

Angoli moderati e coerenti: 0.6rem per le card, 0.45-0.5rem per pulsanti, voci di menu e pulsanti icona, 0.3rem per i chip, pillola piena solo per il campo di ricerca e i contatori. Il nastro è l'unica forma speciale: un rettangolo piatto con la coda a V sul lato sinistro (clip-path a cinque vertici), senza raggio e senza sfumature.

## Components

### Buttons
- **Shape:** angoli leggermente arrotondati (0.375-0.5rem), peso 550.
- **Primary:** verde azione con testo bianco; al buio verde chiaro con testo scuro.
- **Hover / Focus:** il verde si scurisce. Il focus da tastiera è un contorno verde di 2px, distanziato di 2px.
- **Secondary:** fondo foglio, bordo filetto, testo attenuato. Le varianti outline success/danger usano le tonalità da inchiostro degli stati.

### Chips
- **Style:** fondo foglio-2, testo attenuato, 0.78rem, peso 600 (tipo di attività, numero di polizza nella lista «Oggi»).

### Cards / Containers
- **Corner Style:** 0.6rem.
- **Background:** foglio su pagina.
- **Shadow Strategy:** ombra Foglio in chiaro, nessuna al buio.
- **Border:** 1px filetto.
- **Internal Padding:** 1-1.25rem; intestazione con titolo a sinistra e link d'azione a destra, senza sottolineatura fino al passaggio del mouse.

### Inputs / Fields
- **Style:** fondo foglio, bordo filetto, segnaposto in inchiostro attenuato (≥4.5:1). La ricerca è una pillola con la lente all'interno.
- **Focus:** anello di focus Bootstrap tinto di verde.

### Navigation
- **Rail:** voci con icona e testo, raccolte in tre gruppi (Lavoro, Archivio, Formazione) etichettati in maiuscoletto attenuato. Voce attiva: sfondo bianco al 13% e testo bianco in grassetto, senza barre laterali colorate. Impostazioni in fondo, separate da un filetto.
- **Mobile:** stessa barra in offcanvas; marchio compatto nella barra superiore.

### Il nastro (Signature Component)
Fascia piatta rosso nastro, alta 1.7rem, testo bianco in maiuscolo condensato con l'icona del segnalibro. Attraversa la card per tutta la larghezza e sporge di circa 1.55rem oltre il bordo sinistro con la coda a V. Etichette in uso: «Prossimo passo», «Muovi questa», «Prossima lezione», con un dettaglio facoltativo in minuscolo. Ha `role="note"`. In stampa mantiene il colore.

## Do's and Don'ts

### Do:
- **Do** usare un solo nastro per schermata, sul prossimo passo reale (The One Ribbon Rule).
- **Do** scrivere date, importi e conteggi in numeri tabellari condensati.
- **Do** ritingere i componenti Bootstrap tramite i token `--dc-*`, in entrambi i temi.
- **Do** forzare la carta chiara nelle schede da stampare (`data-bs-theme="light"`) e in stampa.
- **Do** tenere il contrasto del testo ≥4.5:1 in chiaro e in scuro, nastro compreso.

### Don't:
- **Don't** usare il rosso nastro per errori, badge o decorazioni (The Two Reds Rule).
- **Don't** usare fondi crema o carta ingiallita: la pagina è bianca velata di verde.
- **Don't** imitare materiali (raso del nastro, trama della tela, rilegatura): il mondo entra con palette, caratteri, densità e il nastro piatto.
- **Don't** marcare lo stato con barre colorate laterali su card, righe o voci di menu.
- **Don't** mettere etichette sopra i titoli: il contesto (settimana, area) va sotto il titolo.
