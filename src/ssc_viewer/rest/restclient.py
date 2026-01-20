import requests

from requests import Response


# from opener.opener_interface import OpenerFacade
# from opener.opera_lock_operner import OperaLockOpenerFacade


def apriporta():
    try:
        ## self.opener.unlock()
        response: Response = requests.request("GET", "http://server.door/open")
        response = Response()
        response.status_code = 200
        return response

    except Exception as ex:
        response = Response()
        response.status_code = 500
        response.reason = ex.__str__()
        return response


class SscClient:
    def __init__(self, host, plc):
        self.host = host
        self.plc = plc
        self.header = self.getHeader()
        # self.opener: OpenerFacade = OperaLockOpenerFacade()

    @staticmethod
    def getHeader():
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        return headers

    def getResource(self):
        return requests.get(self.host + '/api/resource')

    def getPlc(self):
        return requests.get(self.host + '/api/plc')

    def sendPayload(self, token=None, plc=None):
        try:
            response: Response = requests.request("GET", self.host + '/api/activation/token/' + token,
                                                  headers=self.header)
            return response

        except Exception as ex:
            response = Response()
            response.status_code = 500
            return response

    def validate(self, token=None, plc=None):
        try:
            response: Response = requests.get(self.host + '/validate/token/' + token)
            return response

        except Exception as ex:
            response = Response()
            response.status_code = 500
            return response

    def apriportaNuki(self):
        try:
            response: Response = requests.request("POST", 'https://api.nuki.io/smartlock/18144720508/action/unlock',
                                                  headers=self.header)
            return response

        except Exception as ex:
            response = Response()
            response.status_code = 500
            response.reason = ex.__str__()
            return response


    def currentReservation(self, tag=None,callback=None):
        try:
            print("Check if exists reservation in progress")
            print(self.host + '/api/resource/reservation/' + tag)
            response: Response = requests.request("GET",self.host + '/api/resource/reservation/' + tag, headers=self.header,timeout=5)
            if callback is not None:
                callback(response)


        except Exception as ex:
            response = Response()
            response.status_code = 500
            response.reason = ex.__str__()
            if callback is not None:
                callback(response)


if __name__ == '__main__':
    client = SscClient('http://totem.local:8080/ssc', 9900001)

    response = client.currentReservation('IN00164')
    body = response.json()
    print(body['result'])
    ##try:
    ##response = client.getPlc()
    ##payload = response.json()
    ##for resource in payload['result']: print(resource)

    # except Exception as e:
    #    print('Connection error %s' % e)

    # client.sendPayload()
