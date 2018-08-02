#!/usr/bin/python
#
# fcgi-pm.py
# By houspi@gmail.com
#
# Python daemon
# prefork TCP server 
# This is the base script
# It doesn't provide any error and exception check
#  Read data from client until get double \r\n (empty line)
#  Run external program
#  Send output to client
#
# usage: fcgi-pm.py [-h] [--socket SOCKET] [--queue-size QUEUE_SIZE]
#                  [--count COUNT] [--daemon DAEMON] --cgi CGI
#
# optional arguments:
#  -h, --help                show this help message and exit
#  --socket SOCKET           host:port
#  --queue-size QUEUE_SIZE   Max requests per child
#  --count COUNT             Num of workers
#  --cgi CGI                 Path to exucatable cgi with parameters
#  --daemon DAEMON           Run as a daemon. Yes/No
#

import os
import sys
import subprocess
import socket
import select
import signal
import resource
import logging
import argparse

PID_FILE    = '/var/run/fcgi-pm.pid'
RUNNING_DIR = '/tmp'
DEFAULT_HOST       = 'localhost'
DEFAULT_PORT       = 8888
DEFAULT_QUEUE_SIZE = 100
DEFAULT_COUNT      = 2
DEFAULT_BACKLOG    = 2
BUFFER_SIZE        = 1024

childs_list = {}

# Child info class
class ChildController:
    def __init__(self, pipe, pid, queue_size):
        self.is_free = True
        self.pipe = pipe
        self.pid = pid
        self.queue_size = queue_size
        self.counter = 0


# Connection handler
# sock - Socket
# cgi_script - external script name
def handle_connection(sock, cgi_script):
    logger.info('Start to process request')
    
    # Read data from socket until double \r\n
    get_data = ''
    while not get_data.endswith('\r\n\r\n'):
        get_data += sock.recv(BUFFER_SIZE)
    
    # Start external program
    proc = subprocess.Popen(cgi_script, shell=True, stdout=subprocess.PIPE)
    (stdout_data, stderr_data) = proc.communicate()
    
    # We mean that the program always runs successfully
    status = "200 OK"
    content_type = "text/plain"
    send_data = '';
    send_data += 'HTTP/1.1 ' + status + '\r\n'
    send_data += 'Server: localhost\r\n'
    send_data += 'Connection: close\r\n'
    send_data += 'Content-Type: ' + content_type + '\r\n'
    send_data += 'Content-Length: ' + str(len(stdout_data)) + '\r\n'
    send_data += '\r\n'
    send_data += stdout_data
    logger.info('Child %d sending data' % (os.getpid()))
    sock.sendall(send_data)


# Start child process
# sock - Socket
# queue_size - max requests per child
# cgi_script - external script name
def start_child(sock, queue_size, cgi_script):
    child_pipe, parent_pipe = socket.socketpair()
    pid = os.fork()
    # child process
    if pid == 0:
        child_pipe.close()
        while 1:
            # read data from parent
            command = parent_pipe.recv(BUFFER_SIZE)
            connection, (client_ip, clinet_port) = sock.accept()
            logger.info('Child %d Accept connection %s:%d' % (os.getpid(), client_ip, clinet_port))
            
            # send answer to parent
            # run external program
            parent_pipe.send('accept')
            handle_connection(connection, cgi_script)
            connection.close()
            logger.info('Child %d finished' % (os.getpid()))
            parent_pipe.send('finished')
    logger.info('Starting child with PID: %s' % pid)
    childs_list[pid] = ChildController(child_pipe, pid, queue_size)
    parent_pipe.close()
    return child_pipe


# Main server loop
# server_host - server host
# server_port - port 
# queue_size  - max requests per child
# workers_count - num of workers
# cgi_script - external script name
def server_loop(server_host, server_port, queue_size, workers_count, cgi_script):
    # Create new socket 
    # bind them and listen
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((server_host, server_port))
    sock.listen(DEFAULT_BACKLOG)
    logger.info('Listning on %s:%d...' % (server_host, server_port))
    
    # start workers
    for i in range(workers_count):
        start_child(sock, queue_size, cgi_script)
    
    # main infinite loop
    to_read = [sock] + [child.pipe.fileno() for child in childs_list.values()]
    while 1:
        # Test if socket is readable
        readables, writables, exceptions = select.select(to_read, [], [])
        if sock in readables:
            # Find free child
            for child in childs_list.values():
                if child.is_free:
                    logger.info('Pass connection to child PID: %d' % (child.pid) )
                    child.counter += 1
                    logger.info('Child %d counter: %d' % (child.pid, child.counter))
                    # Some communication between parent & child
                    child.pipe.send('new connecton')
                    answer = child.pipe.recv(BUFFER_SIZE)
                    child.is_free = False
                    break
                else:
                    # No free child
                    pass
                    
            else:
                # No more childs
                pass

        # Test is there any free child
        for child in childs_list.values():
            if child.pipe.fileno() in readables:
                answer = child.pipe.recv(BUFFER_SIZE)
                child.is_free = True
                # Restart child if queue_size is reached 
                if child.counter == child.queue_size:
                    logger.info('Child %d counter reach max %d, Kill him and start new one' % (child.pid, child.counter))
                    os.kill(child.pid, signal.SIGTERM)
                    del childs_list[child.pid]
                    start_child(sock, queue_size, cgi_script)
                    to_read = [sock] + [child.pipe.fileno() for child in childs_list.values()]


# Do some init and call main loop
def main(server_host, server_port, queue_size, workers_count, cgi_script):
    logger.setLevel(logging.INFO)
    log = logging.StreamHandler()
    log.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S')
    log.setFormatter(formatter)
    logger.addHandler(log)
    logger.info('Start')
    server_loop(server_host, int(server_port), queue_size, workers_count, cgi_script)


# Run script as a daemon
def daemonize():
    if(os.getppid() == 1):
        return
    try:
        pid = os.fork()
    except OSError, e:
        raise Exception,"Exception occured %s [%d]"%(e.strerror,e.errno)
        os._exit(0)

    if pid == 0:
        os.setsid()

        try:
            pid = os.fork()
        except OSError, e:
            raise Exception,"Exception occured %s [%d]"%(e.strerror,e.errno)
            os._exit(0)
        if pid == 0:
            os.chdir(RUNNING_DIR)
            os.umask(027)
        else:
            os._exit(0)
    else:
        os.wait()
        os._exit(0) # Parent of First Child exits

    # STDIN STDOUT STDERR to /dev/null
    fd = os.open(os.devnull,os.O_RDWR)
    os.dup(fd) # STDOUT
    os.dup(fd) # STDERR
#    signal.signal(signal.SIGHUP, signal.SIG_IGN)
#    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', default = DEFAULT_HOST + ':' + str(DEFAULT_PORT), help='host:port')
    parser.add_argument('--queue-size', type=int, default=DEFAULT_QUEUE_SIZE, help='Max requests  per child')
    parser.add_argument('--count', type=int,default=DEFAULT_COUNT, help='Num of workers')
    parser.add_argument('--daemon', default = "No", help='Run as a daemon. Yes/no')
    parser.add_argument('--cgi', required=True, help='Path to exucatable cgi with parameters')
    args = parser.parse_args()

    (server_host, server_port) = args.socket.split(':')

    logger = logging.getLogger('main')

    if args.daemon == "Yes":
        daemonize()

    main(server_host, server_port, args.queue_size, args.count, args.cgi)
