"""Pure FEC parsing and daily cash reconstruction; amounts use integer cents."""
import csv
import io
import re
from decimal import Decimal, InvalidOperation

import pandas as pd

REQUIRED = ['JournalCode', 'EcritureDate', 'CompteNum', 'Debit', 'Credit']


def cents(value):
    value = re.sub(r'[\s\u00a0\u202f€]', '', str(value)).replace(',', '.')
    if not value:
        return 0
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount * 100 != (amount * 100).to_integral_value():
            raise ValueError()
        return int(amount * 100)
    except (InvalidOperation, ValueError):
        raise ValueError(f'Montant invalide : {value!r}') from None


def read_fec(data, name):
    if name.lower().endswith('.xlsx'):
        df = pd.read_excel(io.BytesIO(data), dtype=str, keep_default_na=False)
    else:
        encoding = 'utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            text = data.decode('cp1252')
        header = text.splitlines()[0] if text.splitlines() else ''
        delimiters = ['\t', ';', '|', ',']
        sep = max(delimiters, key=lambda s: len(next(csv.reader([header], delimiter=s))))
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip().lstrip('\ufeff') for c in df.columns]
    missing = set(REQUIRED) - set(df.columns)
    if missing:
        raise ValueError(f'{name} : colonnes absentes : {", ".join(sorted(missing))}')
    if df.empty:
        raise ValueError(f'{name} : fichier vide.')
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    raw = df['EcritureDate']
    dates = pd.Series(pd.NaT, index=df.index, dtype='datetime64[ns]')
    for fmt in ('%Y%m%d', '%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        dates = dates.fillna(pd.to_datetime(raw, format=fmt, errors='coerce'))
    bad = dates.isna() | df['CompteNum'].eq('') | df['JournalCode'].eq('')
    if bad.any():
        lines = ', '.join(str(i + 2) for i in df.index[bad][:10])
        raise ValueError(f'{name} : date, compte ou journal invalide aux lignes {lines}.')
    df['Date'] = dates.dt.normalize()
    for col in ('Debit', 'Credit'):
        values = []
        for i, value in enumerate(df[col]):
            try:
                values.append(cents(value))
            except ValueError as exc:
                raise ValueError(f'{name}, ligne {i + 2}, {col} : {exc}') from exc
        df[col + 'Centimes'] = values
    df['MouvementCentimes'] = df['DebitCentimes'] - df['CreditCentimes']
    df['Source'] = name
    df['LigneSource'] = range(2, len(df) + 2)
    if 'CompteLib' not in df:
        df['CompteLib'] = ''
    return df


def prepare(df, accounts, journals, restart):
    restart = pd.Timestamp(restart)
    bank = df.loc[df.CompteNum.isin(accounts)].copy()
    is_an = bank.JournalCode.isin(journals)
    bank['Decision'] = 'Conservée — mouvement'
    bank.loc[is_an & bank.Date.eq(restart), 'Decision'] = 'Conservée — à-nouveau initial'
    bank.loc[is_an & bank.Date.ne(restart), 'Decision'] = 'Exclue — à-nouveau hors reprise'
    bank.loc[bank.Date.lt(restart), 'Decision'] = 'Exclue — antérieure à la reprise'
    return bank.loc[bank.Decision.str.startswith('Conservée')].copy(), bank


def daily_balances(kept, accounts, restart, end):
    index = pd.date_range(restart, end, name='Date')
    if len(index) == 0:
        raise ValueError('La fin doit être postérieure ou égale à la reprise.')
    changes = kept.groupby(['Date', 'CompteNum']).MouvementCentimes.sum().unstack(fill_value=0)
    changes = changes.reindex(index=index, columns=accounts, fill_value=0).fillna(0)
    result = changes.cumsum() / 100
    result['Total'] = result.sum(axis=1)
    return result
