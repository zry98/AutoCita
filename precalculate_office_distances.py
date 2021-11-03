import json
import requests
from typing import List
from constants import office_codes
from config import *


def get_distances(google_maps_api_key: str, address: str, office_names: List[str]):
    distances = {}
    url = f'https://maps.googleapis.com/maps/api/distancematrix/json?key={google_maps_api_key}&language=en&region=es&origins={address}&destinations={"|".join(office_names)}'
    try:
        resp = requests.get(url).json()
    except Exception as e:
        raise Exception(f'Google DistanceMatrix API error: {e}')
    if resp['status'] != 'OK' or len(resp['rows']) == 0:
        raise Exception(f'Google DistanceMatrix API error: {resp["status"]}')
    for i, e in enumerate(resp['rows'][0]['elements']):
        if e['status'] != 'OK':
            raise Exception(f'No route to office {office_names[i]}')
        else:
            distances[office_names[i]] = e['distance']['value']
    return distances


def divide_offices(l, n: int = 25):
    for i in range(0, len(l), n):
        yield l[i:i + n]


google_maps_api_key = App().google_maps_api_key
address = Info().address
distances = {}
try:
    for offices in divide_offices(list(office_codes.keys())):
        distances |= get_distances(google_maps_api_key, address, offices)
except Exception as e:
    print(f'[ERROR] {e}')

with open(f'office_distances.json', 'w+') as f:
    f.write(json.dumps(distances))
