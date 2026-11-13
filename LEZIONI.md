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
- 2026-11-13 — Il bando ASUIT di Cavalese (aperto fino al 31/12) risultava scaduto il 22/10: la frase era «entro il giorno 2 ottobre. AGGIORNAMENTO DI DATA 22/10/2026!» (visto confrontando la pagina con il suo PDF in `annunci.json`: stesso PDF, due scadenze diverse). Regola: la data di una scadenza va cercata nella stessa frase della parola «entro/scadenza».
- 2026-11-13 — Lo stesso PDF ASUIT era sia allegato della pagina sia annuncio a sé (visto cercando in `annunci.json` i PDF presenti in più voci). Regola: un PDF già allegato a una pagina non è un annuncio a parte, salvo che la pagina risulti scaduta e il PDF no.
- 2026-11-13 — Claraheim, Leoheim e Peter Paul Schrott (Eggental) erano tre voci per un solo bando: stesso PDF caricato tre volte sul sito VdS («…_0.pdf», «…_1.pdf»), stessa scadenza, zone diverse. Regola: un bando comune si mostra una volta, scrivendo le altre strutture («Stesso bando anche per: …»).
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
- Bacheca VdS, Lorenzerhof (swh/475): chiarito in parte. Il testo è lo stesso bando di St. Pankraz (stessi profili, «18, 20 e 22 ore», stessa scadenza 20/11), quindi è giusto che sia un doppione di St. Pankraz. Resta da capire perché lo pubblichi il Lorenzerhof (forse gestione comune).
- OPI Trento, PDF mancanti: dal cloud le pagine opi.tn.it non si aprono (proxy 403, anche con WebFetch): serve un giro vero con la diagnostica `senza_pdf` più ricca, o un controllo a mano di Michael su dove sta l'allegato (link esterno? visualizzatore?).
- Bacheca VdS: la pagina in italiano (`/it/jobs`) ha titoli veri in italiano («cercasi-infermierea-professionale»): si potrebbe leggere quella al posto di `/de/jobs`.
- Dopo il giro di prova del 13/11 (regole 5): controllare che Cavalese abbia scadenza 31/12 e che le tre case Eggental siano una voce sola.
- Melittaklinik («Lavora con noi») e Brixsana («Auch im Job: in besten Händen»): titoli poco chiari dalle pagine fisse; si può aggiungere `titolo:` in `config.yaml` come per Vinzenzhaus.
- Claraheim risulta a Cornedo all'Isarco (Collepietra/Steinegg è frazione di Cornedo: probabilmente giusto, da confermare).
- Ancora non provati dal vero: lettura delle risposte, Excel allegato, invito all'incontro.
