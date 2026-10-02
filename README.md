# Analyse trésorerie — V2

Application Streamlit pour analyser plusieurs FEC successifs d'une même entité.

## Utilisation

1. Importer les FEC TXT, CSV, FEC ou XLSX avec leurs en-têtes normalisés.
2. Sélectionner les comptes bancaires (512 par défaut ; 514/517 disponibles ; autres comptes sur demande).
3. Sélectionner le ou les journaux d'à-nouveaux (AN par défaut) et la date de reprise.
4. Vérifier l'ouverture et l'audit, puis confirmer. Seuls les AN de cette date sont conservés. Toutes les lignes antérieures à la reprise sont exclues, y compris les mouvements ordinaires. Les mouvements ordinaires du jour de reprise sont conservés.
5. Confirmer la période réellement couverte, puis analyser le cumul ou une banque et exporter les résultats.

Les fichiers identiques sont ignorés. Les fichiers dont les intervalles de dates se chevauchent sont bloqués : importer uniquement des périodes distinctes. Les lignes identiques d'un même fichier ne sont jamais supprimées automatiquement. Si le plan de comptes change entre exercices, harmoniser les numéros bancaires avant import.

Le calcul est Débit moins Crédit, en centimes entiers, puis cumul journalier. Tous les jours calendaires sont inclus. Un début d'affichage ultérieur ne réinitialise pas le solde. La date finale proposée est la dernière écriture de tous les comptes des FEC, ajustable jusqu'à la clôture réelle. Les jours sans mouvement reportent le solde précédent ; l'application ne peut pas détecter tous les mouvements manquants. Un compte sans AN exige la confirmation d'une ouverture nulle ; sinon fournir un FEC avec la bonne reprise.

La zone verte s'arrête au minimum exact des soldes affichés, indépendamment des tranches de l'histogramme. Elle est absente si le minimum est négatif ou nul. Ce constat historique sur les soldes comptables de fin de journée n'établit pas un montant disponible pour un placement futur.

Les fichiers sont traités en mémoire sur le serveur Streamlit, sans sauvegarde applicative ni cache partagé. L'application n'effectue aucun envoi vers un service tiers. Ils ne restent donc pas exclusivement dans le navigateur. Ne pas déposer de vrais FEC dans ce dépôt GitHub.

## Streamlit Community Cloud

Choisir le dépôt `YvamDarc/Analyse-tr-so`, la branche contenant la V2 et `app.py` comme fichier principal (Python 3.11 ou 3.12). L'ancien point d'entrée `Analyse TRESO.py` fonctionne aussi. `requirements.txt` contient les dépendances. Aucune installation locale n'est nécessaire pour l'utilisateur.

La V2 attend des colonnes FEC (`JournalCode`, `EcritureDate`, `CompteNum`, `Debit`, `Credit` au minimum). L'ancien Excel simplifié Date/Débit/Crédit n'est pas un FEC et n'est pas accepté par ce nouveau parcours.

## Vérification technique

`python -m unittest discover -s tests -v`

`streamlit run app.py`
