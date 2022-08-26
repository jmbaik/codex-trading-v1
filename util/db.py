import pymysql
from datetime import datetime


class DbHelper:
    def __init__(self):
        self.conn = pymysql.connect(host='localhost', user='metstock', password='man100', charset='utf8', db='trading')

    def __del__(self):
        self.conn.close()

    def insert_che(self, code, dic):
        dic['code'] = code
        query = '''
            insert into trading.che(ymd, code, chetime, close, daebi, uprate, fshoga, fbhoga, vol, accvol, high, open, low) 
            values (curdate(), %(code)s, %(chetime)s, %(close)s, %(daebi)s, %(uprate)s, %(fshoga)s, %(fbhoga)s, %(vol)s, %(accvol)s, %(high)s, %(open)s, %(low)s)
        '''
        cursor = self.conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(query, dic)
        self.conn.commit()
