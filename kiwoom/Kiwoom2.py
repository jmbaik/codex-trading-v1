import sys
from datetime import datetime
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop
from PyQt5.QtTest import *
from config.KiwoomType import RealType
from config.log_class import Logging
from config.errorCode import *
from util.db_helper import *
from util.db import *
import pandas as pd
import pymysql
from pykrx import stock as krx


class Kiwoom2(QAxWidget):
    def __init__(self):
        super().__init__()
        self.realType = RealType()
        self.logging = Logging()
        # 변수
        self.trade_account = ''
        self.deposit = 0
        self.d2_deposit = 0
        self.enable_output = 0
        self.seed_total = 0
        self.seed = 0
        self.condition_target = [29, 30, 31, 34, 35, 26, 37, 38]
        # 딕셔너리 변수
        self.jango_stock_dict = {}
        self.condition_stock_dict = {}
        self.notche_stock_dict = {}
        self.jango_dict = {}
        # 스크린 번호 모음
        self.screen_account_info = '2000'
        self.screen_real_stock = '5000'
        self.screen_chart_data = '3000'
        self.screen_start_stop_real = '1000'
        self.screen_condition = '6000'
        self.screen_meme_tr_stock = '7000'
        self.screen_meme_real_stock = '8000'
        # 오늘 workday 아니면 실행하지 않음
        _today = datetime.today().strftime('%Y%m%d')
        _workday = krx.get_nearest_business_day_in_a_week(_today)
        if _today > _workday:
            print('today {0} is not {1}'.format(_today, _workday))
            sys.exit()

        # ocx 인스턴스 생성
        self.get_ocx_instance()
        # 로그인  ###################################
        self.login_event_loop = QEventLoop()
        self.connect_login_slot()  # 로그인 슬롯 연결
        self.signal_login_com_connect()
        # end 로그인 ################################

        # 이벤트 슬롯 connect #######################
        self.event_connect()
        self.tr_event_loop = QEventLoop()
        # end 이벤트 슬롯 ###########################
        self.deposit_event_loop = QEventLoop()
        self.jango_event_loop = QEventLoop()
        self.chart_data_event_loop = QEventLoop()
        self.get_account_info()  # 계좌 정보 가져 오기 - 로그인 이후 정보로 알수 있음
        self.req_deposit_info()  # 예수금 상세 현황 요청
        self.req_jango_stock()  # 잔고 현황 요청

        QTest.qWait(2000)
        self.dynamicCall('SetRealReg(QString, QString, QString, QString)', self.screen_start_stop_real, '', self.realType.REALTYPE['장시작시간']['장운영구분'], '0')

        # 조건 검색 부분 #################################
        self.condition_event_slot()
        self.condition_signal()
        self.db = DbHelper()

    def get_ocx_instance(self):
        self.setControl('KHOPENAPI.KHOpenAPICtrl.1')

    # 로그인
    def connect_login_slot(self):
        self.OnEventConnect.connect(self.login_slot)

    def login_slot(self, errcode):
        self.logging.logger.debug(errors(errcode)[1])
        self.login_event_loop.exit()

    def signal_login_com_connect(self):
        self.dynamicCall('CommConnect()')
        self.login_event_loop.exec_()

    # --// 로그인 end

    def event_connect(self):
        self.OnReceiveMsg.connect(self.msg_slot)
        self.OnReceiveTrData.connect(self.tr_data_slot)
        self.OnReceiveRealData.connect(self.real_data_slot)
        self.OnReceiveChejanData.connect(self.chejan_slot)

    def stop_screen_cancel(self, sScrNo=None):
        self.dynamicCall('DisconnectRealData(QString)', sScrNo)  # 스크린번호 연결 끓기

    def msg_slot(self, sScrNo, sRQName, sTrCode, msg):
        log_to_db('msg_slot','스크린: %s, 요청이름: %s, tr코드: %s --- %s' % (sScrNo, sRQName, sTrCode, msg))
        # self.logging.logger.debug('스크린: %s, 요청이름: %s, tr코드: %s --- %s' % (sScrNo, sRQName, sTrCode, msg))

    def tr_data_slot(self, sScrNo, sRQName, sTrCode, sRecordName, sPrevNext):
        '''
        tr 요청을 받는 슬롯이다.
        :param sScrNo: 스크린 번호
        :param sRQName: 내가 요청했을 때 지은 이름
        :param sTrCode: 요청 id,  tr코드
        :param sRecordName: 사용안함
        :param sPrevNext: 다음 페이지가 있는지
        :return:
        '''
        if sRQName == '예수금상세현황요청':
            deposit = self.dynamicCall('GetCommData(QString, QString, int, String)', sTrCode, sRQName, 0, '예수금')
            enable_output = self.dynamicCall('GetCommData(QString, QString, int, String)', sTrCode, sRQName, 0, '출금가능금액')
            d2_deposit = self.dynamicCall('GetCommData(QString, QString, int, String)', sTrCode, sRQName, 0, 'd+2추정예수금')
            self.deposit = int(deposit)
            self.enable_output = int(enable_output)
            self.d2_deposit = int(d2_deposit)
            self.seed_total = int(d2_deposit)
            self.logging.logger.debug('d2추정예수금:%s 예수금:%s 출금가능금액:%s' % (self.d2_deposit, self.deposit, self.enable_output))
            self.stop_screen_cancel(self.screen_account_info)
            self.deposit_event_loop.exit()

        elif sRQName == '계좌평가잔고내역요청':
            total_buy_money = int(self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, 0, '총매입금액'))
            total_profit_loss_money = int(self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, 0, '총평가손익금액'))
            total_profit_loss_rate = float(self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, 0, '총수익률(%)'))
            self.logging.logger.debug('계좌평가잔고내역요청 싱글 데이터 : %s - %s - %s' % (total_buy_money, total_profit_loss_money, total_profit_loss_rate))
            rows = self.dynamicCall('GetRepeatCnt(QString, QString)', sTrCode, sRQName)
            for i in range(rows):
                code = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '종목번호')
                code = code.strip()[1:]
                code_nm = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '종목명')
                stock_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '보유수량')
                buy_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '매입가')
                learn_rate = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '수익률(%)')
                current_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '현재가')
                total_che_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '매입금액')
                possible_qty = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '매매가능수량')

                self.logging.logger.debug('종목코드: %s - 종목명: %s - 보유수량: %s - 매입가:%s - 수익률: %s - 현재가: %s' % (
                    code, code_nm, stock_quantity, buy_price, learn_rate, current_price))

                self.jango_stock_dict.setdefault(code, {})

                code_nm = code_nm.strip()
                stock_quantity = int(stock_quantity.strip())
                buy_price = int(buy_price.strip())
                learn_rate = float(learn_rate.strip())
                current_price = int(current_price.strip())
                total_che_price = int(total_che_price.strip())
                possible_qty = int(possible_qty.strip())
                self.jango_stock_dict[code].update({'code_nm': code_nm})            # 종목명
                self.jango_stock_dict[code].update({'jango_qty': stock_quantity})   # 보유수량
                self.jango_stock_dict[code].update({'buy_price': buy_price})        # 매입가
                self.jango_stock_dict[code].update({'profit_rate': learn_rate})          # 수익률(%)
                self.jango_stock_dict[code].update({'cur_price': current_price})              # 현재가
                self.jango_stock_dict[code].update({'che_price': total_che_price})               # 매입 금액
                self.jango_stock_dict[code].update({'can_buy_qty': possible_qty})               # 매입 가능 수량

            self.logging.logger.debug('sPreNext : %s' % sPrevNext)

            if sPrevNext == '2':
                self.req_jango_stock(sPrevNext='2')
            else:
                jango_df = pd.DataFrame(self.jango_stock_dict)
                insert_df_to_db('trading', 'jango', jango_df)
                self.jango_event_loop.exit()

        elif sRQName == '주식일봉차트조회':
            code = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, 0, '종목코드')
            code = code.strip()
            cnt = self.dynamicCall('GetRepeatCnt(QString, QString)', sTrCode, sRQName)
            self.logging.logger.debug('남은 일자 수 %s' % cnt)
            for i in range(cnt):
                data = []
                current_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '현재가')
                value = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '거래량')
                trading_value = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '거래대금')
                date = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '일자')
                start_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '시가')
                high_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '고가')
                low_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '저가')
                data.append(current_price.strip())
                data.append(value.strip())
                data.append(trading_value.strip())
                data.append(date.strip())
                data.append(start_price.strip())
                data.append(high_price.strip())
                data.append(low_price.strip())
            if sPrevNext == '2':
                self.req_chart_data_1d(code=code, sPrevNext=sPrevNext)
            else:
                self.logging.logger.debug('총 일수 %s' % str(cnt))
                self.chart_data_event_loop.exit()

    def real_data_slot(self, sCode, sRealType, sRealData):
        if sRealType == '장시작시간':
            fid = self.realType.REALTYPE[sRealType]['장운영구분']  # (0:장시작전, 2:장종료전(20분), 3:장시작, 4,8:장종료(30분), 9:장마감)
            value = self.dynamicCall('GetCommRealData(QString, int)', sCode, fid)
            if value == '0':
                self.logging.logger.debug('장 시작 전')
            elif value == '3':
                self.logging.logger.debug('장 시작')
            elif value == '2':
                self.logging.logger.debug('장 종료, 동시 호가로 넘어감')
            elif value == '4':
                self.logging.logger.debug('3시30분 장 종료')
                for code in self.condition_stock_dict.keys():
                    scr_no = ''
                    if self.condition_stock_dict[code]['스크린번호'] is None:
                        scr_no = self.screen_condition
                    else:
                        scr_no = self.condition_stock_dict[code]['스크린번호']
                    self.dynamicCall('SetRealRemove(QString, QString)', scr_no, code)
                QTest.qWait(5000)
                sys.exit()

        elif sRealType == '주식체결':
            a = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['체결시간'])  # 출력 HHMMSS
            b = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['현재가'])  # 출력 : +(-)2520
            b = abs(int(b))
            c = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['전일대비'])  # 출력 : +(-)2520
            c = abs(int(c))
            d = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['등락율'])  # 출력 : +(-)12.98
            d = float(d)
            e = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['(최우선)매도호가'])  # 출력 : +(-)2520
            e = abs(int(e))
            f = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['(최우선)매수호가'])  # 출력 : +(-)2515
            f = abs(int(f))
            g = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['거래량'])  # 출력 : +240124  매수일때, -2034 매도일 때
            g = abs(int(g))
            h = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['누적거래량'])  # 출력 : 240124
            h = abs(int(h))
            i = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['고가'])  # 출력 : +(-)2530
            i = abs(int(i))
            j = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['시가'])  # 출력 : +(-)2530
            j = abs(int(j))
            k = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['저가'])  # 출력 : +(-)2530
            k = abs(int(k))
            self.condition_stock_dict.setdefault(sCode, {})
            self.condition_stock_dict[sCode].update({'chetime': a})        # 체결시간
            self.condition_stock_dict[sCode].update({'close': b})             # 현재가
            self.condition_stock_dict[sCode].update({'daebi': c})                # 전일대비
            self.condition_stock_dict[sCode].update({'uprate': d})                  # 등락율
            self.condition_stock_dict[sCode].update({'fshoga': e})
            self.condition_stock_dict[sCode].update({'fbhoga': f})
            self.condition_stock_dict[sCode].update({'vol': g})
            self.condition_stock_dict[sCode].update({'accvol': h})
            self.condition_stock_dict[sCode].update({'high': i})
            self.condition_stock_dict[sCode].update({'open': j})
            self.condition_stock_dict[sCode].update({'low': k})
            condition_df = pd.DataFrame(self.condition_stock_dict)
            insert_df_to_db('trading', 'condition', condition_df)
            self.db.insert_che(sCode, self.condition_stock_dict[sCode])
            log_to_db('체결', '%s : %s' % (sCode, self.condition_stock_dict[sCode],))
            # self.logging.logger.debug('%s : %s' % (sCode, self.condition_stock_dict[sCode],))
            '''
            if sCode in self.jango_dict.keys():
                jd = self.jango_dict[sCode]
                meme_rate = (b - jd['매입단가']) / jd['매입단가'] * 100
                if jd['주문가능수량'] > 0 and (meme_rate > 5 or meme_rate < -2):
                    screen_no = self.screen_meme_real_stock if self.condition_stock_dict[sCode]['screen_no_order'] is None else self.condition_stock_dict[sCode]['screen_no_order']
                    order_success = self.dynamicCall(
                        'SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)',
                        ['신규매도', screen_no, self.trade_account, 2, sCode, jd['주문가능수량'], 0, self.realType.SENDTYPE['거래구분']['시장가'], '']
                    )
                    if order_success == 0:
                        self.logging.logger.debug('%s %s : %s' % ('[신규매도]', sCode, self.condition_stock_dict[sCode],))
                    else:
                        self.logging.logger.debug('%s 매도 주문 전달 실패' % sCode)
            # 검색식 들어 오자 마자 매수
            if sCode not in self.jango_dict.keys() and e > 0:
                qty = int(2000000 / e)
                screen_no = self.screen_meme_real_stock if self.condition_stock_dict[sCode]['screen_no_order'] is None else self.condition_stock_dict[sCode]['screen_no_order']
                order_success = self.dynamicCall(
                    'SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)',
                    ['신규매수', screen_no, self.trade_account, 1, sCode, qty, e, self.realType.SENDTYPE['거래구분']['지정가'], '']
                )
                if order_success == 0:
                    self.logging.logger.debug('%s %s : %s' % ('[신규매수]', sCode, self.condition_stock_dict[sCode],))
                else:
                    self.logging.logger.debug('%s 매수 주문 전달 실패' % sCode)
            '''
    def chejan_slot(self, sGubun, nItemCnt, sFidList):
        if int(sGubun) == 0:  # 주문체결
            trade_account = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['계좌번호'])
            sCode = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['종목코드'])[1:]
            stock_name = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['종목명'])
            stock_name = stock_name.strip()
            origin_order_number = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['원주문번호'])  # 출력 : defaluse : '000000'
            order_number = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['주문번호'])  # 출럭: 0115061 마지막 주문번호
            order_status = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['주문상태'])  # 출력: 접수, 확인, 체결
            order_quan = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['주문수량'])  # 출력 : 3
            order_quan = int(order_quan)
            order_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['주문가격'])  # 출력: 21000
            order_price = int(order_price)
            not_chegual_quan = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['미체결수량'])  # 출력: 15, default: 0
            not_chegual_quan = int(not_chegual_quan)
            order_gubun = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['주문구분'])  # 출력: -매도, +매수
            order_gubun = order_gubun.strip().lstrip('+').lstrip('-')
            chegual_time_str = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['주문/체결시간'])  # 출력: '151028'
            chegual_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['체결가'])  # 출력: 2110  default : ''
            if chegual_price == '':
                chegual_price = 0
            else:
                chegual_price = int(chegual_price)
            chegual_quantity = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['체결량'])  # 출력: 5  default : ''
            if chegual_quantity == '':
                chegual_quantity = 0
            else:
                chegual_quantity = int(chegual_quantity)
            current_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['현재가'])  # 출력: -6000
            current_price = abs(int(current_price))
            first_sell_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['(최우선)매도호가'])  # 출력: -6010
            first_sell_price = abs(int(first_sell_price))
            first_buy_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['주문체결']['(최우선)매수호가'])  # 출력: -6000
            first_buy_price = abs(int(first_buy_price))
            # 새로 들어온 주문이면 주문번호 할당
            if order_number not in self.notche_stock_dict.keys():
                self.notche_stock_dict.update({order_number: {}})
            self.notche_stock_dict[order_number].update({'종목코드': sCode})
            self.notche_stock_dict[order_number].update({'주문번호': order_number})
            self.notche_stock_dict[order_number].update({'종목명': stock_name})
            self.notche_stock_dict[order_number].update({'주문상태': order_status})
            self.notche_stock_dict[order_number].update({'주문수량': order_quan})
            self.notche_stock_dict[order_number].update({'주문가격': order_price})
            self.notche_stock_dict[order_number].update({'미체결수량': not_chegual_quan})
            self.notche_stock_dict[order_number].update({'원주문번호': origin_order_number})
            self.notche_stock_dict[order_number].update({'주문구분': order_gubun})
            self.notche_stock_dict[order_number].update({'주문/체결시간': chegual_time_str})
            self.notche_stock_dict[order_number].update({'체결가': chegual_price})
            self.notche_stock_dict[order_number].update({'체결량': chegual_quantity})
            self.notche_stock_dict[order_number].update({'현재가': current_price})
            self.notche_stock_dict[order_number].update({'(최우선)매도호가': first_sell_price})
            self.notche_stock_dict[order_number].update({'(최우선)매수호가': first_buy_price})

        elif int(sGubun) == 1:  # 잔고
            trade_account = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['계좌번호'])
            sCode = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['종목코드'])[1:]
            stock_name = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['종목명'])
            stock_name = stock_name.strip()
            current_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['현재가'])
            current_price = abs(int(current_price))
            stock_quan = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['보유수량'])
            stock_quan = int(stock_quan)
            like_quan = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['주문가능수량'])
            like_quan = int(like_quan)
            buy_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['매입단가'])
            buy_price = abs(int(buy_price))
            total_buy_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['총매입가'])  # 계좌에 있는 종목의 총매입가
            total_buy_price = int(total_buy_price)
            meme_gubun = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['매도매수구분'])
            meme_gubun = self.realType.REALTYPE['매도수구분'][meme_gubun]
            first_sell_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['(최우선)매도호가'])
            first_sell_price = abs(int(first_sell_price))
            first_buy_price = self.dynamicCall('GetChejanData(int)', self.realType.REALTYPE['잔고']['(최우선)매수호가'])
            first_buy_price = abs(int(first_buy_price))
            if sCode not in self.jango_dict.keys():
                self.jango_dict.update({sCode: {}})
            self.jango_dict[sCode].update({'현재가': current_price})
            self.jango_dict[sCode].update({'종목코드': sCode})
            self.jango_dict[sCode].update({'종목명': stock_name})
            self.jango_dict[sCode].update({'보유수량': stock_quan})
            self.jango_dict[sCode].update({'주문가능수량': like_quan})
            self.jango_dict[sCode].update({'매입단가': buy_price})
            self.jango_dict[sCode].update({'총매입가': total_buy_price})
            self.jango_dict[sCode].update({'매도매수구분': meme_gubun})
            self.jango_dict[sCode].update({'(최우선)매도호가': first_sell_price})
            self.jango_dict[sCode].update({'(최우선)매수호가': first_buy_price})
            if stock_quan == 0:
                del self.jango_dict[sCode]

    # 요청 부분
    def get_account_info(self):
        account_list = self.dynamicCall('GetLoginInfo(String)', 'ACCLIST')
        print('계좌정보 리스트 값 : %s' % account_list)
        self.trade_account = account_list.split(';')[0]
        print('나의 보유계좌 번호 %s ' % self.trade_account)

    def req_deposit_info(self):
        self.dynamicCall('SetInputValue(QString, QString)', '계좌번호', self.trade_account)
        self.dynamicCall('SetInputValue(QString, QString)', '비밀번호', '0000')
        self.dynamicCall('SetInputValue(QString, QString)', '비밀번호입력매체구분', '00')
        self.dynamicCall('SetInputValue(QString, QString)', '조회구분', '2')
        self.dynamicCall('CommRqData(QString, QString, int, String)', '예수금상세현황요청', 'opw00001', '0', self.screen_account_info)
        log_to_db('예수금 상세 현황 요청', '[예수금 상세 현황 요청] 계좌번호: %s' % self.trade_account)
        # self.logging.logger.debug('[예수금 상세 현황 요청] 계좌번호: %s' % self.trade_account)
        self.deposit_event_loop.exec_()

    def req_jango_stock(self, sPrevNext='0'):
        self.dynamicCall('SetInputValue(QString, QString)', '계좌번호', self.trade_account)
        self.dynamicCall('SetInputValue(QString, QString)', '비밀번호', '0000')
        self.dynamicCall('SetInputValue(QString, QString)', '비밀번호입력매체구분', '00')
        self.dynamicCall('SetInputValue(QString, QString)', '조회구분', '2')
        self.dynamicCall('CommRqData(QString, QString, int, String)', '계좌평가잔고내역요청', 'opw00018', sPrevNext, self.screen_account_info)
        self.jango_event_loop.exec_()

    # 차트 데이터 요청
    def req_chart_data_1d(self, code=None, date=None, sPrevNext='0'):
        QTest.qWait(3600)  # 3.6초마다 딜레이를 준다.
        self.dynamicCall('SetInputValue(QString, QString)', '종목코드', code)
        self.dynamicCall('SetInputValue(QString, QString)', '수정주가구분', '1')
        if date is not None:
            self.dynamicCall('SetInputValue(QString, QString)', '기준일자', date)
        self.dynamicCall('CommRqData(QString, QString, int, QString)', '주식일봉차트조회', 'opt10081', sPrevNext, self.screen_chart_data)  # Tr서버로 전송 -Transaction
        self.chart_data_event_loop.exec_()

    def req_chart_data_3m(self, code=None, tick='3', sPrevNext='0'):
        QTest.qWait(3600)  # 3.6초마다 딜레이를 준다.
        self.dynamicCall('SetInputValue(QString, QString)', '종목코드', code)
        gb = str(tick) + ':' + str(tick) + '분'
        self.dynamicCall('SetInputValue(QString, QString)', '틱범위', gb)
        self.dynamicCall('SetInputValue(QString, QString)', '수정주가구분', '1')
        self.dynamicCall('CommRqData(QString, QString, int, QString)', '주식분봉차트조회요청', 'opt10080', sPrevNext, self.screen_chart_data)  # Tr서버로 전송 -Transaction
        self.chart_data_event_loop.exec_()

    # 조건 검색식 이벤트 모음 #################################################################################################################
    def condition_event_slot(self):
        self.OnReceiveConditionVer.connect(self.condition_slot)
        self.OnReceiveTrCondition.connect(self.condition_tr_slot)
        self.OnReceiveRealCondition.connect(self.condition_real_slot)

    # 조건식 로딩 하기
    def condition_signal(self):
        self.dynamicCall('GetConditionLoad()')

    # 어떤 조건식이 있는지 확인
    def condition_slot(self, lRet, sMsg):
        self.logging.logger.debug('호출 성공 여부 %s, 호출 결과 메시지 %s' % (lRet, sMsg))
        condition_name_list = self.dynamicCall('GetConditionNameList()')
        self.logging.logger.debug('HTS 의 조건 검색식 이름 가져 오기 %s' % condition_name_list)
        condition_name_list = condition_name_list.split(';')[:-1]
        for unit_condition in condition_name_list:
            index = unit_condition.split('^')[0]
            index = int(index)
            condition_name = unit_condition.split('^')[1]
            if index in self.condition_target:
                ok = self.dynamicCall('SendCondition(QString, QString, int, int)', '0156', condition_name, index, 1)  # 조회 요청 + 실시간 조회
                self.logging.logger.debug('조회 성공 여부 %s ' % ok)

    # 나의 조건식에 해당하는 종목코드 받기
    def condition_tr_slot(self, sScrNo, strCodeList, strConditionName, index, nNext):
        self.logging.logger.debug('화면 번호: %s, 종목코드 리스트: %s, 조건식 이름: %s, 조건식 인덱스: %s, 연속 조회: %s' % (sScrNo, strCodeList, strConditionName, index, nNext))
        code_list = strCodeList.split(';')[:-1]
        self.logging.logger.debug('코드 종목 \n %s' % code_list)
        for code in code_list:
            self.condition_stock_dict.setdefault(code, {})
            self.condition_stock_dict[code].update({'조건식': strConditionName, '인덱스': index, '타입': 'TR', '스크린번호': self.screen_condition, '검색 시간': self.get_time()})
            self.condition_stock_dict[code].update({'screen_no_order': self.screen_meme_tr_stock})
            self.req_real_che(code)

    def condition_real_slot(self, strCode, strType, strConditionName, strConditionIndex):
        self.logging.logger.debug('종목코드: %s, 이벤트 종류: %s, 조건식 이름: %s, 조건명 인덱스: %s' % (strCode, strType, strConditionName, strConditionIndex))
        if strType == 'I':
            self.condition_stock_dict.setdefault(strCode, {})
            self.condition_stock_dict[strCode].update({'조건식': strConditionName, '인덱스': strConditionIndex, '타입': 'RI', '스크린번호': self.screen_condition, '검색 시간': self.get_time()})
            self.condition_stock_dict[strCode].update({'screen_no_order': self.screen_meme_real_stock})
            self.req_real_che(strCode)
            log_to_db('조건 검색 종목 추가', '[조건 검색 종목 추가] 종목코드: %s, 종목 편입: %s' % (strCode, strType))
            # self.logging.logger.debug('[조건 검색 종목 추가] 종목코드: %s, 종목 편입: %s' % (strCode, strType))
        elif strType == 'D':
            self.condition_stock_dict.setdefault(strCode, {})
            self.condition_stock_dict[strCode].update({'종목 이탈 시간': self.get_time()})
            log_to_db('조건 검색 종목 이탈', '[조건 검색 종목 이탈] 종목코드: %s, 종목 이탈: %s' % (strCode, strType))
            # self.logging.logger.debug('[조건 검색 종목 이탈] 종목코드: %s, 종목 이탈: %s' % (strCode, strType))

    # 실시간 체결 정보 요청
    def req_real_che(self, code):
        self.condition_stock_dict.setdefault(code, {})
        self.condition_stock_dict[code].update({'스크린번호': str(self.screen_real_stock)})
        screen_num = self.condition_stock_dict[code]['스크린번호']
        fids = self.realType.REALTYPE['주식체결']['체결시간']
        self.dynamicCall('SetRealReg(QString, QString, QString, QString)', screen_num, code, fids, '1')
        log_to_db('실시간 체결 정보 요청', '[실시간 체결 정보 요청] 종목코드: %s, 스크린번호: %s, FID: %s' % (code, screen_num, fids))
        # self.logging.logger.debug('[실시간 체결 정보 요청] 종목코드: %s, 스크린번호: %s, FID: %s' % (code, screen_num, fids))

    def get_time(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
