import json
import requests
from typing import Set, Dict
from time import sleep
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.common.exceptions import TimeoutException
from constants import *
from config import App, Info


class AutoCita:
    full_name: str
    # TODO: implement passport number and id type
    nie: str
    country_code: str
    email: str
    phone: str
    exp: str
    address: str
    office_distances: Dict[str, int]
    tramite_code: str
    max_cita_date: datetime

    sleep_minutes: int
    google_maps_api_key: str
    debug: bool

    browser: webdriver.Chrome
    tried_offices: Set[str] = set()

    def __init__(self, app: App, info: Info):
        self.full_name = info.full_name.strip().upper()
        self.nie = info.nie.strip().upper()
        if not nie_pattern.match(self.nie):
            # TODO: validate check digit
            raise ValueError('N.I.E. format error')
        self.country_code = str(info.country_code)
        if not self.country_code.isnumeric() or info.country_code not in countries.values():
            raise CountryNotFoundError
        self.email = info.email.strip().lower()
        self.phone = info.phone.strip()
        if not self.phone.isnumeric():
            raise ValueError('Phone number format error')
        self.exp = info.current_expiry_date.strip()
        try:
            _ = datetime.strptime(self.exp, '%d/%m/%Y')
        except ValueError:
            raise ValueError('Current card expiry date format error')
        self.address = info.address.strip()
        self.office_distances = info.offices_distances
        self.tramite_code = str(info.tramite_code)
        if not self.tramite_code.isnumeric() or info.tramite_code not in tramites.values():
            raise TramiteNotFoundError
        try:
            self.max_cita_date = datetime.strptime(info.max_cita_date.strip(), '%d/%m/%Y')
        except ValueError:
            raise ValueError('Max cita date format error')

        self.sleep_minutes = app.sleep_minutes
        self.google_maps_api_key = app.google_maps_api_key
        self.debug = app.debug

        self.init_browser(app.chrome_profile_path)

    def init_browser(self, chrome_profile_path: str):
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins-discovery')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-translate')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-gpu')
        options.add_argument('--lang=en')
        # options.add_argument('--no-sandbox')
        options.add_argument('--window-size=1280,800')
        options.add_argument('--no-first-run')
        options.add_argument('--no-service-autorun')
        options.add_argument('--password-store=basic')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(f"--user-data-dir={chrome_profile_path}")
        options.add_experimental_option('prefs', {'intl.accept_languages': 'en_US,es_ES,ca'})
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        if self.debug:
            options.add_experimental_option('detach', True)
            # options.add_argument('--proxy-server=http://127.0.0.1:10086')
        else:
            options.add_argument('--headless')
        self.browser = webdriver.Chrome(options=options)

    def work(self):
        while True:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Start working")
            try:
                self.citar()
                self.acInfo()
                self.acEntrada()
                self.acValidarEntrada()
                self.acCitar()
                self.acVerFormulario()
                self.acOfertarCita()
                self.acVerificarCita()
                cita_code = self.acGrabarCita()
                print(f'[SUCCEEDED] Cita number: {cita_code}')
                return True
            except FailedAttemptAtOffice as e:
                print(f'[FAILED] {e}')
                continue
            except FailedAttempt as e:
                print(f'[FAILED] {e}')
                sleep(self.sleep_minutes * 60)
            except Exception as e:
                raise e
            finally:
                if self.debug and len(self.tried_offices) != 0:
                    print(f'Tried offices: {list(self.tried_offices)}')

    def citar(self):
        self.browser.get(f'{base_url}/icpplustieb/citar?p=8&locale=es')
        self.browser.delete_all_cookies()
        self.browser.refresh()

        if error_503_message in self.browser.page_source:
            raise FailedAttempt('Server 503 error')

        # accept cookies
        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, 'cookie_action_close_header'))
        ).click()

        # select tramite
        Select(WebDriverWait(self.browser, 30).until(
            EC.presence_of_element_located((By.ID, 'tramiteGrupo[0]'))
        )).select_by_value(self.tramite_code)

        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, 'btnAceptar'))
        ).click()

    def acInfo(self):
        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, 'btnEntrar'))
        ).click()

    def acEntrada(self):
        WebDriverWait(self.browser, 30).until(
            EC.presence_of_element_located((By.ID, 'txtIdCitado'))
        )
        # fill-in the form and submit with JS, because had trouble filling a date into txtFecha (dropping "/")
        self.browser.execute_script(f"document.getElementById('txtIdCitado').value='{self.nie}';"
                                    f"document.getElementById('txtDesCitado').value='{self.full_name}';"
                                    f"document.getElementById('txtPaisNac').value='{self.country_code}';"
                                    f"document.getElementById('txtFecha').value='{self.exp}';"
                                    f"envia();")

        # WebDriverWait(self.browser, 30).until(
        #     EC.presence_of_element_located((By.ID, 'txtIdCitado'))
        # ).send_keys(self.nie)
        # WebDriverWait(self.browser, 30).until(
        #     EC.presence_of_element_located((By.ID, 'txtDesCitado'))
        # ).send_keys(self.full_name)
        # Select(WebDriverWait(self.browser, 30).until(
        #     EC.presence_of_element_located((By.ID, 'txtPaisNac'))
        # )).select_by_value(self.country)
        # WebDriverWait(self.browser, 30).until(
        #     EC.presence_of_element_located((By.ID, 'txtFecha'))
        # ).send_keys(self.exp)
        #
        # WebDriverWait(self.browser, 30).until(
        #     EC.element_to_be_clickable((By.ID, 'btnEnviar'))
        # ).click()

    def acValidarEntrada(self):
        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, 'btnEnviar'))
        ).click()

    def acCitar(self):
        if no_cita_message in self.browser.page_source:
            self.tried_offices.clear()
            raise FailedAttempt('No available cita')

        nearest_office_id = self.get_nearest_office_id(self.browser.page_source)
        if nearest_office_id == '':
            self.tried_offices.clear()
            raise FailedAttempt('No available cita')

        self.tried_offices.add(nearest_office_id)

        # select office
        Select(WebDriverWait(self.browser, 30).until(
            EC.presence_of_element_located((By.ID, 'idSede'))
        )).select_by_value(nearest_office_id)

        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, 'btnSiguiente'))
        ).click()

    def acVerFormulario(self):
        WebDriverWait(self.browser, 30).until(
            EC.presence_of_element_located((By.ID, 'txtTelefonoCitado'))
        )
        self.browser.execute_script(f"document.getElementById('txtTelefonoCitado').value='{self.phone}';"
                                    f"document.getElementById('emailUNO').value='{self.email}';"
                                    f"document.getElementById('emailDOS').value='{self.email}';"
                                    f"enviar();")

        # WebDriverWait(self.browser, 30).until(
        #     EC.presence_of_element_located((By.ID, 'txtTelefonoCitado'))
        # ).send_keys(self.phone)
        # WebDriverWait(self.browser, 30).until(
        #     EC.presence_of_element_located((By.ID, 'emailUNO'))
        # ).send_keys(self.email)
        # WebDriverWait(self.browser, 30).until(
        #     EC.presence_of_element_located((By.ID, 'emailDOS'))
        # ).send_keys(self.email)
        #
        # WebDriverWait(self.browser, 30).until(
        #     EC.element_to_be_clickable((By.ID, 'btnSiguiente'))
        # ).click()

    def acOfertarCita(self):
        if no_cita_message in self.browser.page_source:
            raise FailedAttemptAtOffice('No available cita in this office')

        cita_id = self.choose_cita_id(self.browser.page_source)
        if cita_id == '':
            raise FailedAttemptAtOffice('No available cita in this office before max cita date')
        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, f'cita{cita_id}'))
        ).click()

        # try:
        #     # reCAPTCHA_site_key = reCAPTCHA_site_key_pattern.findall(self.r.page_source)[0]
        #     reCAPTCHA_site_key = WebDriverWait(self.browser, 30).until(
        #         EC.presence_of_element_located((By.ID, 'reCAPTCHA_site_key'))
        #     ).get_attribute('value')
        #     print(f'reCAPTCHA site key: {reCAPTCHA_site_key}')
        # # except IndexError:
        # except TimeoutException:
        #     raise Exception('Can\'t extract reCAPTCHA site key')

        try:
            WebDriverWait(self.browser, 30).until(
                lambda driver: driver.find_element(By.ID, 'g-recaptcha-response').get_attribute('value') != ''
            )
            # reCAPTCHA_response = self.browser.find_element(By.ID, 'g-recaptcha-response').get_attribute('value')
            # print(f'reCAPTCHA response: {reCAPTCHA_response}')
        except TimeoutException:
            raise Exception('Can\'t get reCAPTCHA response')

        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, 'btnSiguiente'))
        ).click()

        WebDriverWait(self.browser, 30).until(
            EC.alert_is_present()
        )
        self.browser.switch_to.alert.accept()

    def acVerificarCita(self):
        if 'Captcha' in self.browser.page_source:
            raise FailedAttempt('Failed to pass reCAPTCHA')

        if 'txtCodigoVerificacion' in self.browser.page_source:  # SMS verification needed
            sms_verification_code_txt = WebDriverWait(self.browser, 30).until(
                EC.presence_of_element_located((By.ID, 'txtCodigoVerificacion'))
            )
            sms_verification_code = input('SMS verification code: ').strip()
            if len(sms_verification_code) != 5 or not sms_verification_code.isnumeric():
                raise ValueError('SMS verification code format error')
            sms_verification_code_txt.send_keys(sms_verification_code)

        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, 'chkTotal'))
        ).click()

        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, 'enviarCorreo'))
        ).click()

        WebDriverWait(self.browser, 30).until(
            EC.element_to_be_clickable((By.ID, 'btnConfirmar'))
        ).click()

    def acGrabarCita(self) -> str:
        return WebDriverWait(self.browser, 30).until(
            EC.presence_of_element_located((By.ID, 'justificanteFinal'))
        ).text

    def get_nearest_office_id(self, html: str) -> str:
        offices = offices_pattern.findall(html)
        if len(offices) == 0:
            if '<option' in html:
                print(html)
                print('------[UNKNOWN ERROR]-----')
                exit(0)
            raise Exception('Can\'t extract offices')
        offices = dict([(v[1], v[0]) for v in offices])  # swap to name-id pairs
        if self.debug:
            # dump new offices
            with open(r'offices.log', 'a+') as f:
                for name, id in offices.items():
                    if int(id) not in office_codes.values():
                        print(f'[INFO] Found new office: {name} (id={id})')
                        f.write(f'{name} - {id}\n')
        distances = {}
        offices_to_check = []
        for name, id in list(offices.items()):
            if id in self.tried_offices:
                offices.pop(name)
            else:
                try:
                    distances[name] = self.office_distances[name]
                except KeyError:
                    offices_to_check.append(name)
        if len(distances) == 0 and len(offices_to_check) == 0:
            return ''

        if len(offices_to_check) != 0:
            # get distances through Google Maps DistanceMatrix API
            url = f'https://maps.googleapis.com/maps/api/distancematrix/json?key={self.google_maps_api_key}&language=en&region=es&origins={self.address}&destinations={"|".join(offices_to_check)}'
            try:
                resp = requests.get(url).json()
            except Exception as e:
                raise Exception(f'Google DistanceMatrix API error: {e}')
            if resp['status'] != 'OK' or len(resp['rows']) == 0:
                raise Exception(f'Google DistanceMatrix API error: {resp["status"]}')
            for i, e in enumerate(resp['rows'][0]['elements']):
                if e['status'] != 'OK':
                    print(f'No route to office {offices_to_check[i]}')
                else:
                    distances[offices_to_check[i]] = e['distance']['value']

        nearest_office = min(distances, key=distances.get)
        if self.debug:
            print(f'[INFO] Nearest office: {nearest_office} (id={offices[nearest_office]})')
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


def main(app: App, info: Info):
    try:
        with open('office_distances.json', 'r') as f:
            office_distances = json.loads(f.read())
    except FileNotFoundError:
        office_distances = {}
    if len(office_distances) == 0:
        print('[ERROR] No pre-calculated office distances found')
        return
    else:
        info.offices_distances = office_distances

    try:
        AutoCita(app, info).work()
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
    app = App()
    info = Info()

    main(app, info)
