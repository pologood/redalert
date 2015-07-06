#-*-coding:utf-8-*-
import MySQLdb
import sys
import subprocess
import time
import datetime
import random
import getopt
###### zhou fei 2014-07-28

from fabric.api import env,run,put,get,local
reload(sys)
sys.setdefaultencoding('gbk')


ywpt_db_conf='/home/mysql/admin/bin/newbin/ywpt_db.conf'
tmp_ywpt_db_conf='/home/mysql/admin/bin/newbin/tmp_ywpt_db.conf'

monitor_db={}
tmp_monitor_db={}
is_completed='N'
g_gmt_create_dt=datetime.datetime.now()
g_gmt_create=g_gmt_create_dt.strftime('%Y%m%d%H%M%S')
g_gmt_modify=g_gmt_create

def main():
    global g_db_id,g_alert_file,g_alert_key

    try:
        opts, args = getopt.getopt(sys.argv[1:], "Hh:d:f:k:", ["help", "dbid=","alertfile=","alertkey="])
        if len(sys.argv)==1: 
           usage()
           sys.exit(2)
    except getopt.GetoptError:
        # print help information and exit:
        usage()
        sys.exit(2)
    for name,value in opts:
        if name in ("-H","--help"):
           usage()
           sys.exit()
        if name in ("-h","--help"):
           usage()
           sys.exit()
        if name in ("-d","--dbid"):
           g_db_id=value
           print "dbid:"+g_db_id
        if name in ("-f","--alertfile"):
           g_alert_file=value
           print "alert file:"+g_alert_file
        if name in ("-k","--alertkey"):
           g_alert_key=value
           print "alert key:"+g_alert_key
    get_host_alert(g_db_id,g_alert_file,g_alert_key)

def read_conf(conf_file,type):
    file_hand=open(conf_file)
    for line in file_hand:
        line=line.strip()
        (name,value)=line.split(':')
        if type=='ywpt':
            monitor_db[name]=value
        if type=='tmp':
            tmp_monitor_db[name]=value
    file_hand.close()

read_conf(ywpt_db_conf,'ywpt')

mysqldb = MySQLdb.connect(host=monitor_db.get('ip'), user=monitor_db.get('user'),passwd=monitor_db.get('pass'),db=monitor_db.get('db'),port=int(monitor_db.get('port')) ,charset="utf8")
mysqlcur=mysqldb.cursor()






def get_server_pass(t_db_id):
    global g_username
    global g_password
    global g_hostname,g_host_id,g_ip_addr
    mysqlcur.execute("set names utf8")
    t_sql="SELECT user_account,user_passwd,host_name,ip_addr FROM b_host_config a,b_db_config  b  WHERE a.host_id=b.host_id   AND b.db_id=%s limit 1 "
    mysqlcur.execute(t_sql,t_db_id)
    data = mysqlcur.fetchone()
        #hostname
    g_username,g_password,g_hostname,g_ip_addr=data

def insert_data(table_name,varlist):
                get_table_column('sys',table_name)
                mysqlcur.execute("replace into "+table_name+" ("+table_column_mysql+" ) values ("+var_list+")",(varlist))
                mysqldb.commit()

def get_table_column(table_owner,table_name):
    global table_column
    global table_column_mysql
    global var_list
    global table_column_cnt
    read_conf(tmp_ywpt_db_conf,'tmp')
    mysqldbtmp =  MySQLdb.connect(host=tmp_monitor_db.get('ip'), user=tmp_monitor_db.get('user'),passwd=tmp_monitor_db.get('pass'),db=tmp_monitor_db.get('db'),port=int(tmp_monitor_db.get('port')), charset="utf8")
    tmpcur=mysqldbtmp.cursor()
    tmpcur.execute("set names utf8")
    tmpcur.execute("SELECT column_name FROM  COLUMNS WHERE table_name=%s ORDER BY ORDINAL_POSITION",(table_name,))
    data=tmpcur.fetchall()
    table_column=''
    table_column_mysql=''
    table_column_cnt=0
    var_list=''
    for x in data:
       table_column_cnt=table_column_cnt+1
       table_column=table_column+str(x[0])+','
       table_column_mysql=table_column_mysql+'`'+str(x[0])+'`'+','
       var_list=var_list+'%s'+','
    table_column=table_column.rstrip(',')
    table_column_mysql=table_column_mysql.rstrip(',')
    var_list=var_list.rstrip(',')

