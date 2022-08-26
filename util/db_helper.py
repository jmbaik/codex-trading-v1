import pymysql
from sqlalchemy import create_engine
from datetime import datetime

pymysql.install_as_MySQLdb()


def pd_connect(user, password, db, host, port=3306):
    url = 'mysql+mysqldb://{}:{}@{}:{}/{}'.format(user, password, host, port, db)
    engine = create_engine(url)
    return engine


def check_table_exist(db_name, table_name):
    with pymysql.connect(host='localhost', user='metstock', password='man100', db=db_name, charset='utf8') as con:
        cur = con.cursor()
        # sql = "SELECT name FROM sqlite_master WHERE type='table' and name=:table_name"
        sql = f"SELECT TABLE_NAME FROM information_schema.TABLES where TABLE_SCHEMA=:db_name and TABLE_NAME = :table_name"
        cur.execute(sql, {"db_name": db_name, "table_name": table_name})

        if len(cur.fetchall()) > 0:
            return True
        else:
            return False


def insert_df_to_db(db_name, table_name, df, option="replace"):
    sql_engine = pd_connect('metstock', 'man100', db_name, 'localhost')
    df.to_sql(table_name, sql_engine, if_exists=option)


def execute_sql(db_name, sql, param={}):
    # with sqlite3.connect('{}.db'.format(db_name)) as con:
    with pymysql.connect(host='localhost', user='metstock', password='man100', db=db_name, charset='utf8') as con:
        cur = con.cursor()
        cur.execute(sql, param)
        return cur


def log_to_db(subject, log_msg):
    now = datetime.now()
    str_now = now.strftime('%Y%m%d%H%M%S')
    with pymysql.connect(host='localhost', user='metstock', password='man100', db='trading', charset='utf8') as con:
        sql = "INSERT INTO trading.t_log(log_date, subject, msg) VALUES(%s, %s, %s)"
        cur = con.cursor()
        cur.execute(sql, (str_now, subject, log_msg))
        con.commit()


if __name__ == "__main__":
    pass
