---
date: 2026-02-17
title: Using Interactive Broker's TWSAPI
---
Documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/

# Setup

0. Have an IBKR account
1. Download Trader Work Station or IBGateway
	- https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#tws-download
2. Download the TWSAPI
	- https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#find-the-api
	- If you are on Mac or Linux, you should see a zip folder like `twsapi_macunix.1030.01.zip`. Unzipping that gives `twsapi` folder
	- Make a virtual environment and simply pip install the python client like `python3 -m pip install ./twsapi/IBJts/source/pythonclient`
# Architecture of the TWSAPI

Inside `twsapi/IBJts/source/pythonclient/ibapi/` you can see the guts of the python library. Importantly there is `client.py` and `wrapper.py`

`client.py` provides the class `EClient` and `wrapper.py` provides the class `EWrapper`. `EClient` has functions such as:
- `reqMktData`: Call this function to request market data. The market data will be returned by the tickPrice and tickSize events.
- `reqContractDetails`: Call this function to download all details for a particular underlying. The contract details will be received via the contractDetails() function on the EWrapper.
- `reqSecDefOptParams`: Requests security definition option parameters for viewing a contract's option chain

An app using TWSAPI will subclass both `EWrapper` and `EClient`. To run our app, we open up and login to TWS or IBGateway and the `EClient` will provide us with a `connect` function which establishes a socket between TWS/IBGateway and our app.

Once connected, our app will call `EClient` functions to send requests and the responses will be delivered to `EWrapper`. To access those responses, we will overload callback functions outlined by `EWrapper` such as:
- `tickPrice`: Market data tick price callback. Handles all price related ticks.
- `tickSize`: Market data tick size callback. Handles all size-related ticks.
- `contractDetails`: Receives the full contract's definitions.

To better understand the api, the most relevant files to look at are `client.py`, `decoder.py`, `wrapper.py`. 

Summarised and paraphrased version of `client.py` 

```python
import queue

from ibapi import decoder, comm

class EClient(object):
	def __init__(self, wrapper):
	    self.msg_queue = queue.Queue()
		self.wrapper = wrapper
		# ...
	
	# ... 
    def run(self):
        """This is the function that has the message loop."""
				
		while self.isConnected() or not self.msg_queue.empty():	
            text = self.msg_queue.get(block=True, timeout=0.2)
            fields = comm.read_fields(text)
            self.decoder.interpret(fields) # <-- eventually calls EWrapper functions

        self.disconnect()
				
```

The entry point is the `run` function which will consume response messages from IBGateway or Trader Workstation and deserialise them. 
- If you look at `decoder.py` you see `decoder.interpret` finds the appropriate `EWrapper` method to use and then calls `decoder.interpretWithSignature` which actually calls the `EWrapper` method to receive the parsed response
# Basic Example

Given we understand the architecture of the TWS API, we can write our app. 
- We subclass `EWrapper` and `EClient`
- We create a thread to execute the `EClient.run` function in the background which will forward responses over to our app 
- In the main thread we can run our own function `run_app` and call `EClient` functions like `reqMktData` to actually request data

```python
import threading
import time

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

class GetData(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

        self.connected_event = threading.Event()
        self.next_order_id = None
 
    def nextValidId(self, orderId: int):
        print(f"nextValidId: {orderId}")
        self.next_order_id = orderId
        self.connected_event.set()   # API is ready 

    def contractDetails(self, reqId, contractDetails):
        print("CONTRACT DETAILS:", reqId, contractDetails)

    def shutdown(self):
        print("Shutting down...")

        self.disconnect()

        if hasattr(self, "api_thread"):
            self.api_thread.join(timeout=5)

        print("Shutdown complete.")
        
def start_app():
    app = GetData()

    app.connect("127.0.0.1", 4002, clientId=1)

    api_thread = threading.Thread(target=app.run, daemon=True)
    api_thread.start()
    app.api_thread = api_thread

    if not app.connected_event.wait(timeout=10):
        raise RuntimeError("IBKR connection timed out")
    
    # app.reqMarketDataType(3)
    return app
    
def run_app(app):
    c = Contract()
    c.symbol = "3690"
    c.secType = "STK"
    c.exchange = "SEHK"
    c.currency = "HKD"
 

    app.reqContractDetails(
        reqId = 420,
        contract = c,
    )


if __name__ == "__main__":
    app_instance = start_app()
    run_app(app_instance)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received")
        app_instance.shutdown() 
```

## ReqId

Because requests and responses are sent/received asynchronously, we need a way to keep track of which responses came from which request. This is important when we send multiple different requests e.g. a request for each ticker. For a more complex example, we would need to keep a map of which reqId corresponds to which request and parameters. 

## Ports

`app.connect()` takes in address, port, and clientID. By default ports are set to mean
- 4001: IBGateway live trading
- 4002: IBGateway paper trading
- 7496: TWS live trading
- 7497: TWS paper trading

You can change which port is used by going to IBGateway > Configure (in the toolbar) > Settings > API > Settings.
## `threading.Event()`

Documentation for `threading` library: https://docs.python.org/3/library/threading.html

> An event manages a flag that can be set to true with the `set()` method and reset to false with the `clear()` method. The `wait()` method blocks until the flag is true. The flag is initially false.

Before we start making requests in our `run_app` function, we want to ensure that our app is connected. That is why we will wait for the `app.connected_event`.

When the app connects to TWS/IBGateway, the `nextValidId` will be called and `app.connected_event` will be set to true.

## `Contract`

Documentation: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#contracts

You will need to provide enough details when constructing the `Contract` object in order to uniquely specify a financial instrument. 