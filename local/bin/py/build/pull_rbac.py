#!/usr/bin/env python3

import argparse
import sys
import requests
import json
from os import getenv
from collections import defaultdict


def pull_rbac():
    parser = argparse.ArgumentParser()
    parser.add_argument('apikey', default='')
    parser.add_argument('appkey', default='')
    args = parser.parse_args()

    permissions_api_endpoint = 'https://app.datadoghq.com/api/v2/permissions'
    roles_api_endpoint = 'https://app.datadoghq.com/api/v2/roles/templates'
    headers = {'DD-API-KEY': args.apikey, 'DD-APPLICATION-KEY': args.appkey}
    
    formatted_permissions_dict = {}
    permissions_json = None
    roles_json = None

    try:
        permissions_res = requests.get(permissions_api_endpoint, headers=headers)
        roles_res = requests.get(roles_api_endpoint, headers=headers)

        permissions_res.raise_for_status()

        permissions_json = permissions_res.json()
        roles_json = roles_res.json()
    except Exception as e:
        if getenv("CI_COMMIT_REF_NAME"):
            print('\x1b[31mERROR\x1b[0m: RBAC api request failed. Aborting')
            raise e
        else:
            print('\x1b[33mWARNING\x1b[0m: RBAC api request failed. Acceptable behavior locally when missing api/app keys')
            print(f'\x1b[33mWARNING\x1b[0m: RBAC api request failure reason: {e}')
            pass

    if permissions_json and roles_json:
        permissions_data = permissions_json.get('data', [])
        roles_data = roles_json.get('data', [])

        for permission in permissions_data:
            group_name = permission['attributes']['group_name']
            permission_name = permission['attributes']['name']
            permission_role_name = ''

            for role in roles_data:
                role_name = role['attributes']['name']
                role_permissions = role['relationships']['permissions']['data']
                # Ignore UI template roles
                if role_name != 'Datadog Billing Admin Role' and role_name != 'Datadog Security Admin Role':
                    # Compare role id to permission id
                    for role_permission in role_permissions:
                        if role_permission['id'] == permission['id']:
                            permission_role_name = role_name.replace('Read Only', 'Read-Only') # assigning permission_role_name relies on the order of admin, standard, and read-only role objects in the `roles/templates` api.
            # Ignore legacy logs permissions from dictionary before converting to JSON.  These legacy permissions are hard-coded in rbac-permissions-table partial until they can be deprecated.
            if permission_name in ('logs_live_tail', 'logs_read_index_data'):
                continue
            else:
                permission.setdefault('role_name', permission_role_name[0:-5]) # add role name without ' Role' to permission dictionary
                formatted_permissions_dict.setdefault(group_name, []).append(permission) # {group_name: permissions[]}

        formatted_permissions_json = json.dumps(formatted_permissions_dict)

        with open('data/permissions.json', 'w+') as outfile:
            outfile.write(formatted_permissions_json)


pull_rbac()
