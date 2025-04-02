class ConnectionObserver:

    def notifyOnClose(self, observable=None, message=None, exception=None):
        pass

    def notifyOnOpen(self, observable=None, message=None, exception=None):
        pass

    def notifyOnMessage(self, observable=None, message=None, exception=None):
        pass

    def notifyOnError(self, observable=None, message=None, exception=None):
        pass

class Displayer:

    def displayMessage(self,title,message,message_type):
        pass
