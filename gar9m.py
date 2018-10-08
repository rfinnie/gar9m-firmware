# gar9m Firmware
# Copyright (C) 2018 Ryan Finnie
# This is free software; for details, please see COPYING.

# Note that this file exceeds ESP8266 memory limitations if shipped
# verbatim to and run from the device.  It must be compiled with
# mpy-cross and the .mpy must be shipped to the device.

import socket
import json
import time
import machine
import gc
import ubinascii
import os
import select

CONFIG = {
    'listen_addr': '0.0.0.0',
    'enable_http_server': True,
    'listen_port_http': 80,
    'auth_secret': None,
    'syslog_host': None,
    'syslog_id': 'gar9m',
    'button_pin': 5,
    'button_press_time': 0.25,
    'disable_pins': [4, 12, 13, 14],
}

BUTTON_PIN = None
SYSLOG_SOCKET = None


def debug(text):
    print(text)
    if SYSLOG_SOCKET and text:
        try:
            SYSLOG_SOCKET.sendto(
                '<135>{} gar9m: {}'.format(CONFIG['syslog_id'], text).encode('ASCII'),
                (CONFIG['syslog_host'], 514),
            )
        except OSError:
            pass


def parse_data(reqdata):
    return json.loads(reqdata)


def http_error(cl, code, desc):
    debug('ERROR: {} ({})'.format(desc, code))
    cl.write(b'HTTP/1.0 {} {}\r\n'.format(code, desc))
    if code == 401:
        cl.write(b'WWW-Authenticate: Basic realm="Login"\r\n')
    cl.write(b'\r\n{}\r\n'.format(desc))
    cl.close()


def process_connection(cl, addr):
    debug('New connection: {}'.format(addr))
    in_firstline = True
    in_dataarea = False
    httpmethod = None
    httpuri = None
    httpver = None
    httpauth = None
    reqdata = b''
    content_length = 0
    while True:
        if in_dataarea:
            while True:
                reqdata += cl.recv(1024)
                if len(reqdata) >= content_length:
                    break
            break
        line = cl.readline()
        if not line:
            break
        elif in_firstline:
            httpmethod, httpuri, httpver = line.split(b' ')
            in_firstline = False
        elif line.startswith(b'Content-Length: '):
            content_length = int(line[16:-2])
        elif line.startswith(b'Authorization: Basic '):
            httpauth = ubinascii.a2b_base64(line[21:-2]).split(b':', 1)[1].decode('ASCII')
        elif line == b'\r\n':
            if httpmethod in (b'POST', b'PUT'):
                in_dataarea = True
            else:
                break
    debug('IN: {} {} {} - {}'.format(httpmethod, httpuri, httpver, reqdata))

    if CONFIG['auth_secret']:
        if (httpauth is None) or (httpauth != CONFIG['auth_secret']):
            http_error(cl, 401, 'Unauthorized')
            return

    if httpuri == b'/command':
        if httpmethod != b'POST':
            http_error(cl, 400, 'Bad Request')
            return
    else:
        http_error(cl, 404, 'Not Found')
        return

    try:
        j = parse_data(reqdata)
    except:
        http_error(cl, 500, 'Internal Server Error')
        return

    uname = os.uname()
    response = json.dumps({
        'sysinfo': {
            'id': ubinascii.hexlify(machine.unique_id()).decode('ASCII'),
            'freq': str(machine.freq()),
            'release': uname.release,
            'version': uname.version,
            'machine': uname.machine,
        },
    }).encode('ASCII')
    debug('OUT: {}'.format(response))
    cl.write(b'HTTP/1.1 200 OK\r\n')
    cl.write(b'Content-Type: application/json; charset=utf-8\r\n')
    cl.write(b'Content-Length: ' + str(len(response)).encode('ASCII') + b'\r\n')
    cl.write(b'\r\n')
    cl.write(response)
    cl.close()
    if 'cmd' in j:
        if j['cmd'] == 'reset':
            time.sleep(1)
            machine.reset()
            time.sleep(60)
        elif j['cmd'] == 'button':
            debug('Pressing button')
            BUTTON_PIN.on()
            time.sleep(CONFIG['button_press_time'])
            BUTTON_PIN.off()


def main():
    global BUTTON_PIN
    global SYSLOG_SOCKET

    # Unused pins which do not have default pullups/pulldowns.
    # We want to pull these up.
    for pin in CONFIG['disable_pins']:
        machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP)

    BUTTON_PIN = machine.Pin(CONFIG['button_pin'], machine.Pin.OUT)

    if CONFIG['syslog_host']:
        SYSLOG_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    poll = select.poll()

    if CONFIG['enable_http_server']:
        http_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        http_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        http_addr = socket.getaddrinfo(CONFIG['listen_addr'], CONFIG['listen_port_http'])[0][-1]
        http_sock.bind(http_addr)
        http_sock.listen(1)
        debug('Listen (HTTP): {}'.format(http_addr))
        poll.register(http_sock, select.POLLIN)

    try:
        while True:
            debug('Memory free (before GC): {}'.format(gc.mem_free()))
            gc.collect()
            debug('Memory free (after GC):  {}'.format(gc.mem_free()))
            for i in poll.ipoll():
                try:
                    if CONFIG['enable_http_server'] and (i[0] == http_sock):
                        process_connection(*http_sock.accept())
                except Exception as e:
                    debug('Caught exception: {}'.format(e))
        debug('')
    except KeyboardInterrupt:
        if CONFIG['enable_http_server']:
            http_sock.close()
