# CONTESTO – Radar Infermiere P.IVA

Questo file raccoglie tutto il contesto del progetto, ricavato dalle conversazioni con Claude
fino al 13/11/2026. Serve a chiunque (persona o AI) riprenda il lavoro senza la chat originale.
**Il repository deve restare privato: contiene dati personali.**

## 1. Chi sono

- Michael, infermiere iscritto all'OPI.
- Abito a **Mezzolombardo (TN)**: tutte le distanze si calcolano da qui.
- Dal 10/08/2026 sono dipendente dell'Azienda Sanitaria dell'Alto Adige (ASDAA/SABES),
  comprensorio di Bolzano, Medicina interna I (degenza), 36 ore a settimana su turni
  (mattina 7–13:30, giornata da 12 ore, notte 19:30–7:50).
- Lingue: italiano. Tedesco: vedi `config.yaml` (voce `profilo.tedesco`).
- Uso soprattutto il telefono (iPhone): report e app devono essere brevi e leggibili da lì.

## 2. Obiettivo

- Lasciare il posto da dipendente e lavorare come **infermiere in partita IVA (regime forfettario)**
  in Trentino-Alto Adige, con una rete di clienti: RSA/APSP, case di cura, cliniche,
  poliambulatori, medicina del lavoro, assistenza domiciliare, ambulatori stagionali.
- Traguardo: **3.000–3.500 € netti al mese** in modo sostenibile.
- Il Radar serve a non perdere nessun avviso o annuncio adatto, ogni giorno.

## 3. Modello economico (stime fatte in chat, da confermare con un commercialista)

- Forfettario: coefficiente di redditività 78%; imposta sostitutiva 5% per i primi 5 anni, poi 15%.
- ENPAPI: 16% contributo soggettivo + 4% integrativo (a carico del cliente) + circa 100 € di maternità.
- Tetto di ricavi: 85.000 € l'anno.
- Regola pratica: accantonare il 20–25% di ogni incasso.
- Punto di pareggio per 3.000 € netti al mese: circa **53.500 € di fatturato l'anno**
  (per 3.500 € circa 60.000 €).

### Tariffe di riferimento

| Voce | Valore | Affidabilità |
| --- | --- | --- |
| ASUIT, libera professione infermieri (SLP 13/2026, Tione, estate 2026) | 40,00 €/h lordo omnicomprensivo | Avviso ufficiale (chiuso) |
| RSA | circa 30 €/h | Stima non verificata |
| ParaMedica (società di servizi) | 25–28 €/h | Dal tracker, non confermata dall'annuncio |
| FNOPI «Infermieri per voi» | soprattutto 20–50 € a prestazione/ora | Autodichiarata dai colleghi |
| Domiciliare (blog generici) | 30–45 €/h | Non verificata |
| Collaborazione con studi (blog generici) | 25–40 €/h | Non verificata |
| Notte (blog generici) | 150–250 € per turno di 8 h | Non verificata |

Le stime di stipendio degli aggregatori (Indeed, Jooble, Jobsora…) **non sono affidabili**.

## 4. Vincoli

- **Incompatibilità:** finché sono dipendente ASDAA non posso assumere incarichi di libera
  professione o collaborazioni senza dimissioni, aspettativa o autorizzazione.
  Il Radar fa solo ricerca: **non si candida e non contatta nessuno**.
- **Lingua in Alto Adige:** per il tempo indeterminato in ASDAA serve il bilinguismo B2;
  senza attestato il tempo determinato dura al massimo 3 anni. Alcuni posti pubblici sono riservati
  a un gruppo linguistico (es. INAIL Bolzano, gruppo tedesco). Molte strutture private indicano
  italiano + tedesco come titolo preferenziale.
- **Scenari realistici:** niente piani basati su turni da 12 ore tutti i giorni o compensi «pomposi».

## 5. Come si valuta un'offerta (punteggio 0–100)

| Voce | Peso | Criterio |
| --- | --- | --- |
| Contratto | 30 | P.IVA / libera professione al massimo; collaborazione; dipendente al minimo |
| Compenso | 25 | €/h: da 40 € in su il massimo; 30–39 €; sotto; non indicato |
| Distanza | 20 | minuti d'auto da Mezzolombardo: fino a 20, 45, 90, oltre |
| Ore e turni | 15 | blocchi da 12 h, notti, weekend, monte ore adeguato |
| Fonte | 10 | ente ufficiale > sito della struttura > aggregatore / avviso di ricerca |

I pesi sono in `config.yaml`. Se un dato manca si scrive «n.d.», non si inventa.

## 6. Fonti: cosa è stato controllato il 12/11/2026 e con quale esito

