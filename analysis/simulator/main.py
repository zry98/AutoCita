import requests
from flask import Flask, redirect, request
import random
import string

app = Flask(__name__)


@app.route('/')
def index():
    return redirect('/pagina/index/directorio/icpplus')


@app.route('/pagina/index/directorio/icpplus')
def portal():
    return app.send_static_file('portal.html')


@app.route('/icpplus/', methods=['POST'])
def icpplus():
    return app.send_static_file('icpplus.html')


@app.route('/icpplustieb/citar')
def citar():
    return app.send_static_file('citar.html')


@app.route('/icpplustieb/muestraMensajesTramite', methods=['POST'])
def muestraMensajesTramite():
    return app.send_static_file('muestraMensajesTramite.html')


@app.route('/icpplustieb/acInfo', methods=['POST'])
@app.route('/icpplustieb/acInfo<jsessionid>', methods=['POST'])
def acInfo(jsessionid=''):
    return app.send_static_file('acInfo.html')


@app.route('/icpplustieb/acEntrada', methods=['POST'])
def acEntrada():
    return app.send_static_file('acEntrada.html')


@app.route('/icpplustieb/acValidarEntrada', methods=['POST'])
def acValidarEntrada():
    return app.send_static_file('acValidarEntrada.html')


@app.route('/icpplustieb/acCitar', methods=['POST'])
def acCitar():
    return app.send_static_file('acCitar.html')


@app.route('/icpplustieb/acVerFormulario', methods=['GET', 'POST'])
def acVerFormulario():
    return app.send_static_file('acVerFormulario.html')


@app.route('/icpplustieb/acOfertarCita', methods=['POST'])
def acOfertarCita():
    return app.send_static_file('acOfertarCita.html')


@app.route('/icpplustieb/acVerificarCita', methods=['POST'])
def acVerificarCita():
    action = request.form.get('action')
    recaptcha_response = request.form.get('g-recaptcha-response')
    if not is_human(recaptcha_response, action):
        print('reCAPTCHA triggered', flush=True)
        return app.send_static_file('acVerificarCita.failed.html')
    print('reCAPTCHA passed', flush=True)
    sms_verification_code = ''.join(random.choice(string.digits) for _ in range(5))
    print(sms_verification_code, flush=True)
    return app.send_static_file('acVerificarCita.html')


@app.route('/icpplustieb/acGrabarCita', methods=['POST'])
def acGrabarCita():
    return app.send_static_file('acGrabarCita.html')


@app.route('/<path:path>')
def serve_static(path):
    return app.send_static_file(path)


def is_human(recaptcha_response: str, action: str) -> bool:
    recaptcha_secret_key = '6Lc3i_kcAAAAABx1xuczs-6kcEfLmhOtjwk7FRkf'
    payload = {'secret': recaptcha_secret_key, 'response': recaptcha_response, 'action': action}
    response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=payload).json()
    if response['success']:
        print(f"reCAPTCHA score: {response['score']}", flush=True)
    else:
        print(response, flush=True)
    return response['success'] and response['score'] > 0.8


if __name__ == '__main__':
    app.run()
