# PythonDaemon

Python prefork TCP server 

fcgi-pm.py - TCP Server<br>
hello.py   - external program for the fcgi-pm.py

Example
 ./fcgi-pm.py --count=4 --queue-size=100  --cgi="/home/www/fcgi/hello.py --param1=value1 --param2=value2" --daemon=Yes
run <--count> workers, each worker process <--queue-size> requests and dies. 
Server restarts each died worker.

Test with ab
ab -c 5 -n 150 http://127.0.0.1:8888/

