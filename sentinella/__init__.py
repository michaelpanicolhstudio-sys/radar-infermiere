"""Sentinella: legge la mail principale di Michael e lo avvisa solo per le cose importanti.

Bollette e contratti di luce e gas, prenotazioni Airbnb e Booking, appuntamenti e scadenze.
Non risponde, non cancella, non sposta nulla: legge in sola lettura e manda un'email di avviso
dalla stessa casella a sé stessa, con un file .ics per ogni data da mettere in calendario.

Nel repository salva solo impronte dei messaggi già visti (mai mittenti, oggetti o testi).
"""
