import sys
from kiwoom.Kiwoom import *
from PyQt5.QtWidgets import *


class Ui_class():
    def __init__(self):
        print('UI class ')
        self.app = QApplication(sys.argv)

        self.kiwoom = Kiwoom()
        self.app.exec_()
