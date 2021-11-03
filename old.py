import requests
import configparser
from typing import Set, Dict, Tuple, Union
from time import sleep
from datetime import datetime
from constants import *


class AutoCita:
    full_name: str
    # TODO: implement passport number and id type
    nie: str
    country: str
    email: str
    phone: str
    exp: str
    address: str
    tramite: str
    max_cita_date: datetime

    google_maps_api_key: str
    debug: bool

    r: requests.Session
    session_params: Dict[str, Union[str, Tuple[None, str]]]  # hidden UUIDs
    tried_offices: Set[str] = set()

    def __init__(self, info: InfoConfig, google_maps_api_key: str, debug: bool):
        self.full_name = info.full_name.strip().upper()
        self.nie = info.nie.strip().upper()
        if not nie_pattern.match(self.nie):
            # TODO: validate check digit
            raise ValueError('N.I.E. format error')
        self.country = info.country_code.strip()
        if not self.country.isnumeric() or int(self.country) not in countries.values():
            raise CountryNotFoundError
        self.email = info.email.strip()
        self.phone = info.phone.strip()
        if not self.phone.isnumeric():
            raise ValueError('Phone number format error')
        self.exp = info.current_expiry_date.strip()
        try:
            _ = datetime.strptime(self.exp, '%d/%m/%Y')
        except ValueError:
            raise ValueError('Current card expiry date format error')
        self.address = info.address.strip()
        self.tramite = info.tramite_code.strip()
        if not self.tramite.isnumeric() or int(self.tramite) not in tramites.values():
            raise TramiteNotFoundError
        try:
            self.max_cita_date = datetime.strptime(info.max_cita_date.strip(), '%d/%m/%Y')
        except ValueError:
            raise ValueError('Max cita date format error')

        self.google_maps_api_key = google_maps_api_key
        self.debug = debug

    def work(self) -> bool:
        while True:
            try:
                self.init_session()
                self.citar()
                self.acInfo()
                self.acEntrada()
                self.acValidarEntrada()
                nearest_office_id = self.acCitar()
                self.acVerFormulario(nearest_office_id)
                cita_id = self.acOfertarCita()
                self.acVerificarCita(cita_id)  # FIXME: solve reCAPTCHA
                sms_verification_code = input('SMS verification code: ').strip()
                cita_code = self.acGrabarCita(sms_verification_code)
                print(f'[SUCCEEDED] Número de justificante de cita: {cita_code}')
                return True
            except FailedAttemptAtOffice as e:
                print(f'[FAILED] {e}')
                continue
            except FailedAttempt as e:
                print(f'[FAILED] {e}')
                return False
        return False

    def init_session(self):
        self.r = requests.Session()
        self.r.headers.update(browser_headers)
        # for debugging with fiddler
        if self.debug:
            self.r.proxies.update({'http': 'http://127.0.0.1:10086', 'https': 'http://127.0.0.1:10086'})
            self.r.verify = r'FiddlerRoot.pem'

    def citar(self):
        url = f'{base_url}/icpplustieb/citar?p=8&locale=es'
        resp = self.r.get(url)
        if error_503_message in resp.text:
            raise FailedAttempt('Server 503 error')
        self.update_session_params(resp.text)
        self.r.headers.update({'Referer': url, 'Origin': base_url, 'Cache-Control': 'max-age=0'})

    def acInfo(self):
        url = f'{base_url}/icpplustieb/acInfo'
        resp = self.r.post(url, data=self.session_params | {'sede': '99',  # TODO: implement specify office
                                                            'tramiteGrupo[0]': self.tramite})
        self.update_session_params(resp.text)
        self.r.headers.update({'Referer': url})

    def acEntrada(self):
        url = f'{base_url}/icpplustieb/acEntrada'
        resp = self.r.post(url, data=self.session_params)
        self.update_session_params(resp.text)
        self.r.headers.update({'Referer': url})

    def acValidarEntrada(self):
        url = f'{base_url}/icpplustieb/acValidarEntrada'
        for k, v in self.session_params.items():  # convert to multipart/form-data
            self.session_params[k] = (None, v)
        resp = self.r.post(url, files=self.session_params | {'rdbTipoDoc': (None, 'N.I.E.'),
                                                             'txtIdCitado': (None, self.nie),
                                                             'txtDesCitado': (None, self.full_name),
                                                             'txtPaisNac': (None, self.country),
                                                             'txtFecha': (None, self.exp)})
        self.update_session_params(resp.text)
        self.r.headers.update({'Referer': url})

    def acCitar(self) -> str:
        url = f'{base_url}/icpplustieb/acCitar'
        resp = self.r.post(url, data=self.session_params)
        if no_cita_message in resp.text:
            self.tried_offices.clear()
            raise FailedAttempt('No any cita available')

        nearest_office_id = self.get_nearest_office_id(resp.text)
        if nearest_office_id == '':
            self.tried_offices.clear()
            raise FailedAttempt('Can\'t find a nearest office, may be no any cita available')

        self.update_session_params(resp.text)
        self.r.headers.update({'Referer': url})
        return nearest_office_id

    def acVerFormulario(self, nearest_office_id: str):
        url = f'{base_url}/icpplustieb/acVerFormulario'
        resp = self.r.post(url, data=self.session_params | {'idSede': nearest_office_id})
        if self.debug:
            print(f'Tried offices: {list(self.tried_offices)}')
        self.tried_offices.add(nearest_office_id)
        self.update_session_params(resp.text)
        self.r.headers.update({'Referer': url})

    def acOfertarCita(self) -> str:
        url = f'{base_url}/icpplustieb/acOfertarCita'
        resp = self.r.post(url, data=self.session_params | {'txtMailCitado': self.email,
                                                            'emailDOS': self.email,
                                                            'txtTelefonoCitado': self.phone})
        if no_cita_message in resp.text:
            raise FailedAttemptAtOffice('No cita available in this office')

        cita_id = self.choose_cita_id(resp.text)
        if cita_id == '':
            raise FailedAttemptAtOffice('No cita available before MaxCitaDate')

        self.update_session_params(resp.text)
        self.r.headers.update({'Referer': url})
        return cita_id

    def acVerificarCita(self, cita_id: str):
        url = f'{base_url}/icpplustieb/acVerificarCita'
        resp = self.r.post(url, data=self.session_params | {'rdbCita': cita_id})
        if 'Captcha' in resp.text:
            raise FailedAttempt('Failed to pass reCAPTCHA')
        self.update_session_params(resp.text)
        self.r.headers.update({'Referer': url})

    def acVerificarCita_w_reCAPTCHA(self, cita_id: str, reCAPTCHA_site_key: str, reCAPTCHA_response: str):
        url = f'{base_url}/icpplustieb/acVerificarCita'
        resp = self.r.post(url, data=self.session_params | {'rdbCita': cita_id,
                                                            'reCAPTCHA_site_key': reCAPTCHA_site_key,
                                                            'action': 'acOfertarCita',
                                                            'g-recaptcha-response': reCAPTCHA_response})
        if 'Captcha' in resp.text:
            raise FailedAttempt('Failed to pass reCAPTCHA')
        self.update_session_params(resp.text)
        self.r.headers.update({'Referer': url})

    def acGrabarCita(self, sms_verification_code: str) -> str:
        url = f'{base_url}/icpplustieb/acGrabarCita'
        if len(sms_verification_code) != 5 or not sms_verification_code.isnumeric():
            raise ValueError('SMS verification code format error')
        resp = self.r.post(url, data=self.session_params | {'txtCodigoVerificacion': sms_verification_code,
                                                            'chkTotal': '1', 'enviarCorreo': 'on'})
        try:
            cita_code = cita_code_pattern.findall(resp.text)[0]
        except IndexError:
            raise Exception('Can\'t extract cita code')
        return cita_code

    def update_session_params(self, html: str):
        try:
            hidden_params = hidden_params_pattern.findall(html)[0]
        except IndexError:
            print(html)
            raise Exception('Can\'t extract hidden parameters')
        self.session_params = {hidden_params[0]: hidden_params[1], hidden_params[2]: hidden_params[3]}

    def get_nearest_office_id(self, html: str) -> str:
        offices = offices_pattern.findall(html)
        if len(offices) == 0:
            if '<option' in html:
                print(html)
                print('------[UNKNOWN ERROR]-----')
                exit(0)
            raise Exception('Can\'t extract offices')
        offices = dict([(v[1], v[0]) for v in offices])  # swap name and id
        if self.debug:  # record new offices
            with open(r'offices.log', 'a+') as f:
                for name, id in offices.items():
                    if str(id) not in office_codes.values():
                        f.write(name + '\n')
        distances = {}
        for name, id in list(offices.items()):
            if id in self.tried_offices:
                offices.pop(name)
        office_names = list(offices.keys())
        if len(office_names) == 0:
            return ''

        # get distances through Google Maps DistanceMatrix API
        url = f'https://maps.googleapis.com/maps/api/distancematrix/json?key={self.google_maps_api_key}&language=en&region=es&origins={self.address}&destinations={"|".join(office_names)}'
        try:
            resp = requests.get(url).json()
        except Exception as e:
            raise Exception(f'Google DistanceMatrix API error: {e}')
        if resp['status'] != 'OK' or len(resp['rows']) == 0:
            raise Exception(f'Google DistanceMatrix API error: {resp["status"]}')
        for i, e in enumerate(resp['rows'][0]['elements']):
            if e['status'] != 'OK':
                print(f'No route to office {office_names[i]}')
            else:
                distances[office_names[i]] = e['distance']['value']

        nearest_office = min(distances, key=distances.get)
        if self.debug:
            print(f'[INFO] Nearest office: {nearest_office} ({offices[nearest_office]})')
        return offices[nearest_office]

    def choose_cita_id(self, html: str) -> str:
        citas = cita_pattern.findall(html)
        if len(citas) == 0:
            print(html)
            raise Exception('Can\'t extract citas')
        for cita in citas:
            cita_date = datetime.strptime(cita[1], '%d/%m/%Y')
            if cita_date > self.max_cita_date:
                continue
            # TODO: implement time range option
            return cita[0]
        return ''


