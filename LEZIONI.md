# Lezioni imparate (registro per le revisioni automatiche)

Questo file è la memoria di chi migliora il Radar. Va letto **prima** di toccare il codice
e aggiornato **alla fine** di ogni revisione: cosa si è sbagliato, come lo si è scoperto, la regola che ne esce.

## Regole di lavoro
- Prima i dati veri: `data/diagnostica.json`, `data/fonti_stato.json`, `data/annunci.json`, `data/posta_stato.json`, ultimo `data/report/`.
- Un difetto alla volta: prova che lo riproduce in `tests/prova.py`, correzione, `python3 tests/prova.py` tutto OK, poi commit.
- Massimo 3 correzioni per revisione, commit piccoli con messaggio in italiano. Mai committare se le prove falliscono.
- Mai inviare email a strutture, mai candidarsi, mai toccare i segreti, mai leggere siti dietro login o vietati da robots.txt.
- Se un dato manca: «n.d.». Mai inventare indirizzi, compensi, date.
- Dopo una modifica all'app: controllare che `node --check webapp/app.js` passi e, se possibile, guardare una schermata 390×844.
- Se un cambio di regole deve rileggere annunci già in memoria: aumentare `VERSIONE_REGOLE` (o `VERSIONE_PDF`) in `radar/motore.py`.

## Lezioni (dalla più recente)
- 2026-11-13 — Registro della posta: una funzione che rinomina `registra` dentro sé stessa si richiamava all'infinito. Rinominando una funzione passata come argomento, salvare prima l'originale in un'altra variabile.
- 2026-11-13 — «euro-pea» (Unione europea, a capo) veniva preso per un importo: le regex sui soldi devono chiedere una cifra vicina.
- 2026-11-13 — I siti fatti con Elementor chiamano «widget» ogni blocco del contenuto: non usare quel nome per riconoscere i menu laterali.
- 2026-11-13 — «Provincia di Bolzano», «Tribunale di Trento» non sono la sede di lavoro: i capoluoghi contano solo se non preceduti da un ente.
- 2026-11-13 — «38,5 Stunden» veniva letto come 5 ore: nei numeri controllare cosa c'è prima della cifra.
- 2026-11-13 — Una «scadenza» uguale al giorno di pubblicazione è la data del post letta per errore.
- 2026-11-13 — Avvisi con più tariffe (medici 80 €, infermieri 40 €): vale quella più vicina alla parola «infermiere».
- 2026-11-13 — La partita IVA dell'ente («P.IVA 0123…») non è un contratto in libera professione; «spirito di collaborazione» non è un contratto di collaborazione.
- 2026-11-13 — ASUIT funziona solo con `www.`; il bollettino regionale vieta i programmi (robots.txt); i siti `*.upipa.opencontent.it` non si lasciano leggere.
- 2026-11-13 — Un giro manuale di notte segnava come fatto il giro delle 7 e saltava l'email: solo i giri pianificati scrivono `data/ultimo_giro.txt`.

## Problemi aperti (da guardare nelle prossime revisioni)
- OPI Trento: gli allegati PDF degli annunci non vengono trovati (la diagnostica `senza_pdf` mostra solo icone): capire dove sono.
- ASUIT «conferimento incarichi»: il compenso degli infermieri nel PDF non viene letto (si vede solo quello dei medici).
- Bacheca VdS: il titolo viene dal link (es. «Berufskrankenpflegerin berufsbild nr 64…»): cercare un titolo più leggibile nella pagina.
- Claraheim risulta a Cornedo all'Isarco: verificare la zona delle case di riposo Eggental.
- Ancora non provati dal vero: lettura delle risposte, Excel allegato, invito all'incontro.
