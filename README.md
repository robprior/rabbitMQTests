# RabbitMQ Python-Pika Tests

Simple set of files for testing the functionality of rabbitMQ AMQP servers.

## Overview

These test provide basic sending and receiving of messages to/from arbitrary queues or fanout exchanges. There is also support for basic remote procedure calls (RPC). These tests are largely based on the python tutorials for rabbitMQ located here http://www.rabbitmq.com/getstarted.html (though have some added functionality).

## Terminology

**AMQP queue** 

Queue to hold messages. It can have multiple senders/receivers associated with it. If there are multiple receivers, messages by default, will be sent in round robin to the receivers. A sender can send to a queue without any listening receivers; messages will just accumulate on the queue. 

**AMQP exchange**

An exchange does not hold any data; it just handles routing messages. If a sender sends a message to an exchange that currently does not have any associated queues, the message will be lost. Receivers must subscribe to exchanges to receive messages. Senders can specify a routing key to only send to specific queues (or receivers only getting specific messages). Currently in the tests, routing keys are not used so exchanges will send to all listening receivers.

**Remote Procedure Call**

Call a function on a remote machine. Senders can send RPC requests, consisting of a function to call and some arguments. The receiver runs the function and returns the result. 

## Components

### Sender

The sender has two main modes of operation, send and rpcRequest. One of these options must be specified when the script is run. 

**send**

send handles basic message passing and requires a string to send as well as a destination queue or exchange. A new queue/exchange will be created with the specified name if it doesn't exist already. These queues/exchanges will persist as long as the rabbitMQ server remains running. Messages will be lost when sent to an exchange if there are no listening receivers.

usage: sender.py send [-h] [--exchange] stringToSend destination

positional arguments:
  stringToSend  Message that will be sent
  destination   Specifies a destination queue or exchange (default is queue
                change with --exchange) for the given message

optional arguments:
  -h, --help    show this help message and exit
  --exchange    An exchange will be used and any consumers using the same
                exchange will get the messages

**rpcRequest**

rpcRequest performs a remote procedure call and requires a function name to call. Any arguments are optional. These parameters are positional; the first parameter will always be treated as the function name. When this function is called, a temporary queue is created for this sender. It receives the return message from an rpcReceiver. This queue is automatically destroyed when the sender exits. The rpcReceiver is not garunteed to perform the requested function call but will return any errors encountered (such as function doesn't exist, invalid paramters etc.). The sender will not exit until it gets a return and any return is printed to stdout. 

usage: sender.py rpcRequest [-h] FunctionToCall [Arguments [Arguments ...]]

positional arguments:
  FunctionToCall  The function to call from the rpc server
  Arguments       list of arguments for function

optional arguments:
  -h, --help      show this help message and exit

### Receiver 

The receiver listens to a specified queue or exchange without terminating. Receiver also supports handling rpcRequests.

**normal receive**

Receive takes two optional parameters source and exchange. Receive continually listens to the specified queue or the default 'defaultQueue'. If an exchange is specified, a temporary queue for this receiver is created. When a message is received, it is printed out to stdout.

**rpcMode**

rpcMode is option that requires and additional mode argument. As of this writing, it only supports rpcMode call. In this mode, any messages received interurpreted as RPCs. Once the function and argument list are parsed from the message body, the reciever attempts to open the function specified from the files in the rpcServerFunctions/ directory. This loading is done dynamically; while the receiver is running,  new RPC server functions can be created and old ones modified or deleted. There are a few restrictions however:

	1. Functions must take a single list of strings as a parameter
	2. A function with name X must be in a file called X.py (for example factorial function in factorial.py)

An RPC server function can call other functions as normal. The first time one of these functions is called a .pyc file by the same name is generated and used on subsequent calls[1]  provided the original .py file does not change.

If an error is encountered, wheter it is raised by the parsing or by the execution of the called function, the error message will be sent back to the sender.

Given that the functions are loaded from plain text, an easy expansion would be allowing new functions to be created. Doing so would involve writing a new .py file to the rpcServerFuncions. directory and loading as normal. This functionality has not been implemented

usage: receiver.py [-h] [--source SOURCE] [--exchange]
                   [--rpcMode {call,create}]

Receive messages from a given AMQP queue or exchange

optional arguments:
  -h, --help            show this help message and exit
  --source SOURCE       Specifies a source queue or exchange (default is queue
                        change with --exchange)
  --exchange            An exchange will be used. Any receivers/consumers will
                        see all messages from this exchange. A temporary
                        rabbitMQ named queue will be created specifically for
                        this instance of receiver and will be destroyed on
                        exit
  --rpcMode {call,create}
                        Sets up this receiver to handle remote procedure calls
                        (create not yet implemented)


(1) Not sure that the generated .pyc files are used. They are auto generated by the standard imp module that handles loading/imports. 