| Fonte | Esito | Note |
| --- | --- | --- |
| OPI Trento – annunci di lavoro (`opi.tn.it/segreteria/annunci-di-lavoro/`) | Letta | Fonte migliore per APSP, RSA e cliniche del Trentino |
| OPI Bolzano – offerte di lavoro (`opibz.it/?page_id=5109`) | Parziale | Letta la pagina 1 (20 voci) |
| UPIPA – bacheca concorsi delle APSP | Parziale | Letta la pagina 1 |
| ASUIT – bandi e concorsi | Parziale | Avvisi di libera professione con sigla «SLP» |
| SABES onboard (ASDAA) | Parziale | Leggibili le pagine singole, non l'elenco |
| Villa Sant'Anna Merano – lavora con noi | Letta | Annunci senza data |
| Gruppo Bonvicini Bolzano – lavora con noi | Letta | |
| ASSB Bolzano | Letta | Nessun avviso per infermieri (graduatoria valida fino al 15/10/2028) |
| suedtirolerjobs.it | Parziale | Leggibile il singolo annuncio, non gli elenchi |
| Cooperazione trentina – lavora con noi | Parziale | Letta solo la descrizione del portale |
| Indeed, LinkedIn pubblico, Jobrapido, Jooble, Jobsora, Adzuna, Jobeka, Bakeca, Subito, Glassdoor | Solo estratti dei motori di ricerca | Date poco affidabili |
| eJobLavoro (Provincia BZ), Trentino Lavoro, InfoJobs, elenchi Randstad, Euregio | Non leggibili | Pagine dinamiche |
| LinkedIn con accesso, Facebook, Telegram, WhatsApp | Non coperte | Richiedono login: il Radar non le legge |
| Bollettino/concorsi Provincia BZ, Comuni e Comunità di valle, Brixsana, Villa Melitta, Villa Bianca, Martinsbrunn, hospice/ADI | Non coperte | Da aggiungere se si trova una pagina leggibile |

Per coprire il resto del web ci sono 3 avvisi di **Google Alerts** consegnati via feed RSS, già in `config.yaml`
(manca, facoltativo, quello in tedesco).

### Aggiornamento del 13/11/2026 (versione 2 del Radar)

- **ASUIT:** funziona solo l'indirizzo con `www` (`www.asuit.tn.it/bandi-concorsi?page=N`); 4 bandi per pagina,
  dal più nuovo. Il Radar legge le prime 10 pagine e apre solo i bandi per infermieri o di libera professione.
  Le «ricognizioni interne» per prestazioni aggiuntive riguardano i dipendenti ASUIT.
- **UPIPA:** concorsi su due pagine (`…/Bacheca/Concorsi/(offset)/10`); la bacheca «Avvisi» esiste ma è spesso vuota.
  I bandi sono PDF: ora vengono letti.
- **SABES onboard e Cooperazione trentina:** spente, non leggibili in automatico.
- **OPI Bolzano:** molti annunci sono immagini o PDF con poco testo.
- **suedtirolerjobs:** gli elenchi sono dinamici; si segue il singolo annuncio di Schloss Moos.
- Siti delle APSP sulla piattaforma comune (es. `mezzolombardo.upipa.opencontent.it`): in esplorazione,
  vedi `esplora:` in `config.yaml` e `data/diagnostica.json`.

## 7. Offerte già trovate (controllo manuale del 12/11/2026)

Elenco completo (95 righe) nel foglio «Offerte di lavoro infermieri Trentino-Alto Adige – 12/11/2026»:
https://claude.ai/artifact/SY7859YhpV9wyhUBLeWh53

### P.IVA / libera professione / collaborazione

1. **APSP «Clementino Vannetti», Rovereto** – incarichi libero-professionali di infermiere.
   Scadenza prorogata al **27/11/2026 ore 12:00**, domanda via PEC. Aperto.
   https://opi.tn.it/a-p-s-p-c-vannetti-2-copy/
2. **Casa di Cura Villa Sant'Anna, Merano** – assunzione o libera professione, turni da 12 h;
   preferenza italiano + tedesco. https://villa-santanna.eu/lavora-con-noi/
3. **Seniorenwohnheim Schloss Moos, Wiesen-Pfitsch** – attività libero-professionale per notti,
   weekend o sostituzioni lunghe. https://www.suedtirolerjobs.it/jobs/freiberufliche-taetigkeit-in-der-pflege,115073
4. **Privatassistenza, Trento** – infermiere con P.IVA, assistenza domiciliare (visto su Bakeca, 02/11/2026).
5. **Gruppo KOS / Ninacare, Arco** – indeterminato o P.IVA (visto su Bakeca, data n.d.).
6. **Italiassistenza** – P.IVA a Trento (Indeed 29/10/2026) e a Bolzano (Indeed 12/09/2026).
7. **CHC Italy (Cerba HealthCare), Trento** – infermiere P.IVA (Indeed 28/10/2026).
8. **ParaMedica srl** – infermieri RSA zona Rovereto (Indeed 29/10/2026) e zona Trento (14/08/2026); P.IVA, alloggio.
9. **IQVIA Solutions Italy** – attività domiciliari a Bolzano e Trento, collaborazione/P.IVA (Indeed 19/07/2026).
10. **Emodialisi domiciliare a Bolzano** (privato, via OPI Bolzano, 28/07/2026).
    https://www.opibz.it/cercasi-infermiere-a-per-emodialisi-domiciliare-bolzano/
11. **Hotel Palace Merano** – valuta la libera professione (05/03/2026, datato).
    https://www.opibz.it/hotel-palace-merano-cerca-infermiere/

