# -*- coding: utf-8 -*- 
import MySQLdb
import sys
import subprocess
import time
import datetime
import random
import subprocess
import os
from fabric.api import env,run,put,get,local
import getopt

#####zhou fei 2014-07-28

reload(sys)
sys.setdefaultencoding('gbk')
os.getenv("ORACLE_HOME")
os.getenv("LD_LIBRARY_PATH")
os.getenv("NLS_LANG")
os.environ['NLS_LANG'] = 'SIMPLIFIED CHINESE_CHINA.UTF8'
import cx_Oracle

ywpt_db_conf='/home/mysql/admin/bin/newbin/ywpt_db.conf'
tmp_ywpt_db_conf='/home/mysql/admin/bin/newbin/tmp_ywpt_db.conf'

monitor_db={}
tmp_monitor_db={}
is_completed='N'
ora_param={}

def main():
    global h_dbid,h_type

    try:
        opts, args = getopt.getopt(sys.argv[1:], "Hh:d:t:", ["help", "dbid=","host_type="])
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
           h_dbid=value
           print "h_dbid:"+h_dbid
        if name in ("-t","--host_type"):
           h_type=value
           print "G_HOST_TYPE:"+h_type
    connect_ora(h_dbid)

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

def get_table_column(table_owner,table_name):
    global table_column
    global table_column_mysql
    global var_list
    global table_column_cnt
    read_conf(tmp_ywpt_db_conf,'tmp')
    mysqldbtmp =  MySQLdb.connect(host=tmp_monitor_db.get('ip'), user=tmp_monitor_db.get('user'),passwd=tmp_monitor_db.get('pass'),db=tmp_monitor_db.get('db'),port=int(tmp_monitor_db.get('port')), charset="utf8")
    tmpcur=mysqldbtmp.cursor()
    tmpcur.execute("set names utf8")
    tmpcur.execute("SELECT column_name FROM  COLUMNS WHERE table_name=%s and table_schema=%s ORDER BY ORDINAL_POSITION",(table_name,monitor_db.get('db')))
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

def insert_data(select_sql,table_name):
    oraclecur.execute(select_sql)
    row=oraclecur.fetchone()
    cnt=0
    while row:
           value=[]
           for i in range(table_column_cnt):
                 tmp=row[i]
                 #中文转换出错
                 #if isinstance(tmp,str):
                 #   tmp=tmp.decode('utf8')
                 value.append(tmp)
           try:
                 t_sql="replace into  "+table_name+"( "+table_column_mysql+" ) values ("+var_list+")"
                 mysqlcur.execute(t_sql,value)
                 cnt=cnt+1
                 if (cnt%1000==0):
                    mysqldb.commit()
                 row=oraclecur.fetchone()
           except MySQLdb.Error,e:
                 print "Mysql Error %d: %s" % (e.args[0], e.args[1])
    mysqldb.commit()   

#取得在oracle里的dbid
def check_dbid(t_db_name):
    t_del="delete from dba_hist_database_instance where db_name=%s" 
    mysqlcur.execute(t_del,t_db_name)
    get_table_column('SYS','DBA_HIST_DATABASE_INSTANCE')
    insert_data(db_select_db_instance,'DBA_HIST_DATABASE_INSTANCE')
    global g_db_id
    mysqlcur.execute("SELECT dbid FROM dba_hist_database_instance WHERE db_name=%s LIMIT 1",t_db_name)
    g_db_id=mysqlcur.fetchone()
    