def open_alert_file(t_filename):
      conf_file=t_filename
      file_hand=open(conf_file)
      for line in file_hand:
             line=line.strip()
             t_tmd5,tmsg=line.split("$$$$$")
             t_sql="select count(*) from  b_error_msg where msg_md5=%s and alert_msg=%s"
             mysqlcur.execute(t_sql,(t_tmd5,tmsg))
             data=mysqlcur.fetchone()
             if data[0]>=1:
                continue
             t_sql="select count(*),max(gmt_created) from  b_error_msg where  alert_msg=%s and db_id=%s and gmt_created>=DATE_ADD(NOW(),INTERVAL -1 HOUR)"
             mysqlcur.execute(t_sql,(tmsg,g_db_id))
             t_cnt,t_create=mysqlcur.fetchone()
             if t_cnt>=3 :
                  continue
                
             t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
             info=[t_id,g_db_id,tmsg,is_completed,t_tmd5,g_gmt_create,g_gmt_modify,'0','1']
             insert_data('b_error_msg',info)
      file_hand.close()
def get_server_pass(t_db_id):
    global g_username
    global g_password
    global g_hostname,g_host_id,g_ip_addr,g_port
    mysqlcur.execute("set names utf8")
    t_sql="SELECT user_account,user_passwd,host_name,ip_addr,port FROM b_host_config a,b_db_config  b  WHERE a.host_id=b.host_id   AND b.db_id=%s limit 1 "
    mysqlcur.execute(t_sql,(t_db_id,))
    data = mysqlcur.fetchone()
        #hostname
    g_username,g_password,g_hostname,g_ip_addr,g_port=data

def insert_data(table_name,varlist):
                get_table_column('sys',table_name)
                mysqlcur.execute("replace into "+table_name+" ("+table_column_mysql+" ) values ("+var_list+")",(varlist))
                mysqldb.commit()



    
    
def get_host_alert(t_db_id,t_alert_file,t_alert_key):
    get_server_pass(t_db_id)
    env.user=g_username
    env.host_string=g_ip_addr+':22'
    env.password = g_password
    put('/home/mysql/admin/bin/newbin/check_logerr.sh','/tmp')
    run('chmod +x /tmp/check_logerr.sh')
    run('/tmp/check_logerr.sh '+t_alert_file+' '+'"'+t_alert_key+'"'+' '+t_db_id)
    local('rm -rf '+'/tmp/alert-'+g_ip_addr+'_'+t_db_id+'.txt')
    get('/tmp/alert-'+g_hostname+'_'+t_db_id+'.txt','/tmp/alert-'+g_ip_addr+'_'+t_db_id+'.txt')
    open_alert_file('/tmp/alert-'+g_ip_addr+'_'+t_db_id+'.txt') 
    local('rm -rf '+'/tmp/alert-'+g_ip_addr+'_'+t_db_id+'.txt')
'''
if __name__=="__main__":
          g_db_id=g_type=sys.argv[1]
          g_alert_file=sys.argv[2]
          g_alert_key=sys.argv[3] 
          get_host_alert(g_db_id,g_alert_file,g_alert_key)
'''

def usage():
    print '''
---------------usage:------------------
python get_alert_info_new.py -d dbid -f alert_file_path -k alert_key
or
python get_alert_info_new.py --dbid=dbid --alertfile=alert_file_path --alertkey=alert_key
---------------------------------------
'''
         
if __name__=="__main__":
   main()
