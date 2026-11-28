---
name: "radar-infermiere"
description: "Usa per il Radar Infermiere P.IVA di Michael: invio lettere alle strutture, controllo risposte, risposte con CV, aggiunta strutture al Radar, report lavoro."
---

# Radar Infermiere P.IVA

Michael Panico è infermiere ASDAA (Bolzano, Medicina interna I) dal 10/08/2026 e vive a Mezzolombardo (TN). Vuole passare alla libera professione in Trentino, con l'obiettivo di 3.000 € netti al mese. Rispondi in italiano, breve, con la risposta per prima (usa l'iPhone).

Repository privato `michaelpanicolhstudio-sys/radar-infermiere` (branch main). App: https://radar-infermiere.pages.dev. Casella di lavoro: infermiere.michaelpanico@gmail.com, letta solo dal Radar via GitHub Actions.

## Regole che non si toccano
- Nessuna email a una struttura senza il «invia» esplicito di Michael. Mai due volte allo stesso indirizzo. Le PEC le invia lui. APSP Vannetti: esclusa (risponde lui via PEC). Brixsana: «per ora no».
- È ancora dipendente pubblico: niente candidature né accettazione di turni prima dell'autorizzazione ASDAA o delle dimissioni. Nelle risposte si può proporre un colloquio o una telefonata conoscitiva, mai una data di inizio.
- Segreti (password per le app, token) solo nei GitHub Secrets, mai in chat. Non condividere le email di Michael con servizi esterni senza il suo ok.
- Il Radar non legge siti dietro login e non inventa dati: se manca, «n.d.».
- Niente subagenti. Fatti presi dal web sempre citati.

## Comandi
- Prima di ogni commit: `python3 tests/prova.py | tail -1 | grep -q "TUTTO OK" &&` …
- Commit: `git -c user.name="Michael" -c user.email="noreply@users.noreply.github.com" commit …`, messaggio in italiano con le righe di attribuzione della sessione.
- Push: `git pull -q --rebase origin main` poi `git -c push.negotiate=true push -q origin main`.
- Avvio a mano del workflow (gh workflow run fallisce per un errore GraphQL): `gh api -X POST repos/michaelpanicolhstudio-sys/radar-infermiere/actions/workflows/radar.yml/dispatches --input file.json` con `{"ref":"main","inputs":{...}}`. Input: solo_posta, rispondi_rif, rispondi_testo, rispondi_allegato.

## Workflow radar.yml
- 7:07 `--pianificato` (report sulla mail di lavoro); ogni 2 ore 7-21 a :37 `--solo-posta` (email solo se ci sono novità, attivo 8-22); su push `--senza-email` (NON legge la posta).
- Salvataggio con `git pull --rebase -X theirs`.

## Inviare lettere (solo dopo «invia»)
Prima di tutto: «preparami / prepariamo» NON è «invia». Prepara la lettera, mostrala e aspetta.

