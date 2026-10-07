#!/usr/bin/env python3
"""Apply the GLOA look to login.galaxref.com for every app that signs in through it.

    python3 scripts/apply_branding.py            apply to every OAuth-enabled app client
    python3 scripts/apply_branding.py --dry-run  list the clients, change nothing

Cognito's managed login has one "style" per app client. This keeps them all the
same, from the files in branding/:

    settings.json         colors, layout (GLOA navy buttons/links, no page header)
    form-logo.png         the GLOA shield, centered above "Sign in" in the sign-in box
    default-assets.json   Cognito's own icons/graphics (light mode), kept as-is

Run it after changing anything in branding/, and whenever an app is converted
to sign in through login.galaxref.com (its client then becomes OAuth-enabled).
Branding is managed here, not in each app's CloudFormation template, so there is
one copy of it.
"""

import base64
import json
import sys
from pathlib import Path

import boto3

POOL_ID = 'us-east-1_oXFiLITO7'
ROOT = Path(__file__).resolve().parent.parent / 'branding'


def load_branding():
    settings = json.loads((ROOT / 'settings.json').read_text())
    assets = [
        {**a, 'Bytes': base64.b64decode(a['Bytes'])}
        for a in json.loads((ROOT / 'default-assets.json').read_text())
    ]
    assets.append({
        'Category': 'FORM_LOGO',
        'ColorMode': 'LIGHT',
        'Extension': 'PNG',
        'Bytes': (ROOT / 'form-logo.png').read_bytes(),
    })
    return settings, assets


def oauth_clients(cognito):
    clients = []
    paginator = cognito.get_paginator('list_user_pool_clients')
    for page in paginator.paginate(UserPoolId=POOL_ID, MaxResults=60):
        for c in page['UserPoolClients']:
            detail = cognito.describe_user_pool_client(UserPoolId=POOL_ID, ClientId=c['ClientId'])['UserPoolClient']
            if detail.get('AllowedOAuthFlowsUserPoolClient'):
                clients.append((c['ClientId'], c['ClientName']))
    return clients


def main():
    dry_run = '--dry-run' in sys.argv
    session = boto3.Session(profile_name='gloa', region_name='us-east-1')
    cognito = session.client('cognito-idp')
    settings, assets = load_branding()

    clients = oauth_clients(cognito)
    if not clients:
        print('No app clients sign in through login.galaxref.com yet.')
        return
    for client_id, name in clients:
        try:
            existing = cognito.describe_managed_login_branding_by_client(
                UserPoolId=POOL_ID, ClientId=client_id)['ManagedLoginBranding']
        except cognito.exceptions.ResourceNotFoundException:
            existing = None
        action = 'update' if existing else 'create'
        if dry_run:
            print(f'would {action}: {name} ({client_id})')
            continue
        if existing:
            cognito.update_managed_login_branding(
                UserPoolId=POOL_ID,
                ManagedLoginBrandingId=existing['ManagedLoginBrandingId'],
                UseCognitoProvidedValues=False,
                Settings=settings,
                Assets=assets)
        else:
            cognito.create_managed_login_branding(
                UserPoolId=POOL_ID,
                ClientId=client_id,
                UseCognitoProvidedValues=False,
                Settings=settings,
                Assets=assets)
        print(f'{action}d: {name} ({client_id})')


if __name__ == '__main__':
    main()
