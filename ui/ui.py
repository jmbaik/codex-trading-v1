from PyQt5.QtWidgets import *

from kiwoom.Kiwoom2 import *


class Ui_class():
    def __init__(self):
        print('UI class ')
        self.app = QApplication(sys.argv)

        self.kiwoom = Kiwoom2()
        self.app.exec_()
