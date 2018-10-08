# gar9m Firmware
# Copyright (C) 2018 Ryan Finnie
# This is free software; for details, please see COPYING.

# This file is not meant to be uploaded to the gar9m during normal
# use.  It's executed after the gar9m.main() loop is broken, and is to
# aid in development.


def _recv(file=None, port=9999):
    import usocket as socket
    try:
        import network
        print('Station: {}'.format(network.WLAN(network.STA_IF).ifconfig()))
        print('AP: {}'.format(network.WLAN(network.AP_IF).ifconfig()))
    except:
        pass

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(socket.getaddrinfo('0.0.0.0', port)[0][-1])
    s.listen(1)
    print('Listening on port {}'.format(port))

    while True:
        (cl, addr) = s.accept()
        print('Accepted from {}'.format(addr))
        if file is None:
            header = cl.readline()
            if not header.startswith('RECV:'):
                print('file not provided on recv() call or as header')
                cl.close()
                continue
            fn = header.rstrip()[5:]
        else:
            fn = file
        print('New connection: {}'.format(addr))
        f = open(fn, 'w')
        written = 0
        while True:
            buf = cl.recv(1024)
            if not buf:
                break
            f.write(buf)
            written += len(buf)
        f.close()
        cl.close()
        print('{} bytes written to {}'.format(written, fn))
    s.close()


def recv(*args, **kwargs):
    reset = True
    if 'reset' in kwargs:
        reset = kwargs['reset']
        del(kwargs['reset'])

    try:
        _recv(*args, **kwargs)
    except KeyboardInterrupt:
        pass

    if reset:
        import machine
        machine.reset()
