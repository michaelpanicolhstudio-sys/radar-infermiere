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
- 2026-11-13 — Cambiando `VERSIONE_REGOLE`, 8 annunci VdS sono finiti tra gli «aggiornati» dell'email solo perché il Radar ne aveva riscritto il titolo (visto nel report: i «cambi» erano tutti `titolo:`). Regola: le differenze dovute a nuove regole di lettura non sono novità; solo la scadenza si segnala sempre.
- 2026-11-13 — «Altenheim St. Pankraz» risultava a Bolzano (visto confrontando datore e zona in `annunci.json`): il testo nominava Bozen. Regola: se il nome della struttura contiene un comune, quello è il posto di lavoro.
- 2026-11-13 — I titoli della bacheca VdS presi dall'indirizzo erano tedesco illeggibile («berufsbild nr 64 der viiter funktionsebene…»). Regola: un titolo ricavato da un indirizzo va tradotto in parole semplici, usando solo ciò che l'indirizzo dice.
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
- Bacheca VdS: i titoli ora sono tradotti dall'indirizzo («Infermiere/a – part-time…»); resta da capire se la pagina ha un titolo vero (dal cloud il sito non si apre: proxy).
- Bacheca VdS: l'annuncio di «Stiftung Lorenzerhof» (swh/475) cita «Casa di riposo San Pancrazio» ed è messo a San Pancrazio; il Lorenzerhof dovrebbe essere a Lana: verificare a mano quale struttura pubblica davvero quel bando.
- Melittaklinik («Lavora con noi») e Brixsana («Auch im Job: in besten Händen»): titoli poco chiari dalle pagine fisse; si può aggiungere `titolo:` in `config.yaml` come per Vinzenzhaus.
- Claraheim risulta a Cornedo all'Isarco (Collepietra/Steinegg è frazione di Cornedo: probabilmente giusto, da confermare).
- Ancora non provati dal vero: lettura delle risposte, Excel allegato, invito all'incontro.
