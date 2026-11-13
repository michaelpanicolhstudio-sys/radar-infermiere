# Radar Infermiere P.IVA

Ogni mattina alle 7 circa questo programma:

1. legge le fonti elencate in `config.yaml` (OPI Trento e Bolzano, UPIPA, ASUIT, cliniche, i tuoi Google Alerts);
2. apre ogni annuncio e i **PDF allegati** (bandi e avvisi) ed estrae datore, contratto, compenso, ore e turni, zona, scadenza, email di contatto;
3. dà un punteggio da 0 a 100 (contratto, compenso, distanza da Mezzolombardo, turni, fonte);
4. scarta i ruoli che non sono da infermiere, gli annunci fuori regione e i doppioni, confronta con il giorno prima e ti manda **un'email** con novità, scadenze e le 5 offerte migliori;
5. aggiorna la **web app** da tenere sulla schermata Home dell'iPhone.

Gira da solo su GitHub, gratis. Non serve tenere acceso niente.

> **Cosa non fa.** Non legge social, LinkedIn con accesso o siti che richiedono login. Non si candida
> e non contatta nessuno. I dati sono estratti in automatico e possono contenere errori:
> apri sempre l'annuncio originale. Se un dato manca trovi «n.d.».

Il contesto del progetto (obiettivi, tariffe, vincoli, fonti già controllate) è in [`CONTESTO.md`](CONTESTO.md).

---

## Messa in funzione (una volta sola, circa 40 minuti)

Conviene farla da un computer. I passi 1–3 bastano per ricevere l'email; 4–6 aggiungono l'app.

### 1. Carica il programma su GitHub

1. Su github.com: **+** in alto a destra → **New repository**. Nome `radar-infermiere`, scegli **Private**, poi **Create repository**.
2. Scompatta lo zip sul computer.
3. Nella pagina del repository: **uploading an existing file** → trascina **tutto il contenuto** della cartella scompattata → **Commit changes**.
4. La cartella `.github` è nascosta e spesso non viene trascinata. Controlla se nel repository la vedi. Se manca:
   **Add file → Create new file**, come nome scrivi `.github/workflows/radar.yml`, incolla il contenuto di
   `workflow-da-copiare.txt` e fai **Commit changes**.

### 2. Password per le app di Gmail

1. Vai su https://myaccount.google.com/apppasswords (serve la verifica in due passaggi attiva).
2. Nome dell'app: `Radar`. Google mostra una password di 16 lettere: copiala.
   Non è la tua password normale e puoi revocarla quando vuoi.

### 3. Segreti su GitHub

Nel repository: **Settings → Secrets and variables → Actions → New repository secret**. Crea:

| Nome | Valore |
| --- | --- |
| `GMAIL_USER` | il tuo indirizzo Gmail (quello della password per le app) |
| `GMAIL_APP_PASSWORD` | la password di 16 lettere |
| `EMAIL_TO` | facoltativo: l'indirizzo che riceve il report, se diverso |

**Prima prova:** scheda **Actions** → **Radar giornaliero** → **Run workflow**. Dopo qualche minuto arriva l'email.
Il primo report elenca anche le fonti che non si riescono a leggere: è normale, vedi «Se una fonte non funziona».

### 4. Cloudflare: chiave per pubblicare l'app

1. Su dash.cloudflare.com copia l'**Account ID** (pagina iniziale dell'account o **Workers & Pages**, colonna a destra).
2. **Profilo (in alto a destra) → API Tokens → Create Token → Custom token**.
   Permesso: **Account → Cloudflare Pages → Edit**. Crea e copia il token.
3. Su GitHub aggiungi altri due segreti: `CLOUDFLARE_ACCOUNT_ID` e `CLOUDFLARE_API_TOKEN`.
4. Avvia di nuovo il workflow (**Run workflow**). Crea il progetto `radar-infermiere` e pubblica l'app.
5. In Cloudflare, **Workers & Pages → radar-infermiere**: lì trovi l'indirizzo dell'app
   (di solito `https://radar-infermiere.pages.dev`; se il nome era già preso avrà qualche lettera in più).
6. Se l'indirizzo è diverso da `https://radar-infermiere.pages.dev`, scrivilo in `config.yaml` alla voce `app_url`:
   è il collegamento che compare nelle email.

### 5. Proteggi l'app con Cloudflare Access (subito dopo il passo 4)

