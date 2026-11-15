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
- 2026-11-15 — ASUIT SLP 15/26 (Campiglio e Sèn Jan) risultava scaduto il 13/08, ma il PDF dice 10/09 (visto confrontando `scadenza` e `da_pdf.scadenza` in `annunci.json`): sotto il titolo «Date e scadenze» la prima data era quella della delibera («n. 634 di data 13 agosto»). Regola: una data che segue «deliberazione/determinazione/decreto n. …» è la data di un atto, mai una scadenza.
- 2026-11-15 — ASUIT Cavalese (avviso aperto) risultava scaduto dal 26/10 mentre il suo PDF chiude il 31/12, e il PDF restava una voce a parte (stesso confronto pagina/PDF). Regola: se pagina e bando PDF danno due scadenze diverse vale la più lontana (una proroga sta sulla pagina, la chiusura vera degli avvisi aperti sta nel PDF), con l'avviso «Scadenza dal bando PDF».
- 2026-11-14 (sera) — Le selezioni ASUIT SC 04/26–13/26 hanno due sessioni (15/11 e 11/12), ma l'annuncio scritto a mano aveva solo la prima: dal 16/11 sarebbe risultato scaduto e poi tolto (visto confrontando `nota_manuale` con `scadenza` in `annunci.json`). Regola: un annuncio a mano con più date si scrive con `scadenze: [...]`; il Radar mostra la prima non passata e lo segnala come aggiornamento quando passa alla successiva.
- 2026-11-14 (sera) — «Study nurse» di Eurac e la Residenza Annenberg di Laces erano senza datore (visto cercando in `annunci.json` le voci con `datore` vuoto): «Istituto» non era tra gli enti riconosciuti e «Residenza per anziani…» veniva scartata come frase. Regola: «Istituto/Residenza per (la/anziani)…» è un nome; un nome tutto in maiuscolo si riscrive in minuscolo leggibile, lasciando le sigle.
- 2026-11-14 — Un errore di rete di un giorno cancellava la lettura buona del giorno prima (APSP San Giuseppe di Primiero e Villa Maria: `estratto` vuoto e avviso «Pagina non letta» in `annunci.json`, confrontando con la versione del 13/11 nella storia git). Regola: se un sito non risponde per un problema passeggero, si tiene l'ultima lettura buona; solo un 404 dice che la pagina non c'è più.
- 2026-11-14 — L'annuncio scritto a mano (San Giuseppe, OPI) vinceva sul doppione UPIPA ma non aveva compenso né email, che invece il doppione aveva (visto guardando chi nascondeva chi tra le voci con `doppione_di`). Regola: tra doppioni dello stesso bando si mostra uno solo, ma con tutti i dati che gli altri conoscono, dicendo da dove vengono. I dati presi in prestito si ricalcolano a ogni giro e non sono «aggiornamenti».
- 2026-11-14 — Titoli di pagine fisse poco chiari (Melittaklinik «Lavora con noi», Brixsana «Auch im Job…»): si scrive `titolo:` in `config.yaml` usando solo ciò che dice la pagina.
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
- Regole a 7 (15/11): verificato nel giro di prova. ASUIT Cavalese è aperto fino al 31/12 (una voce sola, il PDF è suo doppione, unico «aggiornato» del report); SLP 15/26 ora scade il 10/09; la proroga Vannetti (27/11) resta. Da controllare nei prossimi giri che nessun altro annuncio cambi scadenza in modo strano per la nuova regola.
- ASUIT SC 04/26–13/26 (scritto a mano): zona «Mezzolombardo» a 0 minuti nonostante le molte sedi. Michael il 15/11 ha detto di lasciarla così: non riproporlo.
- Claraheim risulta a Cornedo all'Isarco (Collepietra/Steinegg è frazione di Cornedo: probabilmente giusto, da confermare).
- Doppioni Vannetti: il concorso visto su UPIPA e su OPI Trento (scadenza 13/11) non era unito perché già scaduto; ora non si vede più, ma se torna un caso simile con scadenza futura va controllato che la regola «stessa zona e scadenza» lo unisca.
- Rete guasta: verificato nel giro di prova del 14/11 sera (VdS non rispondeva: gli 8 annunci sono rimasti con estratto pieno, nessun avviso «Pagina non letta», nessuno segnato come sparito).
- Giro di prova del 14/11 dopo le correzioni: San Giuseppe di Primiero ora mostra il compenso preso da UPIPA (con l'avviso); Melittaklinik e Brixsana hanno il titolo nuovo; nessun problema segnalato.
- SABES graduatoria permanente (scritta a mano): la nota dice «Scadenze successive: 31/05 e 30/09» senza anno; se Michael conferma che sono del 2027 si possono aggiungere in `scadenze`, così non sparisce dopo il 31/01.
- Regole a 6 (14/11 sera): verificato nel giro di prova, Eurac e Annenberg hanno il datore, nessun «aggiornato» dovuto al datore riscritto; ASUIT SC 04/26 ha `scadenze` e passerà all'11/12 dal 16/11 (da controllare quel giorno).
- Dal cloud non si aprono né opi.tn.it/opibz.it né apspgrazioli.it né jobs.stiftung-st-elisabeth.it (proxy 403): APSP Grazioli è a zero da 8 giorni perché «Lavora con noi» linka solo una selezione OSS; forse va letta anche `Albo-online/Concorsi-e-selezioni` (da verificare in un giro vero).
- Ancora non provati dal vero: lettura delle risposte, Excel allegato, invito all'incontro.