### Apertura (invio unico di una o poche strutture)
1. Aspetta che non ci siano giri in corso (`gh run list -L 1` = completed), poi `git pull`.
2. Salva la selezione completa: copia di config.yaml e della riga `selezione: [...]` in /tmp.
3. In config.yaml metti TEMPORANEAMENTE `selezione: ["<solo i nomi da inviare>"]` (MAI lasciare la selezione completa: dentro ci sono ~20 lettere pronte non autorizzate). Testi su misura in `invio.dedicate`; `invio.gia_conosciute` per chi conosce già Michael (es. Cristani).
4. Imposta `una_tantum` alla data di oggi e cancella `data/invio_una_tantum.txt` se ha già quella data.
5. Prova a secco con `invio.coda(...)`: deve uscire SOLO la struttura autorizzata (assert sul numero). Poi test, commit, push: il giro su push invia (l'invio unico parte anche con `--senza-email`), non serve dispatch.
6. Aspetta la fine del giro, `git pull` e verifica in data/contatti.json `inviata_il` e `rif`.

### Chiusura (obbligatoria, in un solo blocco)
- Usa `set -e` e mai `git commit -a`: aggiungi i file per nome.
- Se `git pull` si blocca per un file non tracciato (es. data/invio_una_tantum.txt creato dal giro), toglilo e rifai il pull PRIMA di toccare altro.
- Rimetti la selezione completa e `una_tantum: ""`; data/invio_una_tantum.txt deve esistere con la data di oggi.
- Prima del push verifica con grep: `una_tantum: ""`, la selezione completa è tornata (es. contiene "Stella Montis"), nessun «TEMPORANEO» in config.yaml.
- Dopo il push controlla il registro: in data/contatti.json gli invii di oggi devono essere solo quelli autorizzati.
- Se qualcosa è andato storto, dillo subito a Michael in parole semplici (cosa, conseguenze, cosa hai controllato).
- Lettera breve: chiede solo se collaborano con partite IVA e se hanno bisogno; la distanza compare solo fino a 50 minuti.

## Controllare le risposte
- `git pull`, poi leggi TUTTO data/contatti.json: per ogni struttura `risposte` (da, data, oggetto, testo, mid) e `mie_risposte`. Non dire mai «non c'è niente» senza averlo letto tutto.
- Una risposta è in attesa se non c'è una `mie_risposte` con data uguale o successiva.
- Conta solo ciò che ha scritto la struttura: il testo salvato può contenere sotto la lettera di Michael citata («Il giorno … ha scritto:» anche su due righe, «From:», «Da "…"», o la lettera incollata senza intestazione), la firma con P.IVA e la nota legale. «Immediatamente / subito» della nota legale, «P.IVA» della firma e «libero professionista» dell'oggetto citato non dicono né il rapporto né la data d'inizio: se la struttura non lo scrive, «n.d.».
- Esito: «ora no, ma mandi il CV / un'offerta / terremo presente la sua disponibilità» è «più avanti»; «coperto da personale dipendente», «non collaboriamo con liberi professionisti», «non hanno questo tipo di rapporto» o «spiacenti di non poter accogliere» (senza richiesta di CV) è «no», anche se promettono di ricontattare.
- Riporta sempre turni e monte ore al mese se la struttura li scrive («7–15 turni/mese da 8 h, max 195 h/mese», «min. 60–80 h/mese»): per la partita IVA sono il dato che decide il guadagno. Se non li scrive, «n.d.».

## Rispondere a una struttura (solo dopo «invia»)
- Dispatch con rispondi_rif = codice R-xxxx, rispondi_testo = testo, rispondi_allegato = nome file in data/allegati/ (es. CV_Michael_Panico_infermiere.pdf).
- Più risposte: una alla volta, aspettando che il giro precedente sia finito (la concurrency di GitHub tiene un solo giro in attesa: un secondo dispatch lo sostituirebbe). Dopo ogni giro verifica `mie_risposte`.
- Il codice Rif. va sempre letto da data/contatti.json, mai scritto a memoria.
- Dopo l'invio aggiorna data/esiti.json (esito e prossimo passo) e, se c'era un promemoria in calendario per rispondere, toglilo.
- La risposta parte come «Re:» con In-Reply-To; nel registro va solo un'impronta sha256, mai il testo né il numero.
- Cellulare da usare nei contatti di lavoro: 346 5787395.

## App e stato delle strutture
- data/esiti.json: per ogni chiave della struttura `esito` (da fare, sì, più avanti, no, da leggere, in attesa), `prossimo` (una frase) e `aggiornato`. Vince sulla lettura automatica finché la struttura non riscrive. Aggiornalo dopo ogni risposta letta o inviata: è ciò che Michael vede in Oggi e Contatti. Nel `prossimo` scrivi i numeri della struttura (diventano bottoni «Chiama»), non quello di Michael.
- Chi chiede il CV o un recapito telefonico aspetta Michael: senza esito a mano l'app mostra «Tocca a te» finché in `mie_risposte` non c'è una sua risposta dello stesso giorno o dopo, poi «Hai risposto». Se il CV era già partito prima verso un altro indirizzo, di' quando e a chi, e che va rimandato a chi lo chiede ora (non che se n'è dimenticato). Un numero scritto da loro («può chiamarci al …») non è una richiesta. Le risposte mandate dal telefono il Radar non le vede: se Michael dice di aver già mandato CV o numero, scrivilo in data/esiti.json.
- Gli appuntamenti fissati (colloqui, telefonate) vanno nel calendario personale in arancione (colorId 6), una sola volta: prima cerca se esiste già. Anche una telefonata promessa è un appuntamento («la chiamo alle 15», «la contatto oggi»); «oggi», «domani», «venerdì» si contano dal giorno della risposta, non da oggi; «la contatteremo» senza giorno né ora non lo è.
- Un esito scritto a mano resta valido se la struttura riscrive lo stesso giorno: prima di aggiornare data/esiti.json leggi tutte le risposte di quel giorno, così il passo non è già vecchio.
- Un colloquio o una telefonata fissati (anche al telefono) vanno in data/esiti.json con giorno e ora nel `prossimo` («martedì 1/12 alle 11») o nel campo `incontro` ({"data": "AAAA-MM-GG", "ora": "HH:MM", "tipo": "telefonata"} se è una chiamata): così compaiono in app e nel calendario dell'app. Una proposta di Michael non ancora confermata («hai proposto…») non è un appuntamento: aggiornala dopo la conferma.

