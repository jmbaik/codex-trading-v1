import operator

import pymysql
from sqlalchemy import create_engine
import pandas as pd

pymysql.install_as_MySQLdb()
import warnings

warnings.filterwarnings('ignore')


class Codex:
    def __init__(self):
        self.df_sim_high = None
        self.df_sim_gapup = None
        self.conn = pymysql.connect(host='localhost', user='metstock', password='man100', db='codex', charset='utf8')
        self.engine = create_engine('mysql+mysqldb://{}:{}@{}:{}/{}'.format("metstock", "man100", "localhost", 3306, "codex"))
        self.df_codes = self.call_code_name()
        self.dic_codex_m1 = {}

    def __del__(self):
        self.conn.close()

    def call_code_name(self):
        query = "select lower(`종목코드`) as code, `종목명` as name from codex.code_name where `종목코드` like 'a%'"
        return pd.read_sql(query, self.conn, index_col="code")

    def call_m1(self, code="a005930", count=365):
        query = '''
                    select * from (
                        select date, open, high, low, close, volume
                            , row_number() over(order by date desc) as rn
                        from codex.{0} a
                    ) m
                    where m.rn < {1} 
                    order by date asc
                '''.format(code, count + 1)
        return pd.read_sql(query, self.conn, index_col="date", parse_dates={"date": {"format": "%Y%m%d"}})

    def mk_codex_m1(self):
        for c in self.df_codes.index:
            df = self.call_m1(code=c)
            self.dic_codex_m1.update({c: df})

    def calc_gap_up_list(self):
        if len(self.dic_codex_m1) == 0:
            self.mk_codex_m1()
        self.df_sim_gapup = {}
        list_gap = []; list_code = []; list_name = []
        for m1key in self.dic_codex_m1.keys():
            df = self.dic_codex_m1.get(m1key)
            _gap = df.iloc[-1]['open'] - df.iloc[-2]['close']
            _gap = _gap / df.iloc[-2]['close'] * 100
            # 양봉인 경우
            _con1 = df.iloc[-1]['open'] < df.iloc[-1]['close']
            _con2 = df.iloc[-2]['open'] < df.iloc[-2]['close']
            if _gap > 2:
                list_code.append(m1key)
                list_gap.append(_gap)
                list_name.append(self.df_codes.loc[m1key]['name'])
        self.df_sim_gapup = pd.DataFrame({'code': list_code, 'name': list_name, 'gap': list_gap}, columns=['code', 'name', 'gap'])
        self.df_sim_gapup.set_index('code', inplace=True)
        self.df_sim_gapup = self.df_sim_gapup.sort_values('gap', ascending=False)

    def calc_close_high_list(self):
        if len(self.dic_codex_m1) == 0:
            self.mk_codex_m1()
        self.df_sim_high = {}
        list_gap = []; list_code = []; list_name = []
        for m1key in self.dic_codex_m1.keys():
            df = self.dic_codex_m1.get(m1key)
            _gap = df.iloc[-1]['close'] - df.iloc[-2]['close']
            _gap = _gap / df.iloc[-2]['close'] * 100
            # 양봉인 경우
            if _gap > 2:
                list_code.append(m1key)
                list_gap.append(_gap)
                list_name.append(self.df_codes.loc[m1key]['name'])
        self.df_sim_high = pd.DataFrame({'code': list_code, 'name': list_name, 'gap': list_gap}, columns=['code', 'name', 'gap'])
        self.df_sim_high.set_index('code', inplace=True)
        self.df_sim_high = self.df_sim_high.sort_values('gap', ascending=False)

    def log_condition_ymd(self, ymd):
        with pymysql.connect(host='localhost', user='metstock', password='man100', db='trading', charset='utf8') as con:
            update_sql = "update trading.t_log set item_code = regexp_substr(msg, '[0-9]{6}') where log_date like '" + ymd + "%' and subject like '조건 검색%' ".format(ymd)
            cur = con.cursor()
            cur.execute(update_sql)
            con.commit()
            # sql = "select * from trading.t_log where log_date like '" + ymd + "%' and subject like '조건 검색%' order by log_date asc"
            sql = "select * from trading.t_log where log_date like '" + ymd + "%' and subject like '조건 검색%' order by log_date asc"
            return pd.read_sql(sql, con)


if __name__ == "__main__":
    codex = Codex()
    # df = codex.log_condition_ymd("20220809")
    # print(codex.df_codes.loc['a000020']['name'])
    # df = codex.call_m1()
    # print(df)
    # codex.mk_codex_m1()
    # print(codex.codex_m1.get('a005930'))
    # codex.calc_gap_up_list()
    # codex.df_sim_gapup.to_csv('D:\\sim_gapup.csv', encoding="utf-8-sig")
    codex.calc_close_high_list()
    codex.df_sim_high.to_csv('D:\\sim_high.csv', encoding="utf-8-sig")