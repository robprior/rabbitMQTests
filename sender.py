#!/user/bin/env python
import argparse
import sys
import pika
import uuid
from collections import namedtuple

#Class for handling producing
class Sender(object):
	def __init__(self):
	  #setup the connection
	  self.connection = pika.BlockingConnection(pika.ConnectionParameters(
					               'localhost'))
          self.channel = self.connection.channel()

	  #add a temporary, and exclusive call back queue for any response
	  result = self.channel.queue_declare(exclusive = True)
	  self.callbackQueue = result.method.queue
	  self.channel.basic_consume(self.processResponse, queue=self.callbackQueue)

	  #create any constants necessary for the class here
	  #note these aren't true constants
	  #any code like 'self.const.rpcQueueName = ' won't work
	  #however it is possible to just re assign self.consts unfortunatly
	  Constants = namedtuple('String_Constants', ['rpcQueueName'])
	  self.consts = Constants('rpcQueue');

	def processResponse(self, ch, method, props, body):
	  #if the ID of the last message sent is the same response ID
	  if self.correlationID == props.correlation_id:
	    print "Got a response from the RPC server"
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
   	  print " [x] Sent " + args.stringToSend[0] + " to " + args.destination[0]

	#send a rpc request
	def rpcRequest(self, args):
	  print "Sending rpc request"
	  print args
	  self.response = None
	  self.correlationID = str(uuid.uuid4())
	  self.channel.queue_declare(queue=self.consts.rpcQueueName)
	
	  stringToSend = args.FunctionToCall[0] + ','
	  for arg in args.Arguments:
	  	stringToSend += arg + ','	  
	  #cut of the last , string will be split by rpcServer 
	  stringToSend = stringToSend[:-1] 

	  self.channel.basic_publish(exchange='',
				     routing_key=self.consts.rpcQueueName,
				     properties=pika.BasicProperties(
					reply_to = self.callbackQueue,
					correlation_id = self.correlationID,
				     ),
				     body=stringToSend)
	  while self.response is None:
	  	self.connection.process_data_events()
	  print "Server responded with " + self.response

def rpcCreate(channel, args):
	#this would be neat to do but maybe hard get normal RPC/routing going first
	#maybe not practical unless could get decent file transfer going 
	pass

#Main
sender = Sender()

#create top level parser
parser = argparse.ArgumentParser(description='Send a message to a given AMQP queue or exchange')
subparsers = parser.add_subparsers()

#basic send command
send_parser = subparsers.add_parser('send')
send_parser.add_argument('stringToSend', nargs=1, help='Message that will be sent')
send_parser.add_argument('destination', nargs=1,  help='Specifies a destination queue or exchange (default is queue change with --exchange) for the given message')
send_parser.add_argument('--exchange', dest='sendToQueue', action='store_const',
                   const= False, default= True,
                   help='An exchange will be used and any consumers using the same exchange will get the messages')
send_parser.set_defaults(func=sender.send)

#rpc call command
rpcCall_parser = subparsers.add_parser('rpcRequest')
rpcCall_parser.add_argument('FunctionToCall', nargs=1, help='The function to call from the rpc server')
rpcCall_parser.add_argument('Arguments', nargs='*', help='list of arguments for function');
rpcCall_parser.set_defaults(func=sender.rpcRequest)

#End parser creation

#parse the arguments and call the right function with the established connection
args = parser.parse_args()
args.func(args)
