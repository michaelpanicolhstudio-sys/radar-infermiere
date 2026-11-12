# Radar Infermiere P.IVA

Ogni mattina alle 7 circa questo programma:

1. legge le fonti elencate in `config.yaml` (OPI Trento e Bolzano, UPIPA, ASUIT, SABES, cliniche, i tuoi Google Alerts);
2. estrae da ogni annuncio datore, contratto, compenso, ore e turni, zona, scadenza;
3. dà un punteggio da 0 a 100 (contratto, compenso, distanza da Mezzolombardo, turni, fonte);
4. confronta con il giorno prima e ti manda **un'email** con novità, scadenze e le 5 offerte migliori;
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
6. Su GitHub aggiungi il segreto `APP_URL` con quell'indirizzo: comparirà nelle email.

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
- **App → Offerte:** ordinate per punteggio; filtri per stato, contratto, distanza e fonte.
- **App → Scadenze:** prossimi 7 e 30 giorni (solo gli annunci che dichiarano una scadenza).
- **App → Report:** archivio degli ultimi 60 giorni.
- **App → Mappa:** dove sono le offerte rispetto a casa.
- **Avvio a mano:** GitHub → **Actions → Radar giornaliero → Run workflow**.

Le prime 21 offerte in elenco sono quelle trovate a mano il 12/11/2026 (hanno la nota «Inserito a mano»).
Restano finché non scadono, o per 45 giorni.

## Modifiche senza programmare

Tutto si cambia in `config.yaml`: su GitHub apri il file, tocca la **matita**, modifica, **Commit changes**.
Rispetta gli spazi a inizio riga.

### Aggiungere i feed di Google Alerts

1. Su google.com/alerts, accanto a ogni avviso con consegna «Feed RSS» c'è l'icona arancione: copia il link.
2. In `config.yaml` sostituisci `feed_google_alerts: []` con:

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

Eremo e KOS sono già in elenco ma spenti: manca l'indirizzo della loro pagina «lavora con noi».

### Cambiare i pesi del punteggio

Sezione `pesi:` (la somma dovrebbe restare 100). I punteggi si aggiornano al giro successivo.

### Altre impostazioni utili

- `profilo.tedesco`: `no`, `base` oppure `b2`. Con `no` gli annunci che citano il tedesco perdono punti.
- `profilo.includi_dipendenti`: `false` per vedere solo P.IVA e collaborazioni.
- `profilo.minuti_massimi`: ad esempio `90` per nascondere le offerte più lontane.
- Distanze: `data/comuni.csv` (km e minuti da Mezzolombardo). **Sono stime**: correggile se vuoi.

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

**Nota onesta:** il programma è stato provato con pagine finte (`python tests/prova.py`), non sui siti veri,
perché l'ambiente in cui è stato scritto non poteva collegarsi. I primi giri servono a capire
quali fonti rispondono bene: aspettati qualche giorno di aggiustamenti.

## Com'è fatto

```
config.yaml              impostazioni, fonti, pesi
CONTESTO.md              contesto del progetto
radar/rete.py            scaricamento educato (robots.txt, pause, niente login)
radar/estrai.py          lettura di pagine e feed, estrazione dei dati
radar/punteggio.py       punteggio 0–100
radar/motore.py          giro quotidiano e memoria (data/annunci.json)
radar/uscite.py          email e costruzione della web app
webapp/                  la web app (HTML, CSS, JavaScript, senza librerie esterne)
data/                    memoria: annunci, stato delle fonti, report, distanze
tests/prova.py           prove offline
.github/workflows/       automazione giornaliera
```

Sul computer: `pip install -r requirements.txt`, poi `python -m radar --senza-email`.
