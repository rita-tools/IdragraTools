class MyProgress:
    def __init__(self):
        pass

    def setConsoleInfo(self, text):
        text = text.encode('utf-8')
        print('CONSOLE_INFO: %s' % text)

    def error(self, text):
        text = text.encode('utf-8')
        print('ERROR: %s' % text)

    def setProgress(self, val):
        self.setPercentage(val)

    def setPercentage(self, val, printPerc=False):
        if printPerc:
            nblock = int(val / 10)
            blocks = ['#'] * nblock
            lines = ['_'] * (10 - nblock)
            bar = 'PROGRESS: ' + blocks + lines
            print(bar, end="\r")

        else:
            print('PERC: %s' % int(val))

    def setText(self, text):
        text = text.encode('utf-8')
        print('TEXT: %s' % text)

    def setInfo(self, text, error=False):
        text = text.encode('utf-8')
        if error:
            print('ERROR: %s' % text)
        else:
            print('INFO:  %s' % text)

    def pushInfo(self, text, error=False):
        text = text.encode('utf-8')
        if error:
            print('ERROR: %s' % text)
        else:
            print('INFO:  %s' % text)

    def setCommand(self, text):
        text = text.encode('utf-8')
        print('CMD: %s' % text)

    def reportError(self, text, error=False):
        text = text.encode('utf-8')
        if error:
            print('FATAL ERROR: %s' % text)
        else:
            print('WARNING:  %s' % text)
