#!/usr/bin/env python
import argparse
import sys
import pika
import uuid
import os
import ConfigParser
import logging
import time

logging.basicConfig()
config = ConfigParser.ConfigParser()
config.read("./rabbitMQtests.config")

#Class for handling producing
class Sender(object):
	def __init__(self):
	  #setup the connection
	  sslOptions = {}
          sslOptions["ca_certs"]  = os.path.abspath(config.get('general', "CA_CERT_FILE"))
          sslOptions["certfile"]  = os.path.abspath(config.get('general', 'CLIENT_CERT_FILE'))
          sslOptions["keyfile"]   = os.path.abspath(config.get('general', 'CLIENT_KEY_FILE'))
     
          try:
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                                                           host=config.get('general', 'HOST'),
                                                           port=config.getint('general', 'PORT'),
                                                           ssl=config.getboolean('general', 'USE_SSL'),
                                                           ssl_options = sslOptions
                                                          )
                                                         )
                self.channel = self.connection.channel()
          except Exception as e:
                print "Could not connect to AMQP server, exiting with error:"
                print e
		sys.exit(1)

	  #add a temporary, and exclusive call back queue for any response
	  result = self.channel.queue_declare(exclusive = True)
	  self.callbackQueue = result.method.queue
	  self.channel.basic_consume(self.processResponse, queue=self.callbackQueue)
	
	def processResponse(self, ch, method, props, body):
	  #if the ID of the last message sent is the same response ID
	  if self.correlationID == props.correlation_id:
	    self.response = body

	#send a basic message
	def send(self, args):
	  #to a queue
    	  if(args.sendToQueue):
	  	self.channel.queue_declare(queue=args.destination[0])
		self.channel.basic_publish(exchange='',
	        		      routing_key=args.destination[0],
		                      body=args.stringToSend[0])
	  #to a fan out exchange (all listening receivers/consumers will get this message
	  else:
	  	self.channel.exchange_declare(exchange=args.destination[0],
		                              type='fanout')
		self.channel.basic_publish(exchange=args.destination[0],
					   routing_key='',
	               			   body=args.stringToSend[0])
   	  print "Sent " + args.stringToSend[0] + " to " + args.destination[0]

	#send a rpc request
	def rpcRequest(self, args):
	  print "Sending rpc request"
	  self.response = None
	  self.correlationID = str(uuid.uuid4())
	  self.channel.queue_declare(queue=config.get('general', 'RPC_REQUEST_Q'))
	
	  stringToSend = args.FunctionToCall[0] + ','
	  for arg in args.Arguments:
	  	stringToSend += arg + ','	  
	  #cut of the last , string will be split by rpcServer 
	  stringToSend = stringToSend[:-1] 
	  self.channel.basic_publish(exchange='',
	      			     routing_key=config.get('general', 'RPC_REQUEST_Q'),
				     properties=pika.BasicProperties(
					reply_to = self.callbackQueue,
					correlation_id = self.correlationID,
				     ),
				     body=stringToSend)
	  while self.response is None:
	   	self.connection.process_data_events()
	    
	def rpcCreate(self, args):
	  try:
		  with open (args.PathToFunction[0], "r") as funcFile:
		    data = funcFile.read()
	  except Exception as e:
	  	print "Unable to open file to due exception:"
		print e
		sys.exit(1)
	  self.channel.queue_declare(queue=config.get('general', 'RPC_CREATE_Q'))
	  self.channel.basic_publish(exchange='',
	        		     routing_key=config.get('general', 'RPC_CREATE_Q'),
		                     body=str(data))
	  print "Sent function to RPC server"
	
	def basicTiming(self, args):
	  self.response = None
	  self.correlationID = str(uuid.uuid4())
	  self.channel.queue_declare(queue=config.get('general', 'TIMING_Q'))
	
	  loops = int(args.NumLoops[0])
	  while loops > 0:
		  self.channel.basic_publish(exchange='',
	        			     routing_key=config.get('general', 'TIMING_Q'),
					     properties=pika.BasicProperties(
						reply_to = self.callbackQueue,
						correlation_id = self.correlationID,
					     ),
					     body='.')
		  while self.response is None:
		   	self.connection.process_data_events()
		  loops = loops - 1
	    
#Main

#create top level parser
parser = argparse.ArgumentParser(description='Send a message to a given AMQP queue or exchange')
subparsers = parser.add_subparsers(dest='command')

#basic send command
send_parser = subparsers.add_parser('send')
send_parser.add_argument('stringToSend', nargs=1, help='Message that will be sent')
send_parser.add_argument('destination', nargs=1,  help='Specifies a destination queue or exchange (default is queue change with --exchange) for the given message')
send_parser.add_argument('--exchange', dest='sendToQueue', action='store_const',
                   const= False, default= True,
                   help='An exchange will be used and any consumers using the same exchange will get the messages')
send_parser.set_defaults(func=Sender.send)

#rpc call command
rpcRequest_parser = subparsers.add_parser('rpcRequest')
rpcRequest_parser.add_argument('FunctionToCall', nargs=1, help='The function to call from the rpc server')
rpcRequest_parser.add_argument('Arguments', nargs='*', help='List of arguments for function');
rpcRequest_parser.set_defaults(func=Sender.rpcRequest)

#rpc create command
rpcCreate_parser = subparsers.add_parser('rpcCreate')
rpcCreate_parser.add_argument('PathToFunction', nargs=1, help='File to create new function on the rpc server. Caveat: a function called X must be in a file named X and the function is called with rpcRequest using the name X. This is why a function name is not required as a parameter. This function also must be the first function in the file.')
rpcCreate_parser.set_defaults(func=Sender.rpcCreate)

#basic timing command
timing_parser = subparsers.add_parser('time')
timing_parser.add_argument('NumLoops', nargs=1, help="Specify the number of empty messages to send to the receiver. Sender will wait for an acknowledgement vefore sending the next.")
timing_parser.set_defaults(func=Sender.basicTiming)

#End parser creation

#parse the arguments and call the right function with the established connection
args = parser.parse_args()
timeFunction = args.command == 'time'
if timeFunction: start = time.time()
sender = Sender()
args.func(sender, args)
if timeFunction:
  end = time.time()
  print "Time = " + str(end - start)