Finché non fai questo passo, chi conosce l'indirizzo può vedere l'elenco delle offerte
(le tue note no: restano solo sul telefono).

1. **Workers & Pages → radar-infermiere → Settings → Enable access policy**.
2. Tocca **Manage** sulla regola appena creata, poi **Access → Applications →** il tuo progetto → **Configure**.
3. In **Public hostname**, campo **Subdomain**, cancella l'asterisco `*` e salva
   (se dà errore, cambia anche il nome dell'applicazione). Ora è protetto l'indirizzo principale.
4. Torna in **Settings → General** del progetto e premi di nuovo **Enable access policy**
   (protegge anche le anteprime).
5. Nella regola (policy) controlla che sia ammessa solo la tua email.
   All'apertura dell'app Cloudflare ti manderà un codice via email.
6. Nella stessa applicazione imposta **Session duration** su **1 month**: così il codice ti viene chiesto una volta al mese e non ogni giorno.

Cloudflare cambia spesso i menu: la guida ufficiale aggiornata è
https://developers.cloudflare.com/pages/platform/known-issues/ (sezione «Enable Access on your *.pages.dev domain»).

### 6. Installa l'app sull'iPhone

1. Apri l'indirizzo dell'app in **Safari** e accedi con il codice.
2. Tocca **Condividi** (quadrato con la freccia) → **Aggiungi alla schermata Home** → **Aggiungi**.
3. L'icona «Radar» apre l'app a tutto schermo. Senza rete mostra gli ultimi dati scaricati.

Gli stati (interessante / contattato / scartato) e le note restano **solo su quel telefono**.
Se cancelli i dati di Safari o reinstalli l'icona possono andare persi.
Per averli su più dispositivi servirebbe un piccolo archivio in rete (ad esempio Cloudflare KV con una
funzione di Pages protetta da Access): si può aggiungere in seguito.

---

## Uso quotidiano

- **Email:** arriva dopo le 7. GitHub può ritardare l'avvio anche di 15–30 minuti. Se non c'è nulla di nuovo è una riga sola.
  Ogni offerta nell'email apre direttamente la sua scheda nell'app.
- **App → Oggi:** il riepilogo del giorno, il radar delle zone, le novità, le scadenze entro 7 giorni
  e le offerte in libera professione più adatte.
- **App → Offerte:** ricerca per parola; filtri per stato, contratto, distanza, struttura e fonte;
  ordinamento per punteggio, più recenti, scadenza o distanza.
- **App → Scadenze:** tutte le scadenze dichiarate, dalla più vicina.
- **App → Zone:** dove sono le offerte rispetto a casa (il centro del radar è Mezzolombardo, più lontano dal centro = più minuti d'auto).
- **App → Report:** quante offerte per tipo di contratto, novità giorno per giorno e archivio degli ultimi 60 giorni.
- **Scheda di un'offerta:** annuncio originale, indicazioni stradali, scadenza da aggiungere al calendario,
  email di richiesta informazioni già scritta (parte dal tuo telefono solo se la invii tu), stato e appunti.
- **Avvio a mano:** GitHub → **Actions → Radar giornaliero → Run workflow** (manda anche l'email).
- **Dopo una modifica** a `config.yaml` o al programma parte da solo un giro di prova, senza email, e l'app si aggiorna.

Le prime 21 offerte in elenco sono quelle trovate a mano il 12/11/2026 (hanno la nota «Inserito a mano»).
Restano finché non scadono, o per 45 giorni.

## Modifiche senza programmare

Tutto si cambia in `config.yaml`: su GitHub apri il file, tocca la **matita**, modifica, **Commit changes**.
Rispetta gli spazi a inizio riga.

### Aggiungere i feed di Google Alerts

1. Su google.com/alerts, accanto a ogni avviso con consegna «Feed RSS» c'è la piccola icona RSS (grigia): tieni premuto e copia il link.
2. In `config.yaml` aggiungi il link all'elenco `feed_google_alerts` (tre sono già inseriti):

```yaml
feed_google_alerts:
  - "https://www.google.com/alerts/feeds/…primo link…"
  - "https://www.google.com/alerts/feeds/…secondo link…"
```

Gli avvisi che non riguardano il Trentino-Alto Adige vengono scartati.

### Aggiungere una fonte

Copia un blocco sotto `fonti:` e cambia i valori:

```yaml
  - nome: Nome che vuoi vedere nell'app
    tipo: pagina            # pagina = una sola pagina "lavora con noi"; elenco = lista di annunci; rss = feed
    url: https://indirizzo-della-pagina
    affidabilita: struttura # ufficiale | struttura | aggregatore
    datore: Nome della struttura   # facoltativo
    zona: Arco                     # facoltativo: un comune presente in data/comuni.csv
    attiva: true
```

Con `tipo: elenco` puoi aggiungere `parole_link:` (un elenco di parole) per aprire solo i link che le contengono,
come fa la fonte ASUIT.

### Cercare la pagina giusta di un sito

Sotto `esplora:` puoi mettere l'indirizzo di un sito (una APSP, una clinica). A ogni giro il Radar lo apre e
scrive in `data/diagnostica.json` i link che parlano di lavoro, concorsi e avvisi: da lì si sceglie la pagina
da aggiungere alle fonti. Lo stesso file dice, fonte per fonte, quante pagine sono state lette e perché
un annuncio è stato scartato.

### Cambiare i pesi del punteggio

Sezione `pesi:` (la somma dovrebbe restare 100). I punteggi si aggiornano al giro successivo.

### Altre impostazioni utili

- `profilo.tedesco`: `no`, `base` oppure `b2`. Con `no` gli annunci che citano il tedesco perdono punti.
- `profilo.includi_dipendenti`: `false` per vedere solo P.IVA e collaborazioni.
- `profilo.minuti_massimi`: ad esempio `90` per nascondere le offerte più lontane.
- `pdf.leggi`: `false` per non aprire i PDF allegati (il giro è più veloce, ma bandi e avvisi restano con molti «n.d.»).
- `email_contatto`: oggetto e testo dell'email di richiesta informazioni proposta dall'app.
- `giorni_annuncio_datato`: dopo quanti giorni un annuncio senza scadenza è considerato vecchio (ora 120).
- `parole.escludi_titolo` e `parole.fuori_regione`: ruoli e luoghi da scartare.
- Distanze: `data/comuni.csv` (km e minuti da Mezzolombardo, 129 comuni). **Sono stime**: correggile se vuoi.

## Se una fonte non funziona

Il report ha la sezione «Fonti non lette o da controllare». I casi tipici:

| Messaggio | Cosa significa | Cosa fare |
| --- | --- | --- |
| `risposta HTTP 403/404` | il sito rifiuta i programmi o l'indirizzo è cambiato | apri l'indirizzo a mano; se è cambiato, aggiornalo in `config.yaml` |
| `bloccata da robots.txt` | il sito chiede di non essere letto in automatico | il Radar lo rispetta: metti `attiva: false` e seguila con Google Alerts |
| `pagina quasi vuota` | pagina caricata in modo dinamico | come sopra |
| `oggi nessun annuncio… potrebbe aver cambiato struttura` | prima funzionava, ora no | se il messaggio resta per più giorni, chiedi a Claude di sistemare quella fonte |
| `nessun link ad annunci trovato` | non ha mai funzionato | controlla l'indirizzo |

Un annuncio che sparisce dall'elenco della fonte resta visibile 30 giorni con un avviso.
Se il workflow fallisce del tutto, GitHub ti manda un'email.

**Nota onesta:** le regole sono verificate con circa 60 prove su pagine finte (`python tests/prova.py`) e con i giri
veri su GitHub. I siti però cambiano: quando una fonte smette di rendere lo vedi nel report e in `data/diagnostica.json`.

## Com'è fatto

```
config.yaml              impostazioni, fonti, pesi
CONTESTO.md              contesto del progetto
radar/rete.py            scaricamento educato (robots.txt, pause, niente login)
radar/estrai.py          lettura di pagine, feed e PDF, estrazione dei dati
radar/punteggio.py       punteggio 0–100
radar/motore.py          giro quotidiano e memoria (data/annunci.json)
radar/uscite.py          email e costruzione della web app
webapp/                  la web app (HTML, CSS, JavaScript, senza librerie esterne)
data/                    memoria: annunci, stato delle fonti, report, diagnostica, distanze
tests/prova.py           prove offline
.github/workflows/       automazione giornaliera
```

Sul computer: `pip install -r requirements.txt`, poi `python -m radar --senza-email`.