def check_snapid(dbid):
    t_snap_count="  select count(*) from ( select dbid from dba_hist_snapshot where dbid=%s limit 1) t"
    mysqlcur.execute(t_snap_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','DBA_HIST_SNAPSHOT')
       insert_data("select * from sys.dba_hist_snapshot",'DBA_HIST_SNAPSHOT')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from dba_hist_snapshot  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','DBA_HIST_SNAPSHOT')
       t_sql="select * from sys.dba_hist_snapshot where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'DBA_HIST_SNAPSHOT')

def check_sql_stat(dbid):
    t_sqlstat_count=" select count(*) from (select dbid from dba_hist_sqlstat where dbid=%s limit 1) t "
    mysqlcur.execute(t_sqlstat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','DBA_HIST_SQLSTAT')
       insert_data("select "+table_column+" from sys.dba_hist_sqlstat",'DBA_HIST_SQLSTAT')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from dba_hist_sqlstat  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','DBA_HIST_SQLSTAT')
       t_sql="select "+table_column+"  from sys.dba_hist_sqlstat where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'DBA_HIST_SQLSTAT')    

def check_sql_text():
       mysqlcur.execute("truncate table dba_hist_temp_sqltext")
       get_table_column('SYS','dba_hist_temp_sqltext')
       insert_data("select "+table_column+" from sys.dba_hist_sqltext",'dba_hist_temp_sqltext')
       get_table_column('SYS','DBA_HIST_SQLTEXT')
       mysqlcur.execute("DELETE a.*  FROM dba_hist_temp_sqltext a,dba_hist_sqltext b   WHERE a.dbid=b.DBID AND a.sql_id =b.sql_id")
       mysqlcur.execute("select dbid,sql_id from dba_hist_temp_sqltext")
       data=mysqlcur.fetchall()
       for x in data:
               tdbid,tsql_id=x
               insert_data("select "+table_column+" from sys.dba_hist_sqltext where dbid="+"'"+str(tdbid)+"'"+" and sql_id="+"'"+tsql_id+"'",'DBA_HIST_SQLTEXT')


def check_seg_obj(dbid):
       get_table_column('SYS','DBA_HIST_SEG_STAT_OBJ')
       insert_data("select "+table_column+" from sys.DBA_HIST_SEG_STAT_OBJ",'DBA_HIST_SEG_STAT_OBJ')


def check_active_session_his(dbid):
    t_active_session_count="  select count(*) from ( select dbid from dba_hist_active_sess_history where dbid=%s limit 1) t"
    mysqlcur.execute(t_active_session_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','dba_hist_active_sess_history')
       insert_data("select "+table_column+" from sys.dba_hist_active_sess_history",'dba_hist_active_sess_history')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from dba_hist_active_sess_history  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','dba_hist_active_sess_history')
       t_sql="select "+table_column+"  from sys.dba_hist_active_sess_history where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'dba_hist_active_sess_history')
    

def check_waitstat(dbid):
    t_waitstat_count="  select count(*) from ( select dbid from dba_hist_waitstat where dbid=%s limit 1) t"
    mysqlcur.execute(t_waitstat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','dba_hist_waitstat')
       insert_data("select "+table_column+" from sys.dba_hist_waitstat",'dba_hist_waitstat')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from dba_hist_waitstat  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','dba_hist_waitstat')
       t_sql="select "+table_column+"  from sys.dba_hist_waitstat where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'dba_hist_waitstat')


def check_sysstat(dbid):
    t_sysstat_count="  select count(*) from ( select dbid from DBA_HIST_SYSSTAT where dbid=%s limit 1) t"
    mysqlcur.execute(t_sysstat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','DBA_HIST_SYSSTAT')
       insert_data("select "+table_column+" from sys.DBA_HIST_SYSSTAT",'DBA_HIST_SYSSTAT')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from DBA_HIST_SYSSTAT  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','DBA_HIST_SYSSTAT')
       t_sql="select "+table_column+"  from sys.DBA_HIST_SYSSTAT where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'DBA_HIST_SYSSTAT')


def  check_osstat(dbid):
    t_osstat_count="  select count(*) from ( select dbid from DBA_HIST_OSSTAT where dbid=%s limit 1) t"
    mysqlcur.execute(t_osstat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','DBA_HIST_OSSTAT')
       insert_data("select "+table_column+" from sys.DBA_HIST_OSSTAT",'DBA_HIST_OSSTAT')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from DBA_HIST_OSSTAT  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','DBA_HIST_OSSTAT')
       t_sql="select "+table_column+"  from sys.DBA_HIST_OSSTAT where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'DBA_HIST_OSSTAT')

def check_segstat(dbid):
    t_segstat_count="  select count(*) from ( select dbid from DBA_HIST_SEG_STAT where dbid=%s limit 1) t"
    mysqlcur.execute(t_segstat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','DBA_HIST_SEG_STAT')
       insert_data("select "+table_column+" from sys.DBA_HIST_SEG_STAT",'DBA_HIST_SEG_STAT')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from DBA_HIST_SEG_STAT  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','DBA_HIST_SEG_STAT')
       t_sql="select "+table_column+"  from sys.DBA_HIST_SEG_STAT where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'DBA_HIST_SEG_STAT')


def check_undostat(dbid):
    t_undostat_count="  select count(*) from ( select dbid from DBA_HIST_UNDOSTAT where dbid=%s limit 1) t "
    mysqlcur.execute(t_undostat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','DBA_HIST_UNDOSTAT')
       insert_data("select "+table_column+" from sys.DBA_HIST_UNDOSTAT",'DBA_HIST_UNDOSTAT')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from DBA_HIST_UNDOSTAT  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','DBA_HIST_UNDOSTAT')
       t_sql="select "+table_column+"  from sys.DBA_HIST_UNDOSTAT where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'DBA_HIST_UNDOSTAT')


def check_buffer_pool_stat(dbid):
    t_bp_stat_count="  select count(*) from ( select dbid from DBA_HIST_BUFFER_POOL_STAT where dbid=%s limit 1) t"
    mysqlcur.execute(t_bp_stat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','DBA_HIST_BUFFER_POOL_STAT')
       insert_data("select "+table_column+" from sys.DBA_HIST_BUFFER_POOL_STAT",'DBA_HIST_BUFFER_POOL_STAT')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from DBA_HIST_BUFFER_POOL_STAT  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','DBA_HIST_BUFFER_POOL_STAT')
       t_sql="select "+table_column+"  from sys.DBA_HIST_BUFFER_POOL_STAT where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'DBA_HIST_BUFFER_POOL_STAT')

def check_sga_stat(dbid):
    t_bp_stat_count="  select count(*) from ( select dbid from dba_hist_sgastat where dbid=%s limit 1) t"
    mysqlcur.execute(t_bp_stat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','DBA_HIST_SGASTAT')
       insert_data("select "+table_column+" from sys.DBA_HIST_SGASTAT",'DBA_HIST_SGASTAT')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from DBA_HIST_SGASTAT  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','DBA_HIST_SGASTAT')
       t_sql="select "+table_column+"  from sys.DBA_HIST_SGASTAT where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'DBA_HIST_SGASTAT')


def check_system_event(dbid):
    t_bp_stat_count="  select count(*) from ( select dbid from dba_hist_system_event where dbid=%s limit 1) t"
    mysqlcur.execute(t_bp_stat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','dba_hist_system_event')
       insert_data("select "+table_column+" from sys.dba_hist_system_event",'dba_hist_system_event')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from dba_hist_system_event  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','dba_hist_system_event')
       t_sql="select "+table_column+"  from sys.dba_hist_system_event where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'dba_hist_system_event')


def check_sysmetric(dbid):
    t_bp_stat_count="  select count(*) from ( select dbid from dba_hist_sysmetric_summary  where dbid=%s limit 1) t"
    mysqlcur.execute(t_bp_stat_count,dbid)
    row=mysqlcur.fetchone()
    #判断是否采集过数据
    if row[0] == 0:
       #没有采集过，做全量收集
       get_table_column('SYS','dba_hist_sysmetric_summary')
       insert_data("select "+table_column+" from sys.dba_hist_sysmetric_summary ",'dba_hist_sysmetric_summary')
    else:
       #己采集过，取最大的snapid再采集
       mysqlcur.execute("select max(snap_id) from dba_hist_sysmetric_summary  where dbid=%s",dbid)
       t_snap_id=mysqlcur.fetchone()
       get_table_column('SYS','dba_hist_sysmetric_summary')
       t_sql="select "+table_column+"  from sys.dba_hist_sysmetric_summary where snap_id>"
       t_sql+=str(t_snap_id[0])
       insert_data(t_sql,'dba_hist_sysmetric_summary')




db_select_db_instance= "select a.DBID,a.INSTANCE_NUMBER,a.STARTUP_TIME,PARALLEL,VERSION,DB_NAME,INSTANCE_NAME,HOST_NAME,LAST_ASH_SAMPLE_ID\
  from sys.dba_hist_database_instance a,\
       (select dbid, instance_number, max(startup_time) startup_time\
          from sys.dba_hist_database_instance\
         group by dbid, instance_number) b\
 where a.dbid = b.dbid\
   and a.instance_number = b.instance_number\
   and a.startup_time = b.startup_time"


def get_ora_pass(t_dbid):
    global username,password,port,ip_addr,host_id,sid,ora_db_name,ora_host_name,host_user_name,host_password
    mysqlcur.execute("set names utf8")
    t_sql="SELECT a.db_username,a.db_passwd,a.port,b.ip_addr,a.host_id,sid,db_name,b.host_name,b.user_account,b.user_passwd FROM b_db_config a,b_host_config b WHERE a.host_id=b.host_id  and a.db_id=%s   limit 1 "
    mysqlcur.execute(t_sql,(t_dbid,))
    data = mysqlcur.fetchone()
    print data
    username,password,port,ip_addr,host_id,sid,ora_db_name,ora_host_name,host_user_name,host_password=data


def insert_data2(table_name,varlist):
                get_table_column('sys',table_name)
                mysqlcur.execute("replace into "+table_name+" ("+table_column_mysql+" ) values ("+var_list+")",(varlist))
                mysqldb.commit()

def get_awr():
     check_dbid(ora_db_name)
     check_snapid(g_db_id)
     check_sql_stat(g_db_id)
     check_active_session_his(g_db_id)
     check_waitstat(g_db_id)
     check_sysstat(g_db_id)
     check_osstat(g_db_id)
     check_segstat(g_db_id)
     check_seg_obj(g_db_id)
     check_undostat(g_db_id)
     check_buffer_pool_stat(g_db_id)
     check_system_event(g_db_id)
     check_sga_stat(g_db_id)
     check_sysmetric(g_db_id)
     

def get_sqltext():
     check_sql_text()

def get_ora_param():
    global g_statu
    g_statu=''
    mysqlcur.execute("SELECT id,upper(quota_name) FROM `b_quota_model` WHERE sys_category=2")
    data=mysqlcur.fetchall()
    for x in data:
        id,name=x
        ora_param[name]=id
        g_statu=g_statu+",'"+name+"'"
    g_statu=g_statu.lstrip(',') 


def get_ora_quota_collect_day_lastval(hostid,dbid,quota_id,snap_id):
    global ora_qcdl_lastval,ora_qcdl_lastval_date
    
    t_sql="select MAX(gmt_created),count(*) from  b_oracle_quota_collect_day WHERE host_id= "+"'"+hostid+"'"+" and db_id ="+"'"+dbid+"'"+" and quota_id="+"'"+str(quota_id)+"'"+" and snap_id<"+str(snap_id)
    mysqlcur.execute(t_sql)
    data=mysqlcur.fetchone()
    dt,cnt=data
    if cnt==0:
       ora_qcdl_lastval=0
       ora_qcdl_lastval_date='1990-01-01 00:00:00'
    else:
       t_sql="select quota_value from  b_oracle_quota_collect_day WHERE host_id= "+"'"+hostid+"'"+" and db_id ="+"'"+dbid+"'"+" and quota_id="+"'"+str(quota_id)+"'"+" and gmt_created="+"'"+str(dt)+"'"+" and snap_id<"+str(snap_id)
       mysqlcur.execute(t_sql)
       data= mysqlcur.fetchone()
       ora_qcdl_lastval=data[0]
       ora_qcdl_lastval_date=dt



def get_ora_stat(g_dbid):
    #取得oracle dbid
    g_completed="N"
    t_sql="select dbid,instance_number from sys.dba_hist_database_instance where instance_name="+"'"+sid+"'"+" and host_name="+"'"+ora_host_name+"'"+" and rownum <=1"
    oraclecur.execute(t_sql)
    data=oraclecur.fetchone()
    ora_dbid,ora_instance_number=data
    #判断是否取过数据
    t_sql="select count(*) from dba_hist_snapshot_orastat where dbid=%s and instance_number=%s"
    mysqlcur.execute(t_sql,(ora_dbid,ora_instance_number))
    row=mysqlcur.fetchone()
    if row[0] == 0:
       t_snap_id=0
    else:
       mysqlcur.execute("select max(snapid) from dba_hist_snapshot_orastat where dbid=%s and instance_number=%s",(ora_dbid,ora_instance_number))
       data=mysqlcur.fetchone()
       t_snap_id=data[0]
    t_sql="SELECT snap_id,dbid,instance_number,end_interval_time FROM  sys.dba_hist_snapshot WHERE snap_id>:1 and instance_number=:2 ORDER BY instance_number,snap_id"
    get_ora_param()
    oraclecur.execute(t_sql,(t_snap_id,ora_instance_number))
    data=oraclecur.fetchall()
    try:
       print data[0]
    except Exception as e:
       print "Oracle Awr NoData!!!"
       t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
       info=[t_id,g_dbid,"Oracle Awr Data Not Found,Please Check GATHER_STATS_JOB!!","N","oracle awr data",g_gmt_create,g_gmt_modify,'0','13']
       insert_data2('b_error_msg',info)
       os._exit(0)
    oraclecur2=oracledb.cursor()
    for x in data:
        m_snap_id,m_dbid,m_instance_number,g_gmt_create=x
        t_sql=" select 77777778,'sesson total',count(*) cnt_sum from GV$SESSION  where inst_id="+str(m_instance_number)+\
              " union  all "\
              " select 77777781,'undo_used',trunc(100 * nvl((select sum(undoblks) * 8 * 1024 as undouse from v$undostat where begin_time > (sysdate - 3 / 24)),0) /  (select sum(bytes) as undosum  from dba_data_files  where tablespace_name in  (select upper(value)  from v$parameter   where name = 'undo_tablespace'))) as undo_percent from dual"+\
              " union  all "\
              " select 77777777,'active sessoin',sum(decode(status,'INACTIVE',0,'ACTIVE',1,0))  from GV$SESSION  where inst_id="+str(m_instance_number)+\
              " union all "\
              " select 77777782,'share_pool_lib_hit', round((1-sum(reloads)/sum(pins))*100,2) hit from dba_hist_librarycache where dbid="+str(m_dbid)+\
              "  and instance_number="+str(m_instance_number)+" and snap_id="+str(m_snap_id)+  "  union all " +\
              " select  77777783,'share_pool_dict_hit',round(((1-(sum(GetMisses)/(sum(Gets)+sum(GetMisses))))* 100),2)  from dba_hist_rowcache_summary  where dbid="+str(m_dbid)+\
              "   and instance_number="+str(m_instance_number)+" and snap_id="+str(m_snap_id)+\
              " union all SELECT stat_id,stat_name,VALUE FROM sys.dba_hist_sysstat where upper(stat_name) in ("+g_statu+") and dbid="+str(m_dbid)+\
              " and instance_number="+str(m_instance_number)+" and snap_id="+str(m_snap_id)+  "  union all " +\
              " SELECT event_id stat_id,event_name stat_name,TOTAL_WAITS VALUE FROM sys.dba_hist_system_event where upper(event_name) "\
              " in ("+g_statu+") and dbid="+str(m_dbid)+\
              " and instance_number="+str(m_instance_number)+" and snap_id="+str(m_snap_id)+\
              " union all select metric_id stat_id,metric_name stat_name,round(average,2) value  from dba_hist_sysmetric_summary where upper(metric_name) "\
              " in ("+g_statu+") and dbid="+str(m_dbid)+\
              " and instance_number="+str(m_instance_number)+" and snap_id="+str(m_snap_id)
        oraclecur2.execute(t_sql)
        data2=oraclecur2.fetchall()
        g_gmt_modify=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        t_sql="delete from b_oracle_quota_collect_day  where snap_id="+str(m_snap_id)+" and db_id="+"'"+str(g_dbid)+"'"
        mysqlcur.execute(t_sql)
        for x2  in data2:
               v_id,v_name,v_value=x2
               get_ora_quota_collect_day_lastval(host_id,g_dbid,v_id,m_snap_id)
               t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
               info=[t_id,host_id,g_dbid,m_snap_id,v_id,v_name,v_value,g_gmt_create,g_gmt_modify,ora_qcdl_lastval,g_completed,ora_qcdl_lastval_date]
               insert_data2('b_oracle_quota_collect_day',info)
        info=[m_snap_id,m_dbid,m_instance_number]
        insert_data2('dba_hist_snapshot_orastat',info) 
    
def get_ora_long_sql(g_dbid):
    t_sql="select sid,serial#,username,machine,sql_hash_value,last_call_et from v$session s \
                where s.username is not null and s.username <>'SYS' and s.status='ACTIVE' and s.last_call_et>180 \
                and type='USER'"
    oraclecur.execute(t_sql)
    oraclecur2=oracledb.cursor()
    data=oraclecur.fetchall()
    g_gmt_modify=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    g_gmt_create=g_gmt_modify
    for x in data:
          t_sid,t_serial,t_username,t_machine,t_sql_hash_value,t_last_call_et=x
          t_sql2="select sql_text,piece from v$sqltext_with_newlines where hash_value="+str(t_sql_hash_value)+"  order by piece "
          oraclecur2.execute(t_sql2)
          data2=oraclecur2.fetchall()
          t_sqltext=""
          for x2  in data2:
              t_t_sqltext,t_piece=x2
              t_sqltext=t_sqltext+" "+t_t_sqltext
          t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
          info=[t_id,g_dbid,"session is to long:"+str(t_last_call_et)+" sec SID:"+str(t_sid)+","+str(t_serial)+"  USERNAME:"+t_username+"  MACHINE:"+t_machine+" HASH:"+str(t_sql_hash_value)+" SQL:"+t_sqltext,"N","Oracle long session",g_gmt_create,g_gmt_modify,'1','3']
          insert_data2('b_error_msg',info)

def get_trans_info(g_dbid):
     t_sql="   select   trans_cnt ,  round(max_blocks * 1000 * 8192 / 1024 / 1024, 2) undo_used_mb,  round(max_duration, 0)   max_duration_seconds  \
                 from (select count(*) trans_cnt,   \
                              nvl(max(used_ublk), 0) / 1000 max_blocks,  \
                              nvl((sysdate -  min(to_date(start_time, 'mm/dd/yy hh24:mi:ss'))),  0) * 1440 * 60 max_duration   \
                           from v$transaction) "
     oraclecur.execute(t_sql)
     data=oraclecur.fetchall()
     g_gmt_modify=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
     g_gmt_create=g_gmt_modify     
     for x in data:
           t_trans_cnt,t_undo_used_mb,t_max_duration_sec=x
           if t_trans_cnt>=50:
              t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
              info=[t_id,g_dbid,"trans more than:50 now:"+str(t_trans_cnt),"N","oracle trans cnt",g_gmt_create,g_gmt_modify,'0','7']
              insert_data2('b_error_msg',info)
           if t_undo_used_mb>=100:
              t_sql="select sid,serial#,username,machine,program,sql_id from v$session  where taddr=(select addr from v$transaction  where used_ublk in (select max(used_ublk) from v$transaction) and  rownum <=1)"
              oraclecur.execute(t_sql)
              data=oraclecur.fetchall()
              for x in data:
                  t_sid,t_serial,t_username,t_machine,t_program,t_sqlid=x
                  t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
                  info=[t_id,g_dbid,"trans undo more than:100M now:"+str(t_undo_used_mb)+"mb sid:"+str(t_sid)+","+str(t_serial)+" username:"+t_username+" machine:"+t_machine+" program:"+t_program+" sqlid:"+t_sqlid ,"N","oracle trans undo",g_gmt_create,g_gmt_modify,'0','8']
                  insert_data2('b_error_msg',info)                            
           if t_max_duration_sec>=180:
              t_sql="select sid,serial#,username,machine,program,sql_id from v$session  where osuser<>'oracle' and taddr=(select addr from v$transaction  where start_time in (select min(start_time) from v$transaction) and  rownum <=1)"              
              oraclecur.execute(t_sql)
              data=oraclecur.fetchall()
              for x in data:
                  t_sid,t_serial,t_username,t_machine,t_program,t_sqlid=x              
                  t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
                  info=[t_id,g_dbid,"trans time more than:180 sec now:"+str(t_max_duration_sec)+" sec sid:"+str(t_sid)+","+str(t_serial)+" username:"+t_username+" machine:"+t_machine+" program:"+t_program+" sqlid:"+t_sqlid ,"N","oracle trans time",g_gmt_create,g_gmt_modify,'0','4']
                  insert_data2('b_error_msg',info) 


def get_index_level(g_dbid):
     t_sql="select owner,index_name,blevel from dba_indexes where blevel >=4"
     oraclecur.execute(t_sql)
     data=oraclecur.fetchall()
     g_gmt_modify=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
     g_gmt_create=g_gmt_modify
     for x in data: 
              t_owner,t_index_name,t_blevel=x
              t_id=monitor_db.get('hid')+datetime.datetime.now().strftime('%Y%m%d%H%M%S')+str(random.randint(10000,90000))
              info=[t_id,g_dbid,"index level more than 4 now:"+str(t_blevel),"N","oracle index level",g_gmt_create,g_gmt_modify,'0','5']
              insert_data2('b_error_msg',info)             


def get_ora_standby(g_dbid):
    env.user=host_user_name
    env.host_string=ip_addr+':22'
    env.password = host_password
    run('ps -ef | grep oracle|wc -l')
          
def connect_ora(g_dbid):
  global oracledb,oraclecur,oraclecur2
  g_completed='N'
  g_gmt_create=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  g_gmt_modify=g_gmt_create
  table_name='b_oracle_quota_collect_day'
  get_ora_pass(g_dbid)  
  if h_type=='standby':
       get_ora_standby(g_dbid)  
  else:
       tns_name = cx_Oracle.makedsn(ip_addr,port,sid)
       oracledb = cx_Oracle.connect(username,password, tns_name)
       oraclecur=oracledb.cursor()
       if h_type=='awr':
               get_awr()
       if h_type=='sqltext':
               get_sqltext()
       if h_type=='stat':
               get_ora_stat(g_dbid)
       if h_type=='longsql':
               get_ora_long_sql(g_dbid)
       if h_type=='trans':
               get_trans_info(g_dbid)
       if h_type=='level':
               get_index_level(g_dbid)
  mysqlcur.close()
  mysqldb.close()
'''
if __name__=="__main__":
    h_dbid=sys.argv[1]   #要访问的db_id
    h_type=sys.argv[2] 
    connect_ora(h_dbid) 

'''

def usage():
    print '''
---------------usage:------------------
python get_ora_info_new.py -d dbid -t type (awr,sqltext,stat,longsql,trans,level)
or
python get_ora_info_new.py --dbid=dbid --host_type=(awr,sqltext,stat,longsql,trans,level)
---------------------------------------
'''

if __name__=="__main__":
   main()

