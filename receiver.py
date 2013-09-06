#!/user/bin/env python
import argparse
import sys
import pika
import imp
from os import path
from collections import namedtuple

class Receiver(object):
	def __init__(self):	  
	  self.connection = pika.BlockingConnection(pika.ConnectionParameters(
          				       'localhost'))
	  self.channel = self.connection.channel()
	
	  #put any constants necessary for the class here
          #note these aren't true constants
          #any code like 'self.const.rpcQueueName = ' won't work
          #however it is possible to just re assign self.consts unfortunatly
          Constants = namedtuple('String_Constants', ['rpcQueueName'])
          self.consts = Constants('rpcQueue');

	  #set up directory where RPC functions will be stored
	  self.pathToRPCFunc = path.abspath('rpcServerFunctions/')

	def basicReceive(self, args):
	  outputMessage = " [*] Waiting for messages from "

	  #TODO little bit messy but source is either a string or a 1 element list of strings
	  #the string is known to be 'defaultQueue' (it isn't user specified) 
	  #and the list is known to force 1 element
	  #this converts the 1 element list of strings to a string
	  if(len(args.source) == 1):
		args.source = args.source[0]

	  if(args.receiveFromQueue):
		self.channel.queue_declare(queue=args.source)
		self.channel.basic_consume(self.basicCallback,
					   queue=args.source)
	 	outputMessage += "queue "
	  else:
   	  	self.channel.exchange_declare(exchange=args.source,
	  	     	                      type='fanout')
		result = self.channel.queue_declare(exclusive=True)
		queue_name = result.method.queue
		self.channel.queue_bind(exchange=args.source,
        		           queue=queue_name)
		self.channel.basic_consume(self.basicCallback,
				      queue=queue_name)
		outputMessage += "exchange "

	  outputMessage += args.source
	  print outputMessage
	  self.channel.start_consuming()

	def basicCallback(self, ch, method, properties, body):
	  print "[x] Received %r" % (body,)
	  ch.basic_ack(delivery_tag = method.delivery_tag)


	def rpcCallReceive(self, args):
	  self.channel.queue_declare(queue=self.consts.rpcQueueName)
	  self.channel.basic_consume(self.rpcCallback,
				     queue=self.consts.rpcQueueName)
	  print "Begining rpc Receive"
	  self.channel.start_consuming()

	def rpcCallback(self, ch, method, properties, body):
	  print "Received rpc %r" %(body,)
	  commandToParse = body.split(",");
	  function = commandToParse[0]
	  args = commandToParse[1:]
	  print "Attempting calling function %s with args %r" % (function, args,)
	  try:
		  fileHandle, pathName, impDescrip = imp.find_module(function, [self.pathToRPCFunc])
		  module = imp.load_module(function, fileHandle, pathName, impDescrip)
		  result = getattr(module, function)(args)
		  print "Print function returned " + str(result)
	  except Exception as e:
		  print "Encountered an error sending error response to sender"
		  result = e

	  self.channel.basic_publish(exchange='',
        	             	     routing_key=properties.reply_to,
	        	             properties=pika.BasicProperties(correlation_id = \
                		                                     properties.correlation_id),
		                     body=str(result))
          self.channel.basic_ack(delivery_tag = method.delivery_tag)

#Main
receiver = Receiver()

parser = argparse.ArgumentParser(description='Receive messages from a given  AMQP queue or exchange')

parser.add_argument('--source', dest='source', nargs=1, default="defaultQueue",  help='Specifies a source queue or exchange (default is queue change with --exchange)')
parser.add_argument('--exchange', dest='receiveFromQueue', action='store_const',
                   const= False, default= True,
                   help='An exchange will be used. Any receivers/consumers will see all messages from this exchange. A temporary rabbitMQ named queue will be created specifically for this instance of receiver and will be destroyed on exit')
parser.add_argument('--rpcMode', choices=['call', 'create'], dest='rpcMode',
		    help='Sets up this receiver to handle remote procedure calls (create not yet implemented)')

args = parser.parse_args()

if args.rpcMode is None:
	receiver.basicReceive(args)
elif args.rpcMode == 'call':
	receiver.rpcCallReceive(args)

