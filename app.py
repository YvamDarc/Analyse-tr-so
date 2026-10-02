import hashlib
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from treasury import daily_balances, prepare, read_fec


def euro(value):
    return f'{value:,.2f} €'.replace(',', ' ').replace('.', ',')


def main():
    st.set_page_config(page_title='Analyse trésorerie · V2', layout='wide')
    st.title('Analyse de trésorerie · V2')
    st.caption('Plusieurs FEC • Banques au choix • Une seule reprise des à-nouveaux')
    st.info('Importez les FEC successifs d’une même entité, avec un plan de comptes bancaire stable. '
            'Les soldes sont des soldes comptables en fin de journée.')
    files = st.file_uploader('FEC à analyser', type=['txt', 'csv', 'fec', 'xlsx'], accept_multiple_files=True)
    st.caption('FEC avec en-têtes : tabulation, point-virgule, barre verticale ou virgule ; UTF-8, Windows-1252 ou UTF-16 avec BOM. '
               'Les fichiers sont traités en mémoire sur le serveur Streamlit pendant la session.')
    if not files:
        st.stop()
    frames, seen, summaries = [], set(), []
    for file in files:
        payload = file.getvalue()
        fingerprint = hashlib.sha256(payload).hexdigest()
        if fingerprint in seen:
            st.warning(f'{file.name} : fichier identique déjà importé, ignoré.')
            continue
        seen.add(fingerprint)
        try:
            frame = read_fec(payload, file.name)
        except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
            st.error(str(exc))
            st.stop()
        frames.append(frame)
        summaries.append({'Fichier': file.name, 'Début constaté': frame.Date.min().date(),
                          'Fin constatée': frame.Date.max().date(), 'Lignes': len(frame)})
    st.dataframe(pd.DataFrame(summaries), hide_index=True, width='stretch')
    # A repeated export must not silently double all bank movements. Do not delete
    # individual identical rows: several genuinely separate entries may match.
    ordered = sorted(summaries, key=lambda row: row['Début constaté'])
    overlaps = [(a['Fichier'], b['Fichier']) for i, a in enumerate(ordered)
                for b in ordered[i + 1:] if b['Début constaté'] <= a['Fin constatée']]
    if overlaps:
        st.error('Périodes de FEC qui se chevauchent : ' + '; '.join(f'{a} / {b}' for a, b in overlaps)
                 + '. Retirez les exports redondants ou fournissez des périodes distinctes pour éviter le double comptage.')
        st.stop()
    df = pd.concat(frames, ignore_index=True)
    catalog = df[['CompteNum', 'CompteLib']].drop_duplicates('CompteNum').sort_values('CompteNum')
    labels = dict(zip(catalog.CompteNum, catalog.CompteLib))
    st.subheader('1 · Banques et reprise')
    all_accounts = st.checkbox('Afficher aussi les comptes hors 512 / 514 / 517')
    options = catalog.CompteNum.tolist() if all_accounts else [c for c in catalog.CompteNum if c.startswith(('512', '514', '517'))]
    accounts = st.multiselect('Comptes bancaires à cumuler', options,
                             default=[c for c in options if c.startswith('512')],
                             format_func=lambda c: f'{c} — {labels[c]}')
    if not accounts:
        st.warning('Sélectionnez au moins un compte bancaire.')
        st.stop()
    journals = sorted(df.JournalCode.unique())
    an = st.multiselect('Journal / journaux d’à-nouveaux', journals,
                       default=[j for j in journals if j.upper() == 'AN'])
    if not an:
        st.warning('Aucun journal d’à-nouveaux sélectionné. Choisissez le code utilisé dans vos FEC '
                   '(AN, RAN, etc.), ou confirmez plus bas une ouverture nulle.')
    bank_an = df.loc[df.CompteNum.isin(accounts) & df.JournalCode.isin(an)]
    default_date = bank_an.Date.min() if not bank_an.empty else df.Date.min()
    # Reset confirmation whenever files or accounting parameters change.
    context = hashlib.sha256(('|'.join(sorted(seen)) + repr(accounts) + repr(an)).encode()).hexdigest()[:16]
    restart = st.date_input('Date de reprise : seule date d’à-nouveaux conservée',
                            value=default_date.date(), min_value=df.Date.min().date(),
                            max_value=df.Date.max().date(), key='restart_' + context)
    st.caption('Tous les mouvements antérieurs à la reprise sont exclus. À compter de cette date, '
               'tous les mouvements ordinaires sont conservés ; les à-nouveaux des autres dates sont exclus.')
    kept, audit = prepare(df, accounts, an, restart)
    initial = kept.loc[kept.Decision.eq('Conservée — à-nouveau initial')]
    missing = [c for c in accounts if c not in initial.CompteNum.unique()]
    opening = initial.groupby('CompteNum').MouvementCentimes.sum().reindex(accounts, fill_value=0) / 100
    st.dataframe(opening.rename('Solde d’ouverture (€)').to_frame(), width='stretch')
    excluded = audit.loc[audit.Decision.str.startswith('Exclue')]
    st.write(f'**{len(initial)}** lignes d’à-nouveaux conservées · **{len(excluded)}** lignes exclues de l’analyse.')
    with st.expander('Vérifier les à-nouveaux et les exclusions'):
        st.dataframe(audit.loc[audit.JournalCode.isin(an) | audit.Decision.str.startswith('Exclue')],
                     hide_index=True, width='stretch')
    decision_key = hashlib.sha256((context + str(restart)).encode()).hexdigest()[:16]
    if missing:
        st.warning('Aucun à-nouveau à la date choisie pour : ' + ', '.join(missing)
                   + '. Le solde de départ de ces comptes sera nul ; cela convient uniquement si ces comptes étaient à zéro ou ont été ouverts ensuite.')
        if not st.checkbox('Je confirme que ces comptes ont un solde d’ouverture nul', key='zero_' + decision_key):
            st.stop()
    if not st.checkbox('Je confirme les journaux d’à-nouveaux et la date de reprise', key='confirm_' + decision_key):
        st.stop()
    st.subheader('2 · Période analysée')
    start = st.date_input('Afficher à partir du', value=restart, min_value=restart,
                          max_value=df.Date.max().date(), key='start_' + decision_key)
    end = st.date_input('Afficher jusqu’au (inclus)', value=df.Date.max().date(),
                        min_value=start, key='end_' + decision_key + str(start))
    if (pd.Timestamp(end) - pd.Timestamp(restart)).days > 36525:
        st.error('La période dépasse 100 ans : vérifiez les dates.')
        st.stop()
    st.caption('La fin proposée est la dernière écriture de l’ensemble des FEC, pas nécessairement la clôture. '
               'Ajustez-la à la période couverte. Les jours sans mouvement reprennent le dernier solde connu.')
    if any((pd.Timestamp(b['Début constaté']) - pd.Timestamp(a['Fin constatée'])).days > 1
           for a, b in zip(ordered, ordered[1:])):
        st.warning('Des intervalles existent entre les périodes des fichiers. Vérifiez qu’aucun exercice ou mouvement ne manque : '
                   'le dernier solde sera reporté pendant ces intervalles.')
    if not st.checkbox('Je confirme que les FEC couvrent tous les mouvements de la reprise à la fin choisie',
                       key='coverage_' + decision_key + str(end)):
        st.stop()
    daily = daily_balances(kept, accounts, restart, end).loc[str(start):]
    view = st.selectbox('Solde à afficher', ['Total'] + accounts,
                        format_func=lambda c: 'Cumul des banques sélectionnées' if c == 'Total' else f'{c} — {labels[c]}')
    series = daily[view]
    floor = max(0.0, float(series.min()))
    a, b, c, d = st.columns(4)
    a.metric('Minimum observé', euro(series.min()))
    b.metric('Moyenne journalière', euro(series.mean()))
    c.metric('Maximum observé', euro(series.max()))
    d.metric('Jours analysés', len(series))
    width = st.number_input('Largeur des tranches (€)', min_value=1, value=5000, step=1000)
    lo = min(0, float(series.min()) // width * width)
    hi = max(width, (float(series.max()) // width + 1) * width)
    if (hi - lo) / width > 2000:
        st.warning('Augmentez la largeur des tranches pour limiter le graphique à 2 000 tranches.')
        st.stop()
    fig = go.Figure(go.Histogram(x=series, xbins=dict(start=lo, end=hi, size=width),
                                 marker_color='#3978b8', name='Jours',
                                 hovertemplate='Solde : %{x} €<br>Nombre de jours : %{y}<extra></extra>'))
    if floor > 0:
        fig.add_vrect(x0=0, x1=floor, fillcolor='#35b779', opacity=0.22, line_width=0, layer='below')
        fig.add_vline(x=floor, line_dash='dash', line_color='#15803d')
    fig.update_layout(title='Répartition des soldes journaliers', xaxis_title='Solde comptable (€)',
                      yaxis_title='Nombre de jours', bargap=0.05, template='plotly_white',
                      xaxis_range=[lo, hi], yaxis=dict(rangemode='tozero', dtick=1 if len(series) < 20 else None))
    st.plotly_chart(fig, width='stretch')
    if floor > 0:
        st.success(f'Zone verte : {euro(floor)} de trésorerie non mobilisée sur la période. '
                   'Le solde de fin de journée n’est jamais descendu sous ce montant.')
    else:
        st.info('Le minimum est nul ou négatif : aucune zone de trésorerie positive non mobilisée.')
    st.caption('Constat historique sur les soldes de fin de journée ; les creux intrajournaliers et les besoins futurs ne sont pas mesurés. '
               'Le minimum du cumul est calculé sur les soldes cumulés jour par jour, pas en additionnant les minima des banques.')
    curve = go.Figure(go.Scatter(x=series.index, y=series, mode='lines', name=view, line_color='#3978b8'))
    curve.update_layout(title='Évolution du solde journalier', yaxis_title='Solde (€)', template='plotly_white')
    st.plotly_chart(curve, width='stretch')
    st.subheader('3 · Contrôles et exports')
    st.dataframe(daily, width='stretch')
    st.download_button('Télécharger les soldes en CSV', daily.to_csv(sep=';', decimal=',').encode('utf-8-sig'),
                       'soldes_journaliers.csv', 'text/csv')
    output = io.BytesIO()
    params = pd.DataFrame({'Paramètre': ['Journaux AN', 'Reprise', 'Début affiché', 'Fin affichée', 'Comptes'],
                          'Valeur': [', '.join(an), str(restart), str(start), str(end), ', '.join(accounts)]})
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        daily.to_excel(writer, sheet_name='Soldes journaliers')
        # Prefix untrusted strings that Excel could otherwise interpret as formulas.
        safe_audit = audit.copy()
        for col in safe_audit.select_dtypes(include=['object', 'string']):
            safe_audit[col] = safe_audit[col].map(lambda v: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v)
        safe_audit.to_excel(writer, sheet_name='Audit des lignes', index=False)
        params.to_excel(writer, sheet_name='Paramètres', index=False)
    st.download_button('Télécharger Excel : soldes, audit et paramètres', output.getvalue(),
                       'analyse_tresorerie_v2.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


if __name__ == '__main__':
    main()