## Report e allarmi
- Per dire cosa c'è di nuovo leggi `data/report/<oggi>.json` (nuovi, aggiornati, problemi) e `data/annunci.json`; per le risposte vale la sezione «Controllare le risposte».
- Nel report metti per primi gli appuntamenti dei prossimi 7 giorni (colloqui e telefonate, da `incontri` dell'app o da data/esiti.json): l'email del mattino li elenca in cima e nell'oggetto, il riassunto in chat deve fare lo stesso.
- Le email dei portali che confermano una candidatura («Candidatura inviata», link /indeedapply/) non sono offerte nuove: non riportarle come novità.
- Gli articoli di giornale (cronaca, interviste a infermieri) non sono offerte, anche se parlano di partita IVA: dalle «novità» toglili, senza prendere datore o contratto dal testo dell'articolo.
- Se un annuncio dice solo la provincia («Provincia di Trento»), nel report scrivi «provincia di Trento (comune n.d.)», non «zona n.d.»: mai il capoluogo né i suoi minuti.
- Titoli in maiuscolo, anche solo in parte («INFERMIERE - Trento e provincia»): riportali come frase leggibile, i nomi di struttura con le iniziali maiuscole («Opera Romani»), sigle, numeri e comuni intatti, senza cambiare cosa dicono; se sono troncati, tagliali a fine parola e chiudili con «…». Se il titolo comincia con il nome del datore già scritto, non ripeterlo. Date sempre «gg/mm/aaaa»; per le scadenze vicine «scade oggi / domani».
- Allarmi in `config.yaml` → `allarmi` (oggi: bando invernale ASUIT di Campiglio / Sèn Jan, guardato su asuit.tn.it, apss.tn.it e opi.tn.it). Scattano una volta per bando (registro `data/allarmi_inviati.json`); non scattano per bandi scaduti, pagine «datate» senza scadenza (oltre 120 giorni) e copie dello stesso bando su un altro sito.
- Aggiungendo un sito o una parola a un allarme, prova prima `uscite.trova_allarmi` sui dati veri con il registro: non deve uscire nessun bando vecchio.

## Aggiungere strutture
- Riga in data/strutture.csv con note «Scelta N …» o «Scartata per ora: motivo». Se il nome esiste già, correggi la riga esistente (altrimenti la lettera non entra in coda).
- Una pagina «lavora con noi» aggiunta come fonte in config.yaml ha sempre un `titolo:` che dice che cercano (anche) un infermiere, ricavato solo da ciò che dice la pagina; se la struttura ha più sedi e la pagina non dice quale, la zona va segnata come da verificare.

## Lezioni
Leggi LEZIONI.md e README.md del repo prima di cambiare codice; aggiungi lì ogni nuovo errore con la regola generale.