def main(info: InfoConfig, sleep_minutes: int, google_maps_api_key: str, debug: bool):
    try:
        c = AutoCita(info, google_maps_api_key, debug)
        while True:
            if c.work():
                return
            sleep(sleep_minutes * 60)
    except ValueError as e:
        print(f'[ERROR] {e}')
    except CountryNotFoundError:
        print('[ERROR] Country not found, available country codes:\n' + '\n'.join(
            [f'{k}: {v}' for k, v in countries.items()]))
    except TramiteNotFoundError:
        print('[ERROR] Tramite not found, available tramite codes:\n' + '\n'.join(
            [f'{k}: {v}' for k, v in tramites.items()]))
    except Exception as e:
        print(f'[ERROR] {e}')


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(r'config.ini')
    debug = True if config['APP']['Debug'].lower() == 'true' else False
    info = InfoConfig(
        full_name=config['INFO']['FullName'],
        nie=config['INFO']['NIE'],
        country=config['INFO']['CountryCode'],
        email=config['INFO']['Email'],
        phone=config['INFO']['Phone'],
        current_expiry_date=config['INFO']['CurrentExpiryDate'],
        address=config['INFO']['Address'],
        tramite=config['INFO']['TramiteCode'],
        max_cita_date=config['INFO']['MaxCitaDate']
    )

    main(info=info,
         sleep_minutes=int(config['APP']['SleepMinutes']),
         google_maps_api_key=config['APP']['GoogleMapsAPIKey'],
         debug=debug)
