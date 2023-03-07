""" Copyright start
  Copyright (C) 2008 - 2023 Fortinet Inc.
  All rights reserved.
  FORTINET CONFIDENTIAL & FORTINET PROPRIETARY SOURCE CODE
  Copyright end """


import requests
import json
from datetime import datetime
from connectors.core.connector import get_logger, ConnectorError
from .hubspot_api_auth import HubSpotAuth

logger = get_logger('hubspot')


class HubSpot(object):
    def __init__(self, config):
        self.server_url = config.get('resource', '').strip('/')
        if not self.server_url.startswith('https://') and not self.server_url.startswith('http://'):
            self.server_url = 'https://' + self.server_url
        self.verify_ssl = config.get('verify_ssl')
        self.hs_auth = HubSpotAuth(config)
        self.connector_info = config.pop('connector_info', '')
        self.token = self.hs_auth.validate_token(config, self.connector_info)

    def make_rest_call(self, endpoint=None, params=None, json_body=None, payload=None, method='GET'):
        headers = {'Authorization': self.token, 'Content-Type': 'application/json'}
        if endpoint is None:
            service_url = f'{self.server_url}/crm-objects/v1/objects/tickets'
        elif endpoint == 'crm-objects/v1/change-log/tickets':
            service_url = f'{self.server_url}/{endpoint}'
        else:
            service_url = f'{self.server_url}/crm-objects/v1/objects/tickets/{endpoint}'
        logger.debug('Request URL {0}'.format(endpoint))
        try:
            response = requests.request(method, service_url, data=payload, headers=headers, json=json_body,
                                        params=params, verify=self.verify_ssl)
            if response.ok:
                if response.status_code == 204:
                    return response
                content_type = response.headers.get('Content-Type')
                if response.text != "" and 'application/json' in content_type:
                    return response.json()
                else:
                    return response.content
            elif response.status_code == 404:
                return {"message": "Not Found"}
            else:
                if response.text != "":
                    err_resp = response.json()
                    if "message" in err_resp:
                        error_msg = err_resp.get('message')
                        raise ConnectorError(error_msg)
                else:
                    error_msg = '{0}: {1}'.format(response.status_code, response.reason)
                    raise ConnectorError(error_msg)
        except requests.exceptions.SSLError:
            logger.error('An SSL error occurred')
            raise ConnectorError('An SSL error occurred')
        except requests.exceptions.ConnectionError:
            logger.error('A connection error occurred')
            raise ConnectorError('A connection error occurred')
        except requests.exceptions.Timeout:
            logger.error('The request timed out')
            raise ConnectorError('The request timed out')
        except requests.exceptions.RequestException:
            logger.error('There was an error while handling the request')
            raise ConnectorError('There was an error while handling the request')
        except Exception as e:
            logger.error('{0}'.format(e))
            raise ConnectorError('{0}'.format(e))


def build_params(params):
    return {k: v for k, v in params.items() if v is not None and v != ''}


def convert_timestamp(ts):
    epoch = datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S.%fZ').timestamp() * 1000
    return int(epoch)


def create_payload(params):
    payload = []
    for k, v in params.items():
        payload.append({
            "name": k,
            "value": v
        })
    return payload


def build_properties(properties, name):
    props_list = list(filter(None, [props.strip(" ") for props in properties.split(',')]))
    properties = f'{name}=' + f'&{name}='.join(props_list)
    return properties


def build_query_str(params):
    query_str = ''
    properties = params.get('properties')
    if properties and ',' in properties:
        query_str = '?' + build_properties(properties, "properties")
        params.pop('properties')
    properties = params.get('propertiesWithHistory')
    if properties and ',' in properties:
        if query_str == '':
            query_str = '?' + build_properties(properties, "propertiesWithHistory")
        else:
            query_str += '&' + build_properties(properties, "propertiesWithHistory")
        params.pop('propertiesWithHistory')
    return query_str


def check_tkt_properties(ticket_properties):
    properties = []
    if isinstance(ticket_properties, list):
        for item in ticket_properties:
            if item.get('value') != "":
                properties.append(item)
    return properties


def get_all_tickets(config, params):
    hs = HubSpot(config)
    query_str = build_query_str(params)
    params = build_params(params)
    endpoint = f'paged{query_str}'
    response = hs.make_rest_call(endpoint=endpoint, params=params)
    return response


def get_tickets_by_id(config, params):
    hs = HubSpot(config)
    query_str = build_query_str(params)
    params = build_params(params)
    ticket_ids = params.pop('ticket_ids')
    if isinstance(ticket_ids, list):
        payload = {"ids": ticket_ids}
        endpoint = f'batch-read{query_str}'
        response = hs.make_rest_call(endpoint=endpoint, payload=json.dumps(payload), params=params, method='POST')
    else:
        endpoint = f'{ticket_ids}{query_str}'
        response = hs.make_rest_call(endpoint=endpoint, params=params)
    return response


def create_tickets(config, params):
    hs = HubSpot(config)
    if params.pop('create') == 'Single Ticket':
        payload = []
        params = build_params(params)
        if params.get('ticket_properties'):
            payload = check_tkt_properties(params.pop('ticket_properties'))
        if params.get('createdate'):
            params['createdate'] = convert_timestamp(params.get('createdate'))
        payload.extend(create_payload(params))
        response = hs.make_rest_call(payload=json.dumps(payload), method='POST')
    else:
        payload = params.get('ticket_properties')
        response = hs.make_rest_call(endpoint='batch-create', payload=json.dumps(payload), method='POST')
    return response


def update_tickets(config, params):
    hs = HubSpot(config)
    payload = params.get('ticket_properties')
    response = hs.make_rest_call(endpoint='batch-update', payload=json.dumps(payload), method='POST')
    return response


def delete_tickets(config, params):
    hs = HubSpot(config)
    ticket_ids = params.get('ticket_ids')
    if isinstance(ticket_ids, list):
        payload = {"ids": ticket_ids}
        response = hs.make_rest_call(endpoint='batch-delete', payload=json.dumps(payload), method='POST')
    else:
        response = hs.make_rest_call(endpoint=ticket_ids, method='DELETE')
    if response:
        return {"status": "successful", "message": "Deleted Successfully"}


def get_tickets_changes_log(config, params):
    hs = HubSpot(config)
    response = hs.make_rest_call(endpoint='crm-objects/v1/change-log/tickets', params=params)
    return response


operations = {
    'get_all_tickets': get_all_tickets,
    'get_tickets_by_id': get_tickets_by_id,
    'create_tickets': create_tickets,
    'update_tickets': update_tickets,
    'delete_tickets': delete_tickets,
    'get_tickets_changes_log': get_tickets_changes_log
}