### Dipendente, con scadenza

- APSP Vannetti, concorso 10 infermieri: 13/11/2026. https://opi.tn.it/a-p-s-p-c-vannetti-bando/
- ASUIT, selezioni a tempo determinato (SC 04/26–13/26): sessioni 15/11 e 11/12/2026. https://www.asuit.tn.it/bandi-concorsi
- APSP «Giovanni Endrizzi», Lavis: 19/11/2026 ore 12. https://www.upipa.tn.it/Bacheca/Concorsi/APSP-di-Lavis-Infermieri
- APSP «San Giuseppe», Primiero: 04/12/2026 ore 12. https://opi.tn.it/apsp-san-giuseppe-di-primiero-tn-ricerca-di-personale/
- ASDAA/SABES, graduatorie permanenti infermieri: 31/01/2027 (poi 31/05 e 30/09).

### Altri aperti o probabili (dipendente o contratto non indicato)

RSA Ciasa de Palsa (Val Badia), Casa di Cura Eremo (Arco), Cooperativa Villa Maria (Calliano),
Gruppo Bonvicini (Casa di Cura e Centro Emodialisi), Randstad Vipiteno, Adecco Healthcare Trento,
Manpower Arco, Medical Rovereto.

### Chiuso ma ricorrente

- **ASUIT SLP 15/2026** – infermieri libero-professionisti negli ambulatori di primo soccorso
  traumatologico di Madonna di Campiglio e Sèn Jan di Fassa (23/12/2026–29/03/2027). Scaduto l'11/09/2026.
  Contatto: incarichilp@asuit.tn.it. Esce ogni anno.

## 8. Parole chiave

- **Italiano:** infermiere/a, infermiere libero professionista, partita IVA, P.IVA, collaborazione,
  incarico libero professionale, SLP, avviso pubblico, graduatoria, RSA, APSP, domiciliare.
- **Tedesco:** Krankenpfleger/in, Pflegefachkraft, Berufskrankenpfleger, freiberuflich,
  Freiberufliche Tätigkeit, Honorar, Seniorenwohnheim, Sozialgenossenschaft.

## 9. Scadenze ricorrenti

| Quando | Cosa |
| --- | --- |
| Tra agosto e dicembre | ASUIT: avvisi di libera professione per gli ambulatori invernali (SLP) |
| Gennaio | D.O.C.: avviso per la stagione estiva |
| 31/01, 31/05, 30/09 | ASDAA/SABES: graduatorie permanenti infermieri |

## 10. Altri materiali del progetto (artifact di Claude)

- Tracker «Rete strutture per infermiere a partita IVA»: https://claude.ai/artifact/4RrogxYkRWQbWkAp7sx54R
- Scenari 15 e 20 giorni al mese: https://claude.ai/artifact/TBw2S9m4CEtyQ82tYrq38D
- Guida completa P.IVA in Trentino-Alto Adige: https://claude.ai/artifact/QJX5T83dBG53UZvDEhK7qJ

## 11. Limiti noti del Radar

- Legge solo pagine pubbliche: niente login, niente social, rispetto di robots.txt.
- L'estrazione di contratto, compenso, scadenza e zona è automatica (parole chiave):
  può sbagliare. Prima di muoversi va sempre aperto l'annuncio originale.
- I PDF allegati vengono letti (al massimo 2 per annuncio, 12 pagine). I PDF fatti di sole immagini
  (scansioni) restano illeggibili: compare il titolo, con i dati «n.d.».
- La tabella delle distanze contiene stime, non misure.
- L'email proposta dall'app è una richiesta di informazioni: parte solo se la invio io dal telefono.

## 12. Come funziona la versione 2 (13/11/2026)

- Giro alle 7 circa (ora di Roma) con email; giro di prova senza email a ogni modifica caricata su GitHub.
- Scarti automatici: ruoli diversi dall'infermiere (OSS, medici, coordinatori, fisioterapisti…),
  annunci fuori regione, mobilità e comandi riservati a dipendenti pubblici, doppioni tra fonti.
- Un annuncio senza scadenza più vecchio di 120 giorni è «datato»: resta in elenco ma non tra le novità.
- I dati inseriti a mano vincono su quelli letti in automatico (tranne la scadenza, che si aggiorna).
- App: schede Oggi, Offerte, Scadenze, Zone, Report. Stati e appunti restano solo sul telefono.
- Indirizzo dell'app: https://radar-infermiere.pages.dev (protetta da Cloudflare Access).

## 13. Scelte del 13/11/2026 (contatti, conti, agenda)

- Email di primo contatto: le prepara l'app, le invio io con un tocco (non partono da sole). Mai due volte allo stesso indirizzo.
- Mittente: Gmail; PEC solo verso indirizzi PEC, scelta a mano in Mail.
- Il Radar può leggere in Gmail solo le risposte delle strutture contattate e gli avvisi di lavoro dei portali.
- Obiettivo: 3.000 € netti al mese dopo tasse, contributi ENPAPI, spese e fondo pensione da 6.000 € l'anno.
- Agenda: sempre due giorni liberi a settimana, con priorità al weekend.